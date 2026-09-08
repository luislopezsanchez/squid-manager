import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { IconAssistant } from '../components/Icons'
import { Markdown } from '../components/Markdown'

const PROVEEDORES = [
  { value: 'gemini', label: 'Gemini (Google)', ejemploModelo: 'gemini-flash-latest' },
  { value: 'groq', label: 'Groq', ejemploModelo: 'openai/gpt-oss-20b' },
  { value: 'nvidia_nim', label: 'NVIDIA NIM', ejemploModelo: 'meta/llama-3.1-8b-instruct' },
  { value: 'ollama_cloud', label: 'Ollama Cloud', ejemploModelo: 'llama3.1' },
]

type Turno = { pregunta: string; respuesta: string; fuentes: { archivo: string; seccion: string | null }[] }

// La conversación se guarda en sessionStorage -viva mientras dure la
// pestaña/sesión del navegador, como pidió el usuario, sin necesidad de
// nada en el backend para algo que es puramente una comodidad de la UI-.
const CLAVE_CONVERSACION = 'squidmanager:asistente:conversacion'

function cargarConversacion(): Turno[] {
  try {
    const guardado = sessionStorage.getItem(CLAVE_CONVERSACION)
    return guardado ? JSON.parse(guardado) : []
  } catch {
    return []
  }
}

export default function Asistente() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [reindexando, setReindexando] = useState(false)
  const [preguntando, setPreguntando] = useState(false)
  const [pregunta, setPregunta] = useState('')
  const [conversacion, setConversacion] = useState<Turno[]>(cargarConversacion)
  const finRef = useRef<HTMLDivElement>(null)
  const { showToast, ToastContainer } = useToast()

  // Modelos de chat listados tras "Probar conexión" -null hasta que se
  // prueba (o cambia el proveedor, que invalida la lista anterior)-.
  const [probandoProveedor, setProbandoProveedor] = useState(false)
  const [modelosProveedor, setModelosProveedor] = useState<string[] | null>(null)

  const [probandoEmbeddings, setProbandoEmbeddings] = useState(false)
  const [embeddingsOk, setEmbeddingsOk] = useState<number | null>(null)

  const cargar = () => api.getAiConfig().then(setConfig).catch(() => showToast(traducir("Error al cargar la configuración del asistente"), 'error'))

  useEffect(() => {
    cargar().finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversacion])

  useEffect(() => {
    try {
      sessionStorage.setItem(CLAVE_CONVERSACION, JSON.stringify(conversacion))
    } catch {
      // localStorage/sessionStorage puede fallar (modo privado, cuota) — no
      // es crítico, la conversación simplemente no sobrevive al reload.
    }
  }, [conversacion])

  const handleLimpiarConversacion = () => {
    setConversacion([])
    try {
      sessionStorage.removeItem(CLAVE_CONVERSACION)
    } catch {
      // ver nota arriba
    }
  }

  const handleCambiarProveedor = (provider: string) => {
    setConfig({ ...config, provider })
    setModelosProveedor(null) // la lista de modelos era del proveedor anterior
  }

  const handleProbarProveedor = async () => {
    if (!config.api_key || config.api_key === '***') {
      showToast(traducir("Escribí la API key antes de probar la conexión"), 'warning')
      return
    }
    setProbandoProveedor(true)
    setModelosProveedor(null)
    try {
      const r = await api.probarProveedorAi(config.provider, config.api_key)
      const modelos: string[] = r.modelos || []
      setModelosProveedor(modelos)
      if (modelos.length > 0 && !modelos.includes(config.chat_model)) {
        const sugerido = modelos.find(m => m === proveedorActual?.ejemploModelo) || modelos[0]
        setConfig((c: any) => ({ ...c, chat_model: sugerido }))
      }
      showToast(
        modelos.length > 0
          ? traducir(`Conexión exitosa: ${modelos.length} modelos disponibles`)
          : traducir("Conexión exitosa, pero el proveedor no devolvió modelos"),
        'success',
      )
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setProbandoProveedor(false)
    }
  }

  const handleProbarEmbeddings = async () => {
    if (!config.embedding_api_key || config.embedding_api_key === '***') {
      showToast(traducir("Escribí la API key de Jina antes de probar"), 'warning')
      return
    }
    setProbandoEmbeddings(true)
    setEmbeddingsOk(null)
    try {
      const r = await api.probarEmbeddingsAi(config.embedding_api_key)
      setEmbeddingsOk(r.dimensiones)
      showToast(traducir("Conexión con Jina AI exitosa"), 'success')
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setProbandoEmbeddings(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateAiConfig({
        enabled: config.enabled,
        provider: config.provider,
        api_key: config.api_key,
        embedding_api_key: config.embedding_api_key,
        chat_model: config.chat_model,
        embedding_model: config.embedding_model,
      })
      showToast(traducir("Configuración guardada correctamente"), 'success')
      cargar()
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleReindexar = async () => {
    setReindexando(true)
    try {
      const r = await api.reindexarDocumentacion()
      showToast(
        traducir(`Documentación indexada: ${r.fragmentos} fragmentos de ${r.archivos} archivos`) +
          (r.saltados?.length ? ` (${r.saltados.length} con error, ver consola)` : ''),
        'success',
      )
      if (r.saltados?.length) console.warn('Fragmentos saltados al indexar:', r.saltados)
      cargar()
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setReindexando(false)
    }
  }

  const handlePreguntar = async (e: React.FormEvent) => {
    e.preventDefault()
    const texto = pregunta.trim()
    if (!texto || preguntando) return
    setPreguntando(true)
    setPregunta('')
    try {
      const r = await api.preguntarAsistente(texto)
      setConversacion(prev => [...prev, { pregunta: texto, respuesta: r.respuesta, fuentes: r.fuentes || [] }])
    } catch (e: any) {
      setConversacion(prev => [...prev, { pregunta: texto, respuesta: `⚠️ ${e.message}`, fuentes: [] }])
    } finally {
      setPreguntando(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>
  if (!config) return <div className="p-8 text-center text-ink-3">{traducir("No se pudo cargar la configuración")}</div>

  const proveedorActual = PROVEEDORES.find(p => p.value === config.provider)

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Asistente")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Responde consultas sobre cómo usar el panel, basándose únicamente en la documentación del proyecto. No tiene acceso a la configuración real de este servidor ni puede ejecutar ninguna acción.")}
      </p>

      {/* Configuración */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-medium text-ink">{traducir("Configuración")}</h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={e => setConfig({ ...config, enabled: e.target.checked })}
              className="w-5 h-5 rounded text-primary-600"
            />
            <span className="text-sm text-ink-2">{traducir("Habilitar")}</span>
          </label>
        </div>

        {/* Paso 1: proveedor + su API key + probar conexión */}
        <div className="mb-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-3 mb-2">
            {traducir("1. Proveedor que responde las preguntas")}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="field-label block mb-1.5">{traducir("Proveedor")}</label>
              <select value={config.provider} onChange={e => handleCambiarProveedor(e.target.value)} className="input">
                {PROVEEDORES.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label block mb-1.5">{traducir("API key")} ({proveedorActual?.label})</label>
              <input
                type="password"
                value={config.api_key}
                onChange={e => { setConfig({ ...config, api_key: e.target.value }); setModelosProveedor(null) }}
                placeholder={config.api_key === '***' ? traducir('Ya guardada — escribí una nueva para reemplazarla') : ''}
                className="input font-mono text-sm"
              />
            </div>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleProbarProveedor}
              disabled={probandoProveedor || !config.api_key}
              className="btn btn-ghost disabled:opacity-50"
            >
              {probandoProveedor ? traducir('Probando…') : traducir('Probar conexión')}
            </button>
            {modelosProveedor !== null && (
              <span className="text-xs text-ok font-medium">
                ✓ {traducir(`Conectado — ${modelosProveedor.length} modelos disponibles`)}
              </span>
            )}
          </div>

          <div className="mt-3">
            <label className="field-label block mb-1.5">{traducir("Modelo")}</label>
            {modelosProveedor && modelosProveedor.length > 0 ? (
              <select
                value={config.chat_model || ''}
                onChange={e => setConfig({ ...config, chat_model: e.target.value })}
                className="input font-mono text-sm"
              >
                {!modelosProveedor.includes(config.chat_model) && config.chat_model && (
                  <option value={config.chat_model}>{config.chat_model} ({traducir("guardado")})</option>
                )}
                {modelosProveedor.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            ) : (
              <>
                <input
                  type="text"
                  value={config.chat_model || ''}
                  onChange={e => setConfig({ ...config, chat_model: e.target.value })}
                  placeholder={proveedorActual?.ejemploModelo}
                  className="input font-mono text-sm"
                />
                <p className="text-xs text-ink-3 mt-1">
                  {traducir("Probá la conexión arriba para elegir de la lista real de modelos disponibles con esta key.")}
                </p>
              </>
            )}
          </div>
        </div>

        {/* Paso 2: Jina AI, fijo, para la búsqueda en la documentación */}
        <div className="mb-5 pt-4 border-t border-line-soft">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-3 mb-2">
            {traducir("2. Búsqueda en la documentación (siempre Jina AI)")}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
            <div>
              <label className="field-label block mb-1.5">{traducir("API key de Jina AI")}</label>
              <input
                type="password"
                value={config.embedding_api_key || ''}
                onChange={e => { setConfig({ ...config, embedding_api_key: e.target.value }); setEmbeddingsOk(null) }}
                placeholder={config.embedding_api_key === '***' ? traducir('Ya guardada — escribí una nueva para reemplazarla') : ''}
                className="input font-mono text-sm"
              />
              <p className="text-xs text-ink-3 mt-1">
                {traducir("Se usa siempre para buscar en la documentación, sea cual sea el proveedor elegido arriba. Se genera gratis en jina.ai.")}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleProbarEmbeddings}
                disabled={probandoEmbeddings || !config.embedding_api_key}
                className="btn btn-ghost disabled:opacity-50"
              >
                {probandoEmbeddings ? traducir('Probando…') : traducir('Probar conexión')}
              </button>
              {embeddingsOk !== null && (
                <span className="text-xs text-ok font-medium">✓ {traducir("Conectado")}</span>
              )}
            </div>
          </div>
        </div>

        {/* Paso 3: guardar */}
        <div className="pt-4 border-t border-line-soft flex items-center gap-3 flex-wrap">
          <button onClick={handleSave} disabled={saving} className="btn btn-primary disabled:opacity-50">
            {saving ? traducir('Guardando...') : traducir('3. Guardar Configuración')}
          </button>
          <button onClick={handleReindexar} disabled={reindexando || !config.provider} className="btn btn-ghost disabled:opacity-50"
            title={traducir("Vuelve a leer toda la documentación y recalcular la búsqueda — hace falta la API key de Jina guardada")}>
            {reindexando ? traducir('Indexando… puede tardar unos minutos') : traducir('Reindexar documentación')}
          </button>
          <span className="text-xs text-ink-3">
            {traducir("Fragmentos indexados")}: {config.fragmentos_indexados}
          </span>
        </div>
      </div>

      {/* Conversación */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-medium text-ink">{traducir("Preguntas")}</h2>
          {conversacion.length > 0 && (
            <button onClick={handleLimpiarConversacion} className="text-xs text-ink-3 hover:text-danger transition">
              {traducir("Limpiar conversación")}
            </button>
          )}
        </div>

        {!config.enabled ? (
          <p className="text-sm text-ink-3">{traducir("Activá el asistente arriba para poder hacer preguntas.")}</p>
        ) : config.fragmentos_indexados === 0 ? (
          <p className="text-sm text-ink-3">{traducir("Todavía no se indexó la documentación — pulsá \"Reindexar documentación\" arriba.")}</p>
        ) : (
          <>
            <div className="space-y-4 mb-4 max-h-[28rem] overflow-y-auto">
              {conversacion.length === 0 && (
                <p className="text-sm text-ink-3">{traducir("Escribí una pregunta sobre cómo usar el panel, por ejemplo: \"¿cómo bloqueo el acceso a una página web?\"")}</p>
              )}
              {conversacion.map((turno, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-end">
                    <div className="bg-brand-700 text-white rounded-lg rounded-br-sm px-4 py-2 max-w-[80%] text-sm">
                      {turno.pregunta}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="bg-brand-50 border border-line rounded-lg rounded-bl-sm px-4 py-3 max-w-[85%]">
                      <Markdown texto={turno.respuesta} />
                      {turno.fuentes.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-line-soft flex flex-wrap gap-1.5">
                          {turno.fuentes.map((f, j) => (
                            <span key={j} className="text-[11px] text-ink-3 bg-white border border-line rounded px-1.5 py-0.5">
                              {f.archivo}{f.seccion ? ` — ${f.seccion}` : ''}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {preguntando && <p className="text-sm text-ink-3 italic">{traducir("Pensando...")}</p>}
              <div ref={finRef} />
            </div>

            <form onSubmit={handlePreguntar} className="flex gap-3">
              <input
                type="text"
                value={pregunta}
                onChange={e => setPregunta(e.target.value)}
                placeholder={traducir("Escribí tu pregunta...")}
                disabled={preguntando}
                className="input flex-1"
              />
              <button type="submit" disabled={preguntando || !pregunta.trim()} className="btn btn-primary disabled:opacity-50">
                <IconAssistant className="w-4 h-4" />{traducir('Preguntar')}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
