import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { formatRate, formatNumber, formatBytes } from '../utils/format'
import { IconRefresh, IconEdit, IconTrash, IconGlobe, IconUpload, IconClose } from '../components/Icons'
import { LoadingState, ErrorState } from '../components/AsyncState'

interface Node {
  id: number
  name: string
  url: string
  username: string
  password: string
  enabled: boolean
}

interface NodeStatus {
  // null solo en la raíz (este servidor): no es un MonitoredNode de la
  // tabla, no tiene fila propia que editar/borrar ni endpoint de detalle.
  id: number | null
  name: string
  url: string | null
  instance_id?: string | null
  squid_port?: string | null
  status: 'ok' | 'error'
  message?: string
  // Árbol real (no solo un nivel): cada nodo remoto ya trae SUS propios
  // hijos, resueltos del lado de ESE servidor -ver
  // central_monitor_service.consultar_arbol. Vacío, nunca undefined: así
  // el render recursivo no necesita `?? []` en cada punto de uso.
  children: NodeStatus[]
  data?: {
    traffic: {
      total_bytes_per_second: number
      active_ips: string[]
      active_users: string[]
      denied_requests_60s: number
    }
    system: {
      cpu: { percent: number }
      memory: { percent: number }
    }
  }
}

interface NodoDetalle {
  id: number
  name: string
  status: 'ok' | 'error'
  message?: string
  top_users: { user: string; bytes: number; requests: number }[] | null
  top_domains: { domain: string; requests: number; bytes: number }[] | null
  connections: { time: string; user: string; domain: string; status: number; bytes: number; denied: boolean }[] | null
}

function hostPuertoDe(nodo: NodeStatus): string | null {
  if (!nodo.url) return null
  try {
    const host = new URL(nodo.url).hostname
    return nodo.squid_port ? `${host}:${nodo.squid_port}` : host
  } catch {
    return null
  }
}

function TarjetaNodo({ nodo, esRaiz, nivel, ruta, onVerMas }: {
  nodo: NodeStatus; esRaiz: boolean
  // Nivel calculado en el momento, según la profundidad de ESTE recorrido
  // -nunca guardado en ningún lado, ver docs/project-log.md: el mismo nodo
  // puede ser "nivel 1" visto desde su propio panel y "nivel 2" visto desde
  // el de su padre, no hay un número fijo que asignarle de antemano.
  nivel: number
  // Ids desde el hijo DIRECTO de este servidor hasta este nodo (un hijo
  // directo es una ruta de un solo elemento) -lo que necesita el backend
  // para pedir el detalle de un nieto/bisnieto sin tener sus credenciales:
  // cada salto resuelve un id con las suyas y reenvía el resto. Ver
  // GET /central/nodes/detalle-por-ruta.
  ruta: number[]
  onVerMas: (n: NodeStatus, ruta: number[]) => void
}) {
  const enLinea = nodo.status === 'ok'
  const hostPuerto = hostPuertoDe(nodo)
  return (
    <div className={`card p-4 text-left w-60 relative ${
      esRaiz ? 'border-brand-500 border-2' : enLinea ? '' : 'border-rose-200'
    }`}>
      {esRaiz && (
        <span className="absolute -top-2.5 left-3.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-brand-700 text-white">
          {traducir("Este servidor")}
        </span>
      )}
      <div className="flex items-center justify-between gap-2 mb-1">
        <h3 className="font-medium text-ink flex items-center gap-1.5 min-w-0">
          <IconGlobe className="w-4 h-4 text-ink-3 flex-none" />
          <span className="truncate" title={nodo.name}>{nodo.name}</span>
        </h3>
        <span className={`flex-none ${enLinea ? 'pill-ok' : 'pill-danger'}`}>
          {enLinea ? traducir("En línea") : traducir("Sin conexión")}
        </span>
      </div>
      <p className="text-[10px] font-bold uppercase tracking-wide text-ink-3 mb-2">
        {traducir("Nivel {n}", { n: String(nivel) })}{esRaiz ? ` (${traducir("este panel")})` : ''}
      </p>
      {hostPuerto && <p className="text-xs text-ink-3 font-mono mb-2 truncate">{hostPuerto}</p>}
      {enLinea && nodo.data ? (
        <div className="grid grid-cols-2 gap-2 text-sm mb-1">
          <div>
            <p className="text-ink-3 text-xs">{traducir("Tráfico actual")}</p>
            <p className="font-medium">{formatRate(nodo.data.traffic.total_bytes_per_second)}</p>
          </div>
          <div>
            <p className="text-ink-3 text-xs">{traducir("Usuarios activos")}</p>
            <p className="font-medium">{formatNumber(nodo.data.traffic.active_users.length)}</p>
          </div>
        </div>
      ) : (
        <p className="text-xs text-rose-700 mb-1">{nodo.message}</p>
      )}
      {!esRaiz && (
        <div className="mt-2 pt-2 border-t border-line-soft text-right">
          <button onClick={() => onVerMas(nodo, ruta)} className="text-xs font-medium text-brand-700 hover:underline">
            {traducir("Ver más")} →
          </button>
        </div>
      )}
    </div>
  )
}

function ArbolNodo({ nodo, esRaiz, nivel, ruta, onVerMas }: {
  nodo: NodeStatus; esRaiz: boolean; nivel: number; ruta: number[]
  onVerMas: (n: NodeStatus, ruta: number[]) => void
}) {
  return (
    <li>
      <TarjetaNodo nodo={nodo} esRaiz={esRaiz} nivel={nivel} ruta={ruta} onVerMas={onVerMas} />
      {nodo.children.length > 0 && (
        <ul>
          {nodo.children.map((hijo, i) => (
            <ArbolNodo
              key={hijo.id ?? `${hijo.name}-${i}`}
              nodo={hijo} esRaiz={false} nivel={nivel + 1}
              ruta={hijo.id !== null ? [...ruta, hijo.id] : ruta}
              onVerMas={onVerMas}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

function BarraProporcion({ etiqueta, valor, maximo, color }: { etiqueta: string; valor: string; maximo: number; color: string }) {
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="truncate" title={etiqueta}>{etiqueta}</span>
        <b className="flex-none ml-2">{valor}</b>
      </div>
      <div className="h-1.5 rounded-full bg-line-soft overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${Math.max(maximo, 1)}%`, background: color }} />
      </div>
    </div>
  )
}

function ModalDetalleNodo({ nodo, ruta, onClose }: { nodo: NodeStatus; ruta: number[]; onClose: () => void }) {
  const [detalle, setDetalle] = useState<NodoDetalle | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (ruta.length === 0) return
    setCargando(true)
    setError(false)
    api.getCentralNodeDetallePorRuta(ruta)
      .then(r => {
        if (r.status !== 'ok') setError(true)
        setDetalle(r)
      })
      .catch(() => setError(true))
      .finally(() => setCargando(false))
  }, [ruta.join(',')])

  const maxBytesUsuarios = detalle?.top_users?.length ? Math.max(...detalle.top_users.map(u => u.bytes), 1) : 1
  const maxReqDominios = detalle?.top_domains?.length ? Math.max(...detalle.top_domains.map(d => d.requests), 1) : 1
  const hostPuerto = hostPuertoDe(nodo)

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-lg overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line-soft flex-none">
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="text-lg font-bold text-ink truncate">{nodo.name}</h2>
            <span className={nodo.status === 'ok' ? 'pill-ok flex-none' : 'pill-danger flex-none'}>
              {nodo.status === 'ok' ? traducir("En línea") : traducir("Sin conexión")}
            </span>
          </div>
          <button onClick={onClose} aria-label={traducir("Cerrar")}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-ink-3 hover:bg-line-soft hover:text-ink transition flex-none">
            <IconClose className="w-4 h-4" />
          </button>
        </div>
        {hostPuerto && <p className="px-6 pt-3 text-xs text-ink-3 font-mono">{hostPuerto}</p>}

        {cargando ? (
          <p className="text-sm text-ink-3 text-center py-12">{traducir("Cargando...")}</p>
        ) : error && !detalle?.top_users && !detalle?.top_domains && !detalle?.connections ? (
          <p className="text-sm text-rose-700 text-center py-12">
            {detalle?.message || traducir("No se pudo obtener el detalle de este nodo.")}
          </p>
        ) : (
          <div className="px-6 py-4 overflow-y-auto">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-5">
              <div>
                <h3 className="text-xs font-bold text-ink uppercase mb-2">{traducir("Top usuarios")}</h3>
                {detalle?.top_users?.length ? (
                  <div className="flex flex-col gap-2">
                    {detalle.top_users.map(u => (
                      <BarraProporcion key={u.user} etiqueta={u.user} valor={formatBytes(u.bytes)}
                        maximo={(u.bytes / maxBytesUsuarios) * 100} color="var(--brand-400)" />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-ink-3">{traducir("Sin datos todavía.")}</p>
                )}
              </div>
              <div>
                <h3 className="text-xs font-bold text-ink uppercase mb-2">{traducir("Top sitios visitados")}</h3>
                {detalle?.top_domains?.length ? (
                  <div className="flex flex-col gap-2">
                    {detalle.top_domains.map(d => (
                      <BarraProporcion key={d.domain} etiqueta={d.domain} valor={traducir("{n} peticiones", { n: formatNumber(d.requests) })}
                        maximo={(d.requests / maxReqDominios) * 100} color="var(--brand-500)" />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-ink-3">{traducir("Sin datos todavía.")}</p>
                )}
              </div>
            </div>

            <h3 className="text-xs font-bold text-ink uppercase mb-2">{traducir("Últimas conexiones")}</h3>
            {detalle?.connections?.length ? (
              <table className="table-panel">
                <thead className="bg-brand-50 border-b border-line-soft">
                  <tr>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Hora")}</th>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Usuario")}</th>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Dominio")}</th>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Estado")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {detalle.connections.map((c, i) => (
                    <tr key={i} className={c.denied ? 'bg-red-50/40' : ''}>
                      <td className="px-3 py-1.5 text-xs text-ink-3 font-mono whitespace-nowrap">{c.time}</td>
                      <td className="px-3 py-1.5 text-xs font-medium truncate max-w-[140px]" title={c.user}>{c.user}</td>
                      <td className="px-3 py-1.5 text-xs font-mono text-ink-2 truncate max-w-[220px]" title={c.domain}>{c.domain}</td>
                      <td className="px-3 py-1.5 text-xs">
                        <span className={c.denied ? 'pill-danger' : 'pill-ok'}>{c.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs text-ink-3">{traducir("Sin datos todavía.")}</p>
            )}

            <p className="text-xs text-ink-3 mt-4">
              {traducir("Estos datos se piden aparte, bajo demanda, con la misma cuenta guardada para este nodo -el backend hace de intermediario, la contraseña del nodo remoto nunca llega al navegador.")}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

const FORM_VACIO = { name: '', url: '', username: '', password: '', enabled: true }

export default function PanelCentral() {
  const [config, setConfig] = useState<{ enabled: boolean; monitorizar_hijos: boolean; instance_id: string } | null>(null)
  const [savingConfig, setSavingConfig] = useState(false)
  const [nodes, setNodes] = useState<Node[]>([])
  const [raiz, setRaiz] = useState<NodeStatus | null>(null)
  const [loadingEstado, setLoadingEstado] = useState(true)
  const [estadoError, setEstadoError] = useState(false)
  const [ultimaActualizacion, setUltimaActualizacion] = useState<Date | null>(null)
  const [nodoDetalle, setNodoDetalle] = useState<{ nodo: NodeStatus; ruta: number[] } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState(FORM_VACIO)
  const [testing, setTesting] = useState(false)
  const [syncingId, setSyncingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ status: string; message?: string; monitoreo_centralizado_remoto?: boolean | null } | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { showToast, ToastContainer } = useToast()

  const loadConfig = () => {
    api.getCentralConfig().then(setConfig).catch(() => showToast(traducir("Error al cargar la configuración"), 'error'))
  }

  const handleToggleEnabled = async (checked: boolean) => {
    setSavingConfig(true)
    try {
      const nuevo = await api.updateCentralConfig(checked, config?.monitorizar_hijos ?? true)
      setConfig(nuevo)
      if (checked) { loadNodes(); loadEstado() }
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    } finally {
      setSavingConfig(false)
    }
  }

  const handleToggleMonitorizarHijos = async (checked: boolean) => {
    if (!config) return
    setSavingConfig(true)
    try {
      const nuevo = await api.updateCentralConfig(config.enabled, checked)
      setConfig(nuevo)
      loadEstado()
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    } finally {
      setSavingConfig(false)
    }
  }

  const loadNodes = () => {
    api.listCentralNodes().then(setNodes).catch(() => showToast(traducir("Error al cargar los nodos"), 'error'))
  }

  const loadEstado = () => {
    // self + children tal cual los arma el backend (ya es un árbol real,
    // cada hijo con los suyos propios) -ver central_monitor_service.
    // consultar_arbol_de_todos. Nada se aplana acá.
    api.getCentralDashboard()
      .then(r => {
        setRaiz({
          id: null,
          name: r.self.name,
          url: null,
          instance_id: r.self.instance_id,
          squid_port: r.self.squid_port,
          status: r.self.status,
          data: r.self.data,
          children: r.children,
        })
        setUltimaActualizacion(new Date())
        setEstadoError(false)
      })
      .catch(() => { showToast(traducir("Error al consultar el estado de los nodos"), 'error'); setEstadoError(true) })
      .finally(() => setLoadingEstado(false))
  }

  useEffect(() => {
    loadConfig()
  }, [])

  useEffect(() => {
    if (!config?.enabled) return
    loadNodes()
    loadEstado()
    // Cada nodo implica un login + un dashboard completo contra otra
    // instancia -no tiene sentido repetirlo cada pocos segundos como el
    // dashboard local, que solo lee de su propio proceso.
    intervalRef.current = setInterval(loadEstado, 30000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [config?.enabled])

  const resetForm = () => {
    setForm(FORM_VACIO)
    setEditingId(null)
    setTestResult(null)
  }

  const handleEdit = (node: Node) => {
    setForm({ name: node.name, url: node.url, username: node.username, password: '', enabled: node.enabled })
    setEditingId(node.id)
    setTestResult(null)
    setShowForm(true)
  }

  const handleTest = async () => {
    if (!form.url || !form.username || (!form.password && editingId === null)) {
      showToast(traducir("Completa URL, usuario y contraseña para probar la conexión"), 'error')
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const password = form.password || '***'
      const resultado = await api.testCentralNode({
        url: form.url, username: form.username, password,
        // Si la contraseña no se reescribió (queda "***"), esto le permite
        // al backend resolverla contra la guardada de este nodo -sin esto,
        // probar un nodo existente sin tocar la contraseña mandaba el
        // placeholder literal y la prueba fallaba siempre.
        id: editingId ?? undefined,
      })
      setTestResult(resultado)
    } catch (e: any) {
      setTestResult({ status: 'error', message: e.message })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingId !== null) {
        const data: any = { name: form.name, url: form.url, username: form.username, enabled: form.enabled }
        if (form.password) data.password = form.password
        await api.updateCentralNode(editingId, data)
        showToast(traducir("Nodo actualizado"))
      } else {
        await api.createCentralNode(form)
        showToast(traducir("Nodo agregado"))
      }
      resetForm()
      setShowForm(false)
      loadNodes()
      loadEstado()
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    }
  }

  const handleDelete = async (node: Node) => {
    if (!confirm(traducir('¿Eliminar el nodo "{n}"?', { n: node.name }))) return
    try {
      await api.deleteCentralNode(node.id)
      showToast(traducir("Nodo eliminado"))
      loadNodes()
      loadEstado()
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    }
  }

  const handleSync = async (node: Node) => {
    if (!confirm(traducir(
      'Esto SOBRESCRIBE la configuración de "{n}" con la de este servidor (ACLs, reglas, usuarios, grupos, cuotas...). ¿Continuar?',
      { n: node.name },
    ))) return
    setSyncingId(node.id)
    try {
      const resultado = await api.syncCentralNode(node.id)
      if (resultado.status === 'ok') {
        showToast(traducir('Configuración sincronizada a "{n}"', { n: node.name }))
      } else {
        showToast(resultado.message, 'error')
      }
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    } finally {
      setSyncingId(null)
    }
  }

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Monitoreo centralizado")}</h1>
          <p className="page-sub">{traducir("Métricas de este servidor y de otras instancias de SquidManager, en una sola vista")}</p>
        </div>
        {config?.enabled && (
          <button onClick={loadEstado} className="btn btn-outline flex items-center gap-2">
            <IconRefresh className="w-4 h-4" />
            {traducir("Actualizar")}
          </button>
        )}
      </div>

      {/* Apagado por defecto, mismo patrón que LDAP: un banner con el
          interruptor arriba de todo, y el resto de la página (nodos,
          dashboard) recién aparece una vez habilitado -no es solo estético,
          el backend también rechaza esas rutas con 403 mientras esté
          apagado (ver _requerir_habilitado en routes/central.py). */}
      <div className={`rounded-xl p-4 mb-6 border ${config?.enabled ? 'bg-green-50 border-green-200' : 'bg-brand-50 border-line'}`}>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className={`inline-flex h-3 w-3 rounded-full ${config?.enabled ? 'bg-ok' : 'bg-ink-3'}`} />
            <span className="text-sm font-medium text-ink">
              {config?.enabled ? traducir('Monitoreo centralizado activado') : traducir('Monitoreo centralizado desactivado')}
            </span>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config?.enabled ?? false}
              disabled={!config || savingConfig}
              onChange={e => handleToggleEnabled(e.target.checked)}
            />
            <span className="text-sm text-ink-2">{traducir("Habilitar")}</span>
          </label>
        </div>
        <p className="text-xs text-ink-3 mt-2">
          {traducir("Cada nodo se consulta con una cuenta propia del panel remoto (recomendado: un usuario con rol \"solo lectura\" dedicado a esto). No requiere ningún cambio en Squid ni que los nodos se conozcan entre sí. Mientras esté desactivado, este servidor tampoco responde si otro SquidManager lo agrega a él como nodo.")}
        </p>

        {config?.enabled && (
          <div className="mt-3 pt-3 border-t border-line-soft/70">
            <label className="flex items-center gap-2 cursor-pointer w-fit">
              <input
                type="checkbox"
                checked={config?.monitorizar_hijos ?? true}
                disabled={savingConfig}
                onChange={e => handleToggleMonitorizarHijos(e.target.checked)}
              />
              <span className="text-sm text-ink-2">{traducir("Monitorizar mis propios nodos")}</span>
            </label>
            <p className="text-xs text-ink-3 mt-1.5">
              {traducir("Independiente de arriba: este servidor siempre puede seguir siendo visto por otro SquidManager que lo tenga como nodo. Desactivá esto solo si querés que sea un nodo sin hijos propios, sin perder los nodos que ya tengas configurados más abajo.")}
            </p>
          </div>
        )}
      </div>

      {config?.enabled && (
      <>
      {ultimaActualizacion && (
        <p className="text-xs text-ink-3 mb-3">
          {traducir("Última actualización")}: {ultimaActualizacion.toLocaleTimeString()}
        </p>
      )}

      {loadingEstado ? (
        <LoadingState />
      ) : estadoError && !raiz ? (
        <ErrorState onRetry={loadEstado} />
      ) : raiz ? (
        <div className="card p-5 mb-8">
          <div className="flex items-baseline justify-between flex-wrap gap-2 mb-4">
            <h2 className="text-sm font-bold text-ink">{traducir("Árbol de nodos")}</h2>
            <span className="text-xs text-ink-3">
              {traducir("El nivel se calcula según qué panel estés mirando -nadie lo asigna a mano")}
            </span>
          </div>
          {/* pt-3: overflow-x-auto sin overflow-y explícito hace que el
              navegador igual recorte el eje Y (no puede quedar "visible" si
              el otro eje no lo es) -sin este margen arriba, la insignia
              "Este servidor", que sobresale del borde de su tarjeta con
              -top-2.5, quedaba cortada por ese recorte. */}
          <div className="overflow-x-auto pb-2 pt-3">
            <div className="flex justify-center min-w-max px-4">
              <ul className="tree">
                <ArbolNodo nodo={raiz} esRaiz nivel={1} ruta={[]}
                  onVerMas={(nodo, ruta) => setNodoDetalle({ nodo, ruta })} />
              </ul>
            </div>
          </div>
        </div>
      ) : null}

      {nodoDetalle && (
        <ModalDetalleNodo nodo={nodoDetalle.nodo} ruta={nodoDetalle.ruta} onClose={() => setNodoDetalle(null)} />
      )}

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-ink">{traducir("Nodos configurados")}</h2>
        <button
          onClick={() => { if (!showForm) resetForm(); setShowForm(!showForm) }}
          className="btn btn-primary"
        >
          {showForm ? traducir('Cancelar') : traducir('+ Agregar nodo')}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSave} className="card p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="node-name" className="field-label block mb-1.5">{traducir("Nombre")}</label>
              <input id="node-name" type="text" value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                className="input" placeholder={traducir("ej: Sucursal Norte")} required />
            </div>
            <div>
              <label htmlFor="node-url" className="field-label block mb-1.5">{traducir("URL del panel remoto")}</label>
              <input id="node-url" type="text" value={form.url}
                onChange={e => setForm({ ...form, url: e.target.value })}
                className="input font-mono text-sm" placeholder="https://10.0.0.5:8443" required />
            </div>
            <div>
              <label htmlFor="node-username" className="field-label block mb-1.5">{traducir("Usuario")}</label>
              <input id="node-username" type="text" value={form.username}
                onChange={e => setForm({ ...form, username: e.target.value })}
                className="input" required />
              <p className="field-help mt-1">{traducir("Recomendado: una cuenta con rol \"Solo lectura\" dedicada a esto en el nodo remoto.")}</p>
            </div>
            <div>
              <label htmlFor="node-password" className="field-label block mb-1.5">{traducir("Contraseña")}</label>
              <input id="node-password" type="password" value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                className="input" placeholder={editingId !== null ? traducir("Dejar en blanco para no cambiarla") : ''}
                required={editingId === null} />
            </div>
          </div>

          <label className="flex items-center gap-2 mt-4 cursor-pointer">
            <input type="checkbox" checked={form.enabled} onChange={e => setForm({ ...form, enabled: e.target.checked })} />
            {traducir("Habilitado")}
          </label>

          <div className="flex items-center gap-3 mt-4">
            <button type="button" onClick={handleTest} disabled={testing} className="btn btn-outline">
              {testing ? traducir("Probando...") : traducir("Probar conexión")}
            </button>
            <button type="submit" className="btn btn-primary">
              {editingId !== null ? traducir("Guardar cambios") : traducir("Agregar nodo")}
            </button>
          </div>

          {testResult && (
            <div className={`mt-4 note ${
              testResult.status !== 'ok' ? 'note-danger'
                : testResult.monitoreo_centralizado_remoto === false ? 'note-warn'
                  : 'note-ok'
            }`}>
              <p className="note-text">
                {testResult.status !== 'ok'
                  ? testResult.message
                  : testResult.monitoreo_centralizado_remoto === false
                    ? traducir("Conexión exitosa, pero el monitoreo centralizado está deshabilitado en ese nodo: va a aparecer «Sin conexión» en el árbol hasta que lo actives allá (Monitoreo centralizado → Habilitar).")
                    : traducir("Conexión exitosa: el nodo respondió correctamente.")}
              </p>
            </div>
          )}
        </form>
      )}

      {nodes.length === 0 ? (
        <p className="text-ink-3 text-sm">{traducir("No hay nodos remotos configurados todavía.")}</p>
      ) : (
        <div className="card divide-y divide-line-soft">
          {nodes.map(node => (
            <div key={node.id} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium text-ink flex items-center gap-2">
                  {node.name}
                  <span className={node.enabled ? 'pill-ok' : 'pill-mute'}>
                    {node.enabled ? traducir("Habilitado") : traducir("Deshabilitado")}
                  </span>
                </p>
                <p className="text-xs text-ink-3 font-mono">{node.url} · {node.username}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleSync(node)} disabled={syncingId === node.id}
                  className="btn-icon" title={traducir("Sincronizar configuración a este nodo")}>
                  <IconUpload className="w-4 h-4" />
                </button>
                <button onClick={() => handleEdit(node)} className="btn-icon" title={traducir("Editar")}>
                  <IconEdit className="w-4 h-4" />
                </button>
                <button onClick={() => handleDelete(node)} className="btn-icon text-rose-600" title={traducir("Eliminar")}>
                  <IconTrash className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      </>
      )}
    </div>
  )
}
