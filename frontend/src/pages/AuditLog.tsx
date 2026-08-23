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
  create: { label: 'Crear', color: 'pill-ok' },
  update: { label: 'Actualizar', color: 'pill-info' },
  delete: { label: 'Eliminar', color: 'pill-danger' },
  toggle: { label: 'Toggle', color: 'pill-warn' },
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
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">Auditoría</h1>
      <p className="text-sm text-ink-3 mb-6">Registro de todos los cambios realizados en el sistema</p>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="card p-4 border border-line-soft">
            <p className="text-sm text-ink-3">Total cambios</p>
            <p className="page-title">{stats.total}</p>
          </div>
          {Object.entries(stats.by_entity || {}).slice(0, 3).map(([entity, count]: any) => (
            <div key={entity} className="card p-4 border border-line-soft">
              <p className="text-sm text-ink-3">{ENTITY_LABELS[entity] || entity}</p>
              <p className="page-title">{count}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filtros */}
      <div className="flex gap-4 mb-6">
        <select value={filterEntity} onChange={e => setFilterEntity(e.target.value)}
          className="px-4 py-2 border border-line rounded-lg bg-white text-sm">
          <option value="">Todas las entidades</option>
          <option value="proxy_user">Usuarios del Proxy</option>
          <option value="acl">ACLs</option>
          <option value="access_rule">Reglas de Acceso</option>
          <option value="delay_pool">Delay Pools</option>
        </select>
        <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
          className="px-4 py-2 border border-line rounded-lg bg-white text-sm">
          <option value="">Todas las acciones</option>
          <option value="create">Crear</option>
          <option value="update">Actualizar</option>
          <option value="delete">Eliminar</option>
          <option value="toggle">Toggle</option>
        </select>
      </div>

      {/* Tabla */}
      {loading ? (
        <div className="text-center py-12 text-ink-3">Cargando...</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">Fecha</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">Admin</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">Acción</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">Entidad</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {entries.map(entry => {
                const actionInfo = ACTION_LABELS[entry.action] || { label: entry.action, color: 'bg-line-soft text-ink' }
                return (
                  <tr key={entry.id} className="hover:bg-brand-50">
                    <td className="px-4 py-3 text-sm text-ink-3 whitespace-nowrap">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' }) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-ink">{entry.admin_username || 'sistema'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${actionInfo.color}`}>
                        {actionInfo.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-ink-2">{ENTITY_LABELS[entry.entity] || entry.entity}</td>
                    <td className="px-4 py-3 text-sm text-ink-3 font-mono">
                      {entry.new_value || entry.old_value || '-'}
                    </td>
                  </tr>
                )
              })}
              {entries.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-12 text-center text-ink-3">No hay registros de auditoría</td></tr>
              )}
            </tbody>
          </table>
          {total > 100 && (
            <div className="p-4 text-center text-sm text-ink-3 border-t border-line-soft">
              Mostrando 100 de {total} registros
            </div>
          )}
        </div>
      )}
    </div>
  )
}