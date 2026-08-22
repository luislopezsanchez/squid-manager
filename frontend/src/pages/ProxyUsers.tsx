import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface ProxyUser {
  id: number
  username: string
  enabled: boolean
  expires_at: string | null
  created_at: string
  updated_at: string
}

export default function ProxyUsers() {
  const [users, setUsers] = useState<ProxyUser[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [purging, setPurging] = useState(false)
  const { showToast, ToastContainer } = useToast()

  const loadUsers = () => {
    api.listUsers().then(setUsers).catch(e => showToast('Error al cargar usuarios', 'error')).finally(() => setLoading(false))
  }

  useEffect(() => { loadUsers() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api.createUser({ username: newUser.username, password: newUser.password, enabled: true })
      setNewUser({ username: '', password: '' })
      setShowForm(false)
      loadUsers()
      showToast(`Usuario "${newUser.username}" creado correctamente`)
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    }
  }

  const handleToggle = async (id: number) => {
    try {
      const result = await api.toggleUser(id)
      loadUsers()
      showToast(`Usuario "${result.username}" ${result.enabled ? 'activado' : 'desactivado'}`)
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar este usuario?')) return
    try {
      await api.deleteUser(id)
      loadUsers()
      showToast('Usuario eliminado correctamente')
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const handlePurge = async () => {
    if (!confirm('¿Forzar re-autenticación de TODOS los usuarios?\n\nEsta acción purga la caché de credenciales de Squid y todos los usuarios deberán volver a introducir su contraseña.')) return
    setPurging(true)
    try {
      const result = await api.purgeCredentials()
      showToast(result.message, result.status === 'ok' ? 'success' : 'error')
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setPurging(false)
    }
  }

  return (
    <div className="p-8">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Usuarios del Proxy</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={handlePurge}
            disabled={purging}
            className="px-4 py-2 rounded-lg font-medium border border-red-200 text-red-700 hover:bg-red-50 transition disabled:opacity-50"
            title="Purga la caché de credenciales de Squid: todos los usuarios deberán volver a autenticarse"
          >
            {purging ? 'Purgando...' : '🛑 Forzar re-autenticación'}
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 transition"
          >
            {showForm ? 'Cancelar' : '+ Nuevo Usuario'}
          </button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-xs text-blue-800">
        <strong>💡 Dos acciones distintas:</strong>{" "}
        <strong>Bloquear acceso</strong> (deshabilita al usuario, no puede navegar) es diferente de{" "}
        <strong>Forzar re-autenticación</strong> (purga la caché de credenciales, pide contraseña de nuevo a todos).
        La sesión de un usuario vive <strong>{`${2} horas`}</strong> por defecto (configurable en <em>credentialsttl</em>).
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-xl shadow-sm p-6 mb-6 border border-gray-100">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
              <input
                type="text" value={newUser.username}
                onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
              <input
                type="password" value={newUser.password}
                onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>
          </div>
          {error && <div className="mt-4 bg-red-50 text-red-600 text-sm p-3 rounded-lg">{error}</div>}
          <button type="submit" className="mt-4 bg-primary-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-primary-700">
            Crear Usuario
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Cargando...</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Usuario</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Creado</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map(user => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">{user.username}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                      user.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {user.enabled ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(user.created_at).toLocaleDateString('es-ES')}
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button onClick={() => handleToggle(user.id)}
                      className="text-primary-600 hover:text-primary-800 text-sm font-medium"
                      title={user.enabled ? 'Bloquea su acceso a internet hasta que lo habilites' : 'Permite que navegue a través del proxy'}>
                      {user.enabled ? '🚫 Bloquear acceso' : '✅ Habilitar acceso'}
                    </button>
                    <button onClick={() => handleDelete(user.id)}
                      className="text-red-600 hover:text-red-800 text-sm font-medium">
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={4} className="px-6 py-12 text-center text-gray-500">No hay usuarios. Crea el primero.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}