import { traducir } from '../i18n'
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
  create: { label: traducir("Crear"), color: 'pill-ok' },
  update: { label: traducir("Actualizar"), color: 'pill-info' },
  delete: { label: traducir("Eliminar"), color: 'pill-danger' },
  toggle: { label: traducir("Toggle"), color: 'pill-warn' },
  login: { label: traducir("Inicio de sesión"), color: 'pill-ok' },
  login_failed: { label: traducir("Inicio fallido"), color: 'pill-danger' },
  reset_password: { label: traducir("Restablecer contraseña"), color: 'pill-warn' },
  add_member: { label: traducir("Añadir miembro"), color: 'pill-ok' },
  remove_member: { label: traducir("Quitar miembro"), color: 'pill-danger' },
  reorder: { label: traducir("Reordenar"), color: 'pill-info' },
  import: { label: traducir("Importar"), color: 'bg-purple-100 text-purple-800' },
  restore: { label: traducir("Restaurar"), color: 'bg-purple-100 text-purple-800' },
}

const ENTITY_LABELS: Record<string, string> = {
  proxy_user: 'Usuario del Proxy',
  acl: 'ACL',
  access_rule: 'Regla de Acceso',
  delay_pool: 'Delay Pool',
  admin: 'Administrador',
  ldap_user: 'Usuario LDAP',
  user_group: 'Grupo',
  syslog_config: 'Syslog externo',
  backup: 'Backup',
  squid_conf: 'Configuración de Squid',
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
    }).catch(e => showToast(traducir("Error al cargar auditoría"), 'error')).finally(() => setLoading(false))

    api.auditStats().then(setStats).catch(console.error)
  }

  useEffect(() => { loadAudit() }, [filterEntity, filterAction])

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Auditoría")}</h1>
      <p className="text-sm text-ink-3 mb-6">{traducir("Registro de todos los cambios realizados en el sistema")}</p>

      {/* Stats */}
      {stats && (() => {
        const byAction: Record<string, number> = stats.by_action || {}
        const loginFailed = byAction.login_failed || 0
        const deletes = byAction.delete || 0
        const configChanges = Object.entries(byAction)
          .filter(([action]) => action !== 'login' && action !== 'login_failed')
          .reduce((sum, [, count]) => sum + count, 0)
        return (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="card p-4 border border-line-soft">
              <p className="text-sm text-ink-3">{traducir("Total eventos")}</p>
              <p className="page-title">{stats.total}</p>
            </div>
            <div className="card p-4 border border-line-soft">
              <p className="text-sm text-ink-3">{traducir("Inicios de sesión fallidos")}</p>
              <p className={`page-title ${loginFailed > 0 ? 'text-danger' : ''}`}>{loginFailed}</p>
            </div>
            <div className="card p-4 border border-line-soft">
              <p className="text-sm text-ink-3">{traducir("Cambios de configuración")}</p>
              <p className="page-title">{configChanges}</p>
            </div>
            <div className="card p-4 border border-line-soft">
              <p className="text-sm text-ink-3">{traducir("Eliminaciones")}</p>
              <p className="page-title">{deletes}</p>
            </div>
          </div>
        )
      })()}

      {/* Filtros */}
      <div className="flex gap-4 mb-6">
        <select value={filterEntity} onChange={e => setFilterEntity(e.target.value)}
          className="px-4 py-2 border border-line rounded-lg bg-white text-sm">
          <option value="">{traducir("Todas las entidades")}</option>
          <option value="proxy_user">{traducir("Usuarios del Proxy")}</option>
          <option value="ldap_user">{traducir("Usuarios LDAP")}</option>
          <option value="user_group">{traducir("Grupos")}</option>
          <option value="acl">{traducir("ACLs")}</option>
          <option value="access_rule">{traducir("Reglas de Acceso")}</option>
          <option value="delay_pool">{traducir("Delay Pools")}</option>
          <option value="admin">{traducir("Administradores")}</option>
          <option value="syslog_config">{traducir("Syslog externo")}</option>
          <option value="backup">{traducir("Backup")}</option>
          <option value="squid_conf">{traducir("Configuración de Squid")}</option>
        </select>
        <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
          className="px-4 py-2 border border-line rounded-lg bg-white text-sm">
          <option value="">{traducir("Todas las acciones")}</option>
          <option value="create">{traducir("Crear")}</option>
          <option value="update">{traducir("Actualizar")}</option>
          <option value="delete">{traducir("Eliminar")}</option>
          <option value="toggle">{traducir("Toggle")}</option>
          <option value="login">{traducir("Inicio de sesión")}</option>
          <option value="login_failed">{traducir("Inicio fallido")}</option>
          <option value="reset_password">{traducir("Restablecer contraseña")}</option>
          <option value="add_member">{traducir("Añadir miembro")}</option>
          <option value="remove_member">{traducir("Quitar miembro")}</option>
          <option value="reorder">{traducir("Reordenar")}</option>
          <option value="import">{traducir("Importar")}</option>
          <option value="restore">{traducir("Restaurar")}</option>
        </select>
      </div>

      {/* Tabla */}
      {loading ? (
        <div className="text-center py-12 text-ink-3">{traducir("Cargando...")}</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">{traducir("Fecha")}</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">{traducir("Admin")}</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">{traducir("Acción")}</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">{traducir("Entidad")}</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-ink-3 uppercase">{traducir("Detalle")}</th>
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
                <tr><td colSpan={5} className="px-4 py-12 text-center text-ink-3">{traducir("No hay registros de auditoría")}</td></tr>
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