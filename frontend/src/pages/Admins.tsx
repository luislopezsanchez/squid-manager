import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api, getToken } from '../api/client'
import { useToast } from '../components/Toast'

interface AdminUser {
  id: number
  username: string
  email: string | null
  role: string
  is_active: boolean
  created_at: string
  last_login: string | null
}

export default function Admins() {
  const [admins, setAdmins] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<AdminUser | null>(null)
  const [formData, setFormData] = useState({ username: '', password: '', email: '', role: 'admin' })
  const { showToast, ToastContainer } = useToast()

  const load = () => {
    api.listAdmins().then(setAdmins).catch(e => showToast(e.message, 'error')).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleCreate = () => {
    setEditing(null)
    setFormData({ username: '', password: '', email: '', role: 'admin' })
    setShowModal(true)
  }

  const handleEdit = (admin: AdminUser) => {
    setEditing(admin)
    setFormData({ username: admin.username, password: '', email: admin.email || '', role: admin.role })
    setShowModal(true)
  }

  const handleSave = async () => {
    try {
      if (editing) {
        await api.updateAdmin(editing.id, {
          email: formData.email || null,
          role: formData.role,
        })
        showToast(traducir("Administrador actualizado"), 'success')
      } else {
        await api.createAdmin({
          username: formData.username,
          password: formData.password,
          email: formData.email || null,
          role: formData.role,
        })
        showToast(traducir("Administrador creado"), 'success')
      }
      setShowModal(false)
      load()
    } catch (e: any) {
      showToast(e.message, 'error')
    }
  }

  const handleDelete = async (admin: AdminUser) => {
    if (!confirm(`¿Eliminar el administrador "${admin.username}"?`)) return
    try {
      await api.deleteAdmin(admin.id)
      showToast(traducir("Administrador eliminado"), 'success')
      load()
    } catch (e: any) {
      showToast(e.message, 'error')
    }
  }

  const roleBadge = (role: string) => {
    const colors: Record<string, string> = {
      superadmin: 'bg-purple-100 text-purple-700',
      admin: 'pill-info',
      viewer: 'pill-mute',
    }
    const labels: Record<string, string> = {
      superadmin: 'Superadministrador',
      admin: 'Administrador',
      viewer: 'Solo lectura',
    }
    return <span className={`pill ${colors[role] || colors.admin}`}>{labels[role] || role}</span>
  }

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  return (
    <div className="p-6 md:p-7">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#0A2C48' }}>{traducir("Administradores")}</h1>
        <button onClick={handleCreate} className="px-4 py-2 text-white rounded-lg font-medium" style={{ backgroundColor: '#0B497C' }}>{traducir("+ Nuevo Admin")}</button>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 text-sm text-amber-800">
        <strong>{traducir("Información sobre roles:")}</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li><strong>{traducir("Superadministrador")}</strong>{traducir("— Gestiona otros admins, no puede ser eliminado ni degradado")}</li>
          <li><strong>{traducir("Administrador")}</strong>{traducir("— Gestiona el proxy (ACLs, reglas, usuarios, settings) pero no otros admins")}</li>
          <li><strong>{traducir("Solo lectura")}</strong>{traducir("— Solo lectura, no puede hacer cambios")}</li>
        </ul>
      </div>

      <div className="card overflow-hidden">
        <table className="table-panel">
          <thead>
            <tr>
              <th className="text-left">{traducir("Usuario")}</th>
              <th className="text-left">{traducir("Rol")}</th>
              <th className="text-left">{traducir("Email")}</th>
              <th className="text-left">{traducir("Estado")}</th>
              <th className="text-left">{traducir("Creado")}</th>
              <th className="text-left">{traducir("Último login")}</th>
              <th className="text-right">{traducir("Acciones")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {admins.map(a => (
              <tr key={a.id} className="hover:bg-brand-50">
                <td className="px-6 py-3 font-medium">{a.username}{a.id === 1 && <span className="text-xs text-ink-3 ml-2">{traducir("(principal)")}</span>}</td>
                <td className="px-6 py-3">{roleBadge(a.role)}</td>
                <td className="px-6 py-3 text-ink-2 text-xs">{a.email || '-'}</td>
                <td className="px-6 py-3">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${a.is_active ? 'pill-ok' : 'pill-danger'}`}>
                    {a.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="px-6 py-3 text-xs text-ink-3">{new Date(a.created_at).toLocaleDateString()}</td>
                <td className="px-6 py-3 text-xs text-ink-3">{a.last_login ? new Date(a.last_login).toLocaleString() : 'Nunca'}</td>
                <td className="px-6 py-3 text-right space-x-2">
                  <button onClick={() => handleEdit(a)} className="text-xs px-2 py-1 rounded text-blue-600 hover:bg-blue-50">{traducir("Editar")}</button>
                  {a.id !== 1 && (
                    <button onClick={() => handleDelete(a)} className="text-xs px-2 py-1 rounded text-danger hover:bg-red-50">{traducir("Eliminar")}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">{editing ? traducir('Editar Admin') : traducir('Nuevo Admin')}</h2>
            <div className="space-y-4">
              <div>
                <label className="field-label block mb-1.5">{traducir("Usuario")}</label>
                <input type="text" value={formData.username} disabled={!!editing}
                  onChange={e => setFormData({ ...formData, username: e.target.value })}
                  className="input disabled:bg-line-soft" />
              </div>
              {!editing && (
                <div>
                  <label className="field-label block mb-1.5">{traducir("Contraseña")}</label>
                  <input type="password" value={formData.password}
                    onChange={e => setFormData({ ...formData, password: e.target.value })}
                    className="input" />
                </div>
              )}
              <div>
                <label className="field-label block mb-1.5">{traducir("Email (opcional)")}</label>
                <input type="email" value={formData.email}
                  onChange={e => setFormData({ ...formData, email: e.target.value })}
                  className="input" />
              </div>
              <div>
                <label className="field-label block mb-1.5">{traducir("Rol")}</label>
                <select value={formData.role}
                  onChange={e => setFormData({ ...formData, role: e.target.value })}
                  className="input"
                  disabled={editing?.id === 1}>
                  <option value="admin">{traducir("Administrador — gestiona el proxy")}</option>
                  <option value="viewer">{traducir("Solo lectura — consulta sin modificar")}</option>
                  {editing?.id === 1 && <option value="superadmin">{traducir("Superadministrador")}</option>}
                </select>
                {editing?.id === 1 && <p className="text-xs text-ink-3 mt-1">{traducir("El superadmin principal no puede cambiar de rol")}</p>}
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="flex-1 px-4 py-2 border border-line rounded-lg">{traducir("Cancelar")}</button>
              <button onClick={handleSave} className="flex-1 px-4 py-2 text-white rounded-lg" style={{ backgroundColor: '#0B497C' }}>{traducir("Guardar")}</button>
            </div>
          </div>
        </div>
      )}
      <ToastContainer />
    </div>
  )
}