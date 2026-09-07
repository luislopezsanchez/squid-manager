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

export default function Asistente() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [reindexando, setReindexando] = useState(false)
  const [preguntando, setPreguntando] = useState(false)
  const [pregunta, setPregunta] = useState('')
  const [conversacion, setConversacion] = useState<Turno[]>([])
  const finRef = useRef<HTMLDivElement>(null)
  const { showToast, ToastContainer } = useToast()

  const cargar = () => api.getAiConfig().then(setConfig).catch(() => showToast(traducir("Error al cargar la configuración del asistente"), 'error'))

  useEffect(() => {
    cargar().finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversacion])

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
  const necesitaKeyDeEmbeddings = config.provider !== 'gemini'

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

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="field-label block mb-1.5">{traducir("Proveedor (responde la pregunta)")}</label>
            <select
              value={config.provider}
              onChange={e => setConfig({ ...config, provider: e.target.value })}
              className="input"
            >
              {PROVEEDORES.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("Modelo")}</label>
            <input type="text" value={config.chat_model} onChange={e => setConfig({ ...config, chat_model: e.target.value })}
              placeholder={proveedorActual?.ejemploModelo} className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">
              {traducir("API key")} {necesitaKeyDeEmbeddings ? `(${proveedorActual?.label})` : ''}
            </label>
            <input type="password" value={config.api_key} onChange={e => setConfig({ ...config, api_key: e.target.value })}
              placeholder={config.api_key === '***' ? traducir('Ya guardada — escribí una nueva para reemplazarla') : ''}
              className="input font-mono text-sm" />
          </div>
          {necesitaKeyDeEmbeddings && (
            <div>
              <label className="field-label block mb-1.5">{traducir("API key de Gemini (para buscar en la documentación)")}</label>
              <input type="password" value={config.embedding_api_key} onChange={e => setConfig({ ...config, embedding_api_key: e.target.value })}
                placeholder={config.embedding_api_key === '***' ? traducir('Ya guardada — escribí una nueva para reemplazarla') : ''}
                className="input font-mono text-sm" />
              <p className="text-xs text-ink-3 mt-1">
                {traducir("La búsqueda semántica en la documentación siempre usa Gemini, sea cual sea el proveedor que responde.")}
              </p>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center gap-3 flex-wrap">
          <button onClick={handleSave} disabled={saving} className="btn btn-primary disabled:opacity-50">
            {saving ? traducir('Guardando...') : traducir('Guardar Configuración')}
          </button>
          <button onClick={handleReindexar} disabled={reindexando || !config.provider} className="btn btn-ghost disabled:opacity-50"
            title={traducir("Vuelve a leer toda la documentación y recalcular la búsqueda — hace falta la API key de Gemini guardada")}>
            {reindexando ? traducir('Indexando… puede tardar unos minutos') : traducir('Reindexar documentación')}
          </button>
          <span className="text-xs text-ink-3">
            {traducir("Fragmentos indexados")}: {config.fragmentos_indexados}
          </span>
        </div>
      </div>

      {/* Conversación */}
      <div className="card p-6">
        <h2 className="font-medium text-ink mb-4">{traducir("Preguntas")}</h2>

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
