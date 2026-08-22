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
        showToast('Administrador actualizado', 'success')
      } else {
        await api.createAdmin({
          username: formData.username,
          password: formData.password,
          email: formData.email || null,
          role: formData.role,
        })
        showToast('Administrador creado', 'success')
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
      showToast('Administrador eliminado', 'success')
      load()
    } catch (e: any) {
      showToast(e.message, 'error')
    }
  }

  const roleBadge = (role: string) => {
    const colors: Record<string, string> = {
      superadmin: 'bg-purple-100 text-purple-700',
      admin: 'bg-blue-100 text-blue-700',
      viewer: 'bg-gray-100 text-gray-600',
    }
    const labels: Record<string, string> = {
      superadmin: '👑 Super Admin',
      admin: '🛡️ Admin',
      viewer: '👁️ Viewer',
    }
    return <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${colors[role] || colors.admin}`}>{labels[role] || role}</span>
  }

  if (loading) return <div className="p-8 text-center text-gray-500">Cargando...</div>

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#083151' }}>Administradores</h1>
        <button onClick={handleCreate} className="px-4 py-2 text-white rounded-lg font-medium" style={{ backgroundColor: '#0b497c' }}>
          + Nuevo Admin
        </button>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 text-sm text-amber-800">
        <strong>Información sobre roles:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>👑 <strong>Super Admin</strong> — Gestiona otros admins, no puede ser eliminado ni degradado</li>
          <li>🛡️ <strong>Admin</strong> — Gestiona el proxy (ACLs, reglas, usuarios, settings) pero no otros admins</li>
          <li>👁️ <strong>Viewer</strong> — Solo lectura, no puede hacer cambios</li>
        </ul>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Usuario</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Rol</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Email</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Estado</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Creado</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Último login</th>
              <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {admins.map(a => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-6 py-3 font-medium">{a.username}{a.id === 1 && <span className="text-xs text-gray-400 ml-2">(principal)</span>}</td>
                <td className="px-6 py-3">{roleBadge(a.role)}</td>
                <td className="px-6 py-3 text-gray-600 text-xs">{a.email || '-'}</td>
                <td className="px-6 py-3">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${a.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {a.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="px-6 py-3 text-xs text-gray-500">{new Date(a.created_at).toLocaleDateString()}</td>
                <td className="px-6 py-3 text-xs text-gray-500">{a.last_login ? new Date(a.last_login).toLocaleString() : 'Nunca'}</td>
                <td className="px-6 py-3 text-right space-x-2">
                  <button onClick={() => handleEdit(a)} className="text-xs px-2 py-1 rounded text-blue-600 hover:bg-blue-50">Editar</button>
                  {a.id !== 1 && (
                    <button onClick={() => handleDelete(a)} className="text-xs px-2 py-1 rounded text-red-600 hover:bg-red-50">Eliminar</button>
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
            <h2 className="text-xl font-bold mb-4">{editing ? 'Editar Admin' : 'Nuevo Admin'}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
                <input type="text" value={formData.username} disabled={!!editing}
                  onChange={e => setFormData({ ...formData, username: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg disabled:bg-gray-100" />
              </div>
              {!editing && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
                  <input type="password" value={formData.password}
                    onChange={e => setFormData({ ...formData, password: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email (opcional)</label>
                <input type="email" value={formData.email}
                  onChange={e => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
                <select value={formData.role}
                  onChange={e => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  disabled={editing?.id === 1}>
                  <option value="admin">🛡️ Admin — Gestiona el proxy</option>
                  <option value="viewer">👁️ Viewer — Solo lectura</option>
                  {editing?.id === 1 && <option value="superadmin">👑 Super Admin</option>}
                </select>
                {editing?.id === 1 && <p className="text-xs text-gray-400 mt-1">El superadmin principal no puede cambiar de rol</p>}
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowModal(false)} className="flex-1 px-4 py-2 border border-gray-300 rounded-lg">Cancelar</button>
              <button onClick={handleSave} className="flex-1 px-4 py-2 text-white rounded-lg" style={{ backgroundColor: '#0b497c' }}>Guardar</button>
            </div>
          </div>
        </div>
      )}
      <ToastContainer />
    </div>
  )
}