import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { formatRate, formatNumber } from '../utils/format'
import { IconRefresh, IconEdit, IconTrash, IconGlobe, IconUpload } from '../components/Icons'

interface Node {
  id: number
  name: string
  url: string
  username: string
  password: string
  enabled: boolean
}

interface NodeStatus {
  id: number | null
  name: string
  url: string | null
  status: 'ok' | 'error'
  message?: string
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

const FORM_VACIO = { name: '', url: '', username: '', password: '', enabled: true }

export default function PanelCentral() {
  const [nodes, setNodes] = useState<Node[]>([])
  const [estado, setEstado] = useState<NodeStatus[]>([])
  const [loadingEstado, setLoadingEstado] = useState(true)
  const [ultimaActualizacion, setUltimaActualizacion] = useState<Date | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState(FORM_VACIO)
  const [testing, setTesting] = useState(false)
  const [syncingId, setSyncingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ status: string; message?: string } | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { showToast, ToastContainer } = useToast()

  const loadNodes = () => {
    api.listCentralNodes().then(setNodes).catch(() => showToast(traducir("Error al cargar los nodos"), 'error'))
  }

  const loadEstado = () => {
    api.getCentralDashboard()
      .then(r => { setEstado(r.nodes); setUltimaActualizacion(new Date()) })
      .catch(() => showToast(traducir("Error al consultar el estado de los nodos"), 'error'))
      .finally(() => setLoadingEstado(false))
  }

  useEffect(() => {
    loadNodes()
    loadEstado()
    // Cada nodo implica un login + un dashboard completo contra otra
    // instancia -no tiene sentido repetirlo cada pocos segundos como el
    // dashboard local, que solo lee de su propio proceso.
    intervalRef.current = setInterval(loadEstado, 30000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [])

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
      const resultado = await api.testCentralNode({ url: form.url, username: form.username, password })
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
        <button onClick={loadEstado} className="btn btn-outline flex items-center gap-2">
          <IconRefresh className="w-4 h-4" />
          {traducir("Actualizar")}
        </button>
      </div>

      <div className="note note-info mb-6">
        <p className="note-text">
          {traducir("Cada nodo se consulta con una cuenta propia del panel remoto (recomendado: un usuario con rol \"solo lectura\" dedicado a esto). No requiere ningún cambio en Squid ni que los nodos se conozcan entre sí.")}
        </p>
      </div>

      {ultimaActualizacion && (
        <p className="text-xs text-ink-3 mb-3">
          {traducir("Última actualización")}: {ultimaActualizacion.toLocaleTimeString()}
        </p>
      )}

      {loadingEstado ? (
        <div className="text-center py-12 text-ink-3">{traducir("Cargando...")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {estado.map((n, i) => (
            <div key={n.id ?? `local-${i}`} className="card p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-ink flex items-center gap-2">
                  <IconGlobe className="w-4 h-4 text-ink-3" />
                  {n.name}
                </h3>
                <span className={n.status === 'ok' ? 'pill-ok' : 'pill-danger'}>
                  {n.status === 'ok' ? traducir("En línea") : traducir("Sin conexión")}
                </span>
              </div>
              {n.url && <p className="text-xs text-ink-3 font-mono mb-3 truncate">{n.url}</p>}
              {n.status === 'ok' && n.data ? (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-ink-3 text-xs">{traducir("Tráfico actual")}</p>
                    <p className="font-medium">{formatRate(n.data.traffic.total_bytes_per_second)}</p>
                  </div>
                  <div>
                    <p className="text-ink-3 text-xs">{traducir("Usuarios activos")}</p>
                    <p className="font-medium">{formatNumber(n.data.traffic.active_users.length)}</p>
                  </div>
                  <div>
                    <p className="text-ink-3 text-xs">CPU</p>
                    <p className="font-medium">{n.data.system.cpu.percent.toFixed(0)}%</p>
                  </div>
                  <div>
                    <p className="text-ink-3 text-xs">{traducir("Memoria")}</p>
                    <p className="font-medium">{n.data.system.memory.percent.toFixed(0)}%</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-rose-700">{n.message}</p>
              )}
            </div>
          ))}
        </div>
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
            <div className={`mt-4 note ${testResult.status === 'ok' ? 'note-ok' : 'note-danger'}`}>
              <p className="note-text">
                {testResult.status === 'ok'
                  ? traducir("Conexión exitosa: el nodo respondió correctamente.")
                  : testResult.message}
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
    </div>
  )
}
