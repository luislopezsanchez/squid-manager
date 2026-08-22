import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface AuditEntry {
  id: number
  admin_id: number | null
  admin_username: string | null
  action: string
  entity: string
  entity_id: number | null
  old_value: string | null
  new_value: string | null
  timestamp: string | null
}

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  create: { label: 'Crear', color: 'bg-green-100 text-green-800' },
  update: { label: 'Actualizar', color: 'bg-blue-100 text-blue-800' },
  delete: { label: 'Eliminar', color: 'bg-red-100 text-red-800' },
  toggle: { label: 'Toggle', color: 'bg-yellow-100 text-yellow-800' },
  apply: { label: 'Aplicar', color: 'bg-purple-100 text-purple-800' },
}

const ENTITY_LABELS: Record<string, string> = {
  proxy_user: 'Usuario del Proxy',
  acl: 'ACL',
  access_rule: 'Regla de Acceso',
  delay_pool: 'Delay Pool',
  squid_setting: 'Configuración',
}

export default function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [filterEntity, setFilterEntity] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [total, setTotal] = useState(0)
  const { showToast, ToastContainer } = useToast()

  const loadAudit = () => {
    let url = `/audit/?limit=100`
    if (filterEntity) url += `&entity=${filterEntity}`
    if (filterAction) url += `&action=${filterAction}`
    api.request(url).then((data: any) => {
      setEntries(data.entries)
      setTotal(data.total)
    }).catch(e => showToast('Error al cargar auditoría', 'error')).finally(() => setLoading(false))

    api.auditStats().then(setStats).catch(console.error)
  }

  useEffect(() => { loadAudit() }, [filterEntity, filterAction])

  return (
    <div className="p-8">
      <ToastContainer />
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Auditoría</h1>
      <p className="text-sm text-gray-500 mb-6">Registro de todos los cambios realizados en el sistema</p>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <p className="text-sm text-gray-500">Total cambios</p>
            <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
          </div>
          {Object.entries(stats.by_entity || {}).slice(0, 3).map(([entity, count]: any) => (
            <div key={entity} className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
              <p className="text-sm text-gray-500">{ENTITY_LABELS[entity] || entity}</p>
              <p className="text-2xl font-bold text-gray-900">{count}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filtros */}
      <div className="flex gap-4 mb-6">
        <select value={filterEntity} onChange={e => setFilterEntity(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm">
          <option value="">Todas las entidades</option>
          <option value="proxy_user">Usuarios del Proxy</option>
          <option value="acl">ACLs</option>
          <option value="access_rule">Reglas de Acceso</option>
          <option value="delay_pool">Delay Pools</option>
        </select>
        <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm">
          <option value="">Todas las acciones</option>
          <option value="create">Crear</option>
          <option value="update">Actualizar</option>
          <option value="delete">Eliminar</option>
          <option value="toggle">Toggle</option>
        </select>
      </div>

      {/* Tabla */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Cargando...</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Fecha</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Admin</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Acción</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Entidad</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map(entry => {
                const actionInfo = ACTION_LABELS[entry.action] || { label: entry.action, color: 'bg-gray-100 text-gray-800' }
                return (
                  <tr key={entry.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' }) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{entry.admin_username || 'sistema'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${actionInfo.color}`}>
                        {actionInfo.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{ENTITY_LABELS[entry.entity] || entry.entity}</td>
                    <td className="px-4 py-3 text-sm text-gray-500 font-mono">
                      {entry.new_value || entry.old_value || '-'}
                    </td>
                  </tr>
                )
              })}
              {entries.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-12 text-center text-gray-500">No hay registros de auditoría</td></tr>
              )}
            </tbody>
          </table>
          {total > 100 && (
            <div className="p-4 text-center text-sm text-gray-500 border-t border-gray-100">
              Mostrando 100 de {total} registros
            </div>
          )}
        </div>
      )}
    </div>
  )
}