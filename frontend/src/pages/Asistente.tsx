import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api, canWrite } from '../api/client'
import { useToast } from '../components/Toast'
import { IconAssistant } from '../components/Icons'
import { Markdown } from '../components/Markdown'
import { LoadingState, ErrorState } from '../components/AsyncState'

interface Proveedor {
  id: string; nombre: string; tipo: string; url_defecto: string; url_editable: boolean
  requiere_clave: boolean; modelo_ejemplo: string; agentico: boolean; ayuda: string
}

type Propuesta = { accion: string; argumentos: Record<string, any> }
type Turno = {
  pregunta: string; respuesta: string
  fuentes: { archivo: string; seccion: string | null }[]
  herramientasUsadas?: string[]
  propuesta?: Propuesta | null
  propuestaEstado?: 'pendiente' | 'aplicada' | 'descartada'
}

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
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
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

  const cargar = () => api.getAiConfig().then(r => { setConfig(r); setLoadError(false) })
    .catch(() => { showToast(traducir("Error al cargar la configuración del asistente"), 'error'); setLoadError(true) })

  useEffect(() => {
    api.listAiProviders().then(setProveedores).catch(() => {})
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

  const proveedorDe = (id: string) => proveedores.find(p => p.id === id)

  const handleCambiarProveedor = (provider: string) => {
    const p = proveedorDe(provider)
    setConfig({
      ...config, provider,
      base_url: p?.url_editable ? (config.base_url || p.url_defecto) : '',
      agentic_enabled: config.agentic_enabled && !!p?.agentico,
    })
    setModelosProveedor(null) // la lista de modelos era del proveedor anterior
  }

  const handleProbarProveedor = async () => {
    const p = proveedorDe(config.provider)
    if (p?.requiere_clave && (!config.api_key || config.api_key === '***') ) {
      if (config.api_key !== '***') { showToast(traducir("Escribe la API key antes de probar la conexión"), 'warning'); return }
    }
    if (p?.url_editable && !config.base_url) { showToast(traducir("Escribe la URL del servicio antes de probar la conexión"), 'warning'); return }
    setProbandoProveedor(true)
    setModelosProveedor(null)
    try {
      const r = await api.probarProveedorAi(config.provider, config.api_key === '***' ? undefined : config.api_key, p?.url_editable ? config.base_url : undefined)
      const modelos: string[] = r.modelos || []
      setModelosProveedor(modelos)
      if (modelos.length > 0 && !modelos.includes(config.chat_model)) {
        const sugerido = modelos.find(m => m === p?.modelo_ejemplo) || modelos[0]
        setConfig((c: any) => ({ ...c, chat_model: sugerido }))
      }
      showToast(
        modelos.length > 0
          ? traducir("Conexión exitosa: {n} modelos disponibles", { n: modelos.length })
          : traducir("Conexión exitosa, pero el proveedor no devolvió modelos"),
        'success',
      )
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setProbandoProveedor(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateAiConfig({
        enabled: config.enabled,
        provider: config.provider,
        api_key: config.api_key,
        base_url: config.base_url || null,
        chat_model: config.chat_model,
        agentic_enabled: config.agentic_enabled,
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
        traducir("Documentación indexada: {f} fragmentos de {a} archivos", { f: r.fragmentos, a: r.archivos }) +
          (r.saltados?.length ? ` (${r.saltados.length} ${traducir("con error, ver consola")})` : ''),
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
      setConversacion(prev => [...prev, {
        pregunta: texto, respuesta: r.respuesta, fuentes: r.fuentes || [],
        herramientasUsadas: r.herramientas_usadas || [],
        propuesta: r.propuesta || null,
        propuestaEstado: r.propuesta ? 'pendiente' : undefined,
      }])
    } catch (e: any) {
      setConversacion(prev => [...prev, { pregunta: texto, respuesta: `⚠️ ${e.message}`, fuentes: [] }])
    } finally {
      setPreguntando(false)
    }
  }

  const handleAplicarPropuesta = async (indice: number) => {
    const turno = conversacion[indice]
    if (!turno.propuesta) return
    try {
      if (turno.propuesta.accion === 'proponer_crear_acl') {
        const a = turno.propuesta.argumentos
        await api.createAcl({
          name: a.name, type: a.type, value: a.value,
          description: a.description || '', enabled: true,
        })
        showToast(traducir('ACL "{n}" creada', { n: a.name }), 'success')
      } else {
        // Defensivo: si algún día se suma una herramienta "proponer_*" nueva
        // y se olvida agregarle su rama acá, mejor avisar con claridad que
        // marcarla como "aplicada" sin haber hecho nada -eso engañaría al
        // administrador haciéndole creer que el cambio ya está en efecto.
        showToast(traducir('No sé cómo aplicar esta propuesta ("{accion}") todavía.', { accion: turno.propuesta.accion }), 'error')
        return
      }
      setConversacion(prev => prev.map((t, i) => i === indice ? { ...t, propuestaEstado: 'aplicada' } : t))
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    }
  }

  const handleDescartarPropuesta = (indice: number) => {
    setConversacion(prev => prev.map((t, i) => i === indice ? { ...t, propuestaEstado: 'descartada' } : t))
  }

  if (loading) return <LoadingState />
  if (loadError && !config) return <ErrorState onRetry={cargar} />
  if (!config) return <div className="p-8 text-center text-ink-3">{traducir("No se pudo cargar la configuración")}</div>

  const proveedorActual = proveedorDe(config.provider)
  const agenticoPosible = !!proveedorActual?.agentico

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Asistente")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {config.agentic_enabled
          ? traducir("Responde consultas sobre SquidManager y puede consultar la configuración real de este servidor para diagnosticar. Puede proponer cambios, pero nunca los aplica solo -siempre pide tu confirmación-, y no tiene acceso a archivos ni al código fuente del proyecto.")
          : traducir("Responde consultas sobre cómo usar el panel, basándose únicamente en la documentación del proyecto. No tiene acceso a la configuración real de este servidor ni puede ejecutar ninguna acción.")}
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

        <div className="mb-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="ai-provider" className="field-label block mb-1.5">{traducir("Proveedor de IA")}</label>
              <select id="ai-provider" value={config.provider} onChange={e => handleCambiarProveedor(e.target.value)} className="input">
                {proveedores.map(p => <option key={p.id} value={p.id}>{traducir(p.nombre)}</option>)}
              </select>
              {proveedorActual?.ayuda && <p className="field-help mt-1">{traducir(proveedorActual.ayuda)}</p>}
            </div>
            {proveedorActual?.url_editable ? (
              <div>
                <label htmlFor="ai-base-url" className="field-label block mb-1.5">{traducir("URL del servicio")}</label>
                <input id="ai-base-url" type="text" value={config.base_url || ''}
                  onChange={e => { setConfig({ ...config, base_url: e.target.value }); setModelosProveedor(null) }}
                  placeholder="https://mi-servidor/v1" className="input font-mono text-sm" />
              </div>
            ) : (
              <div>
                <label htmlFor="ai-api-key-a" className="field-label block mb-1.5">{traducir("API key")}</label>
                <input id="ai-api-key-a" type="password" value={config.api_key}
                  onChange={e => { setConfig({ ...config, api_key: e.target.value }); setModelosProveedor(null) }}
                  placeholder={config.api_key === '***' ? traducir('Ya guardada — escribe una nueva para reemplazarla') : ''}
                  className="input font-mono text-sm" autoComplete="off" />
              </div>
            )}
            {proveedorActual?.url_editable && (
              <div className="md:col-span-2">
                <label htmlFor="ai-api-key-b" className="field-label block mb-1.5">
                  {traducir("API key")} {!proveedorActual.requiere_clave && <span className="font-normal text-ink-3">({traducir("opcional: solo si tu servicio la pide")})</span>}
                </label>
                <input id="ai-api-key-b" type="password" value={config.api_key}
                  onChange={e => { setConfig({ ...config, api_key: e.target.value }); setModelosProveedor(null) }}
                  placeholder={config.api_key === '***' ? traducir('Ya guardada — escribe una nueva para reemplazarla') : ''}
                  className="input font-mono text-sm" autoComplete="off" />
              </div>
            )}
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button onClick={handleProbarProveedor} disabled={probandoProveedor} className="btn btn-ghost disabled:opacity-50">
              {probandoProveedor ? traducir('Probando…') : traducir('Probar conexión')}
            </button>
            {modelosProveedor !== null && (
              <span className="text-xs text-ok font-medium">
                ✓ {traducir("Conectado — {n} modelos disponibles", { n: modelosProveedor.length })}
              </span>
            )}
          </div>

          <div className="mt-3">
            <label htmlFor="ai-chat-model" className="field-label block mb-1.5">{traducir("Modelo")}</label>
            {modelosProveedor && modelosProveedor.length > 0 ? (
              <select id="ai-chat-model" value={config.chat_model || ''} onChange={e => setConfig({ ...config, chat_model: e.target.value })} className="input font-mono text-sm">
                {!modelosProveedor.includes(config.chat_model) && config.chat_model && (
                  <option value={config.chat_model}>{config.chat_model} ({traducir("guardado")})</option>
                )}
                {modelosProveedor.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            ) : (
              <>
                <input id="ai-chat-model" type="text" value={config.chat_model || ''}
                  onChange={e => setConfig({ ...config, chat_model: e.target.value })}
                  placeholder={proveedorActual?.modelo_ejemplo} className="input font-mono text-sm" />
                <p className="text-xs text-ink-3 mt-1">
                  {traducir("Prueba la conexión arriba para elegir de la lista real de modelos disponibles.")}
                </p>
              </>
            )}
          </div>

          <div className="note note-info mt-4">
            <p className="note-text">
              {traducir("Solo necesitas un proveedor. La búsqueda en la documentación es local (se indexa sola al arrancar y al actualizar) y no usa ningún otro servicio. Con Ollama en tu red, nada sale a Internet.")}
            </p>
          </div>

          <label className={`flex items-start gap-2 mt-4 pt-4 border-t border-line-soft ${agenticoPosible ? 'cursor-pointer' : 'opacity-50'}`}>
            <input type="checkbox" checked={!!config.agentic_enabled} disabled={!agenticoPosible}
              onChange={e => setConfig({ ...config, agentic_enabled: e.target.checked })} className="w-4 h-4 mt-0.5 rounded" />
            <span className="text-sm text-ink-2">
              {traducir("Modo agéntico (fase 1): puede consultar ACLs, reglas, grupos y ajustes reales")}
              <span className="block text-xs text-ink-3 mt-0.5">
                {agenticoPosible
                  ? traducir("También puede proponer cambios de configuración -nunca los aplica solo, siempre pide tu confirmación-. Estos datos salen hacia el proveedor de IA, no solo la documentación.")
                  : traducir("No disponible con este proveedor todavía.")}
              </span>
            </span>
          </label>
        </div>

        {/* Paso 3: guardar */}
        <div className="pt-4 border-t border-line-soft flex items-center gap-3 flex-wrap">
          <button onClick={handleSave} disabled={saving} className="btn btn-primary disabled:opacity-50">
            {saving ? traducir('Guardando...') : traducir('Guardar configuración')}
          </button>
          <button onClick={handleReindexar} disabled={reindexando} className="btn btn-ghost disabled:opacity-50"
            title={traducir("Vuelve a leer toda la documentación. Normalmente no hace falta: se indexa sola al arrancar y cuando cambia.")}>
            {reindexando ? traducir('Indexando…') : traducir('Reindexar documentación')}
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
          <p className="text-sm text-ink-3">{traducir("La documentación se está indexando (tarda unos segundos tras arrancar). Si sigue así, pulsa «Reindexar documentación» arriba.")}</p>
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
                      {!!turno.herramientasUsadas?.length && (
                        <p className="mt-2 pt-2 border-t border-line-soft text-[11px] text-ink-3">
                          {traducir("Consultó")}: {turno.herramientasUsadas.join(', ')}
                        </p>
                      )}
                    </div>
                  </div>

                  {turno.propuesta && (
                    <div className="flex justify-start">
                      <div className="border border-brand-300 bg-white rounded-lg px-4 py-3 max-w-[85%] w-full">
                        <p className="text-xs font-semibold uppercase tracking-wide text-brand-700 mb-2">
                          {traducir("Propuesta -sin aplicar todavía")}
                        </p>
                        <pre className="text-xs bg-brand-50 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                          {JSON.stringify(turno.propuesta.argumentos, null, 2)}
                        </pre>
                        {turno.propuestaEstado === 'aplicada' ? (
                          <p className="text-xs text-ok font-medium mt-2">✓ {traducir("Aplicada")}</p>
                        ) : turno.propuestaEstado === 'descartada' ? (
                          <p className="text-xs text-ink-3 mt-2">{traducir("Descartada")}</p>
                        ) : canWrite() ? (
                          <div className="flex gap-2 mt-2">
                            <button onClick={() => handleAplicarPropuesta(i)} className="btn btn-primary btn-sm">
                              {traducir("Aplicar")}
                            </button>
                            <button onClick={() => handleDescartarPropuesta(i)} className="btn btn-ghost btn-sm">
                              {traducir("Descartar")}
                            </button>
                          </div>
                        ) : (
                          // Preguntar está abierto también a cuentas de solo lectura
                          // (ver routes/ai.py), pero aplicar una propuesta termina
                          // llamando a un endpoint que exige permisos de escritura
                          // -mejor decirlo acá que dejar clickear "Aplicar" y
                          // mostrar un 403 crudo.
                          <p className="text-xs text-ink-3 mt-2">
                            {traducir("Tu cuenta es de solo lectura: pedile a un administrador con permisos de escritura que la aplique.")}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {preguntando && (
                <p className="text-sm text-ink-3 italic">
                  {traducir("Pensando... (puede tardar hasta un minuto)")}
                </p>
              )}
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
