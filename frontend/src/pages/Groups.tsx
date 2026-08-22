import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface Group {
  id: number
  name: string
  description: string | null
  members: string[]
}

export default function Groups() {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [newGroup, setNewGroup] = useState({ name: '', description: '' })
  const [newMember, setNewMember] = useState<Record<number, string>>({})
  const [allUsers, setAllUsers] = useState<string[]>([])
  const { showToast, ToastContainer } = useToast()

  const loadGroups = () => {
    api.listGroups().then(setGroups).catch(e => showToast('Error al cargar grupos', 'error')).finally(() => setLoading(false))
  }

  useEffect(() => {
    loadGroups()
    // Combinar usuarios locales + LDAP para autocompletar
    Promise.all([
      api.listUsers().then(us => us.map((u: any) => u.username)).catch(() => []),
      api.listLdapUsers().then(us => us.map((u: any) => u.username)).catch(() => []),
    ]).then(([local, ldap]) => setAllUsers([...new Set([...local, ...ldap])]))
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createGroup({ name: newGroup.name, description: newGroup.description })
      setNewGroup({ name: '', description: '' })
      setShowForm(false)
      loadGroups()
      showToast(`Grupo "${newGroup.name}" creado`)
    } catch (err: any) { showToast(`Error: ${err.message}`, 'error') }
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Eliminar el grupo "${name}"?`)) return
    try {
      await api.deleteGroup(id)
      loadGroups()
      showToast(`Grupo "${name}" eliminado`)
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const handleAddMember = async (groupId: number) => {
    const username = (newMember[groupId] || '').trim()
    if (!username) return
    try {
      await api.addGroupMember(groupId, username)
      setNewMember(prev => ({ ...prev, [groupId]: '' }))
      loadGroups()
      showToast(`Usuario "${username}" añadido al grupo`)
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const handleRemoveMember = async (groupId: number, username: string) => {
    try {
      await api.removeGroupMember(groupId, username)
      loadGroups()
      showToast(`Usuario "${username}" eliminado del grupo`)
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  return (
    <div className="p-8">
      <ToastContainer />
      <datalist id="member-options">
        {allUsers.map(u => <option key={u} value={u} />)}
      </datalist>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Grupos de Usuarios</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 transition"
        >
          {showForm ? 'Cancelar' : '+ Nuevo Grupo'}
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-xs text-blue-800">
        <strong>💡 Grupos = políticas por conjunto de usuarios.</strong> Cada grupo genera una ACL{" "}
        <code>proxy_auth</code> en Squid. Para aplicar una política, crea una <strong>regla de acceso</strong>{" "}
        que referencie el nombre del grupo (ej. <code>allow ventas</code>).
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-xl shadow-sm p-6 mb-6 border border-gray-100">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nombre del grupo</label>
              <input
                type="text" value={newGroup.name}
                onChange={e => setNewGroup({ ...newGroup, name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                placeholder="ventas"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
              <input
                type="text" value={newGroup.description}
                onChange={e => setNewGroup({ ...newGroup, description: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                placeholder="Equipo de ventas"
              />
            </div>
          </div>
          <button type="submit" className="mt-4 bg-primary-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-primary-700">
            Crear Grupo
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Cargando...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {groups.map(group => (
            <div key={group.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-gray-900">{group.name}</h3>
                  {group.description && <p className="text-sm text-gray-500">{group.description}</p>}
                </div>
                <button onClick={() => handleDelete(group.id, group.name)}
                  className="text-red-600 hover:text-red-800 text-sm">Eliminar</button>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                {group.members.map(m => (
                  <span key={m} className="inline-flex items-center gap-1 bg-primary-50 text-primary-800 px-2 py-1 rounded-full text-xs font-medium">
                    {m}
                    <button onClick={() => handleRemoveMember(group.id, m)} className="text-primary-500 hover:text-red-600">×</button>
                  </span>
                ))}
                {group.members.length === 0 && (
                  <span className="text-xs text-gray-400">Sin miembros</span>
                )}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={newMember[group.id] || ''}
                  onChange={e => setNewMember(prev => ({ ...prev, [group.id]: e.target.value }))}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddMember(group.id) } }}
                  className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                  placeholder="nombre de usuario (local o LDAP)"
                  list="member-options"
                />
                <button onClick={() => handleAddMember(group.id)}
                  className="bg-primary-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-primary-700">
                  Añadir
                </button>
              </div>
            </div>
          ))}
          {groups.length === 0 && (
            <div className="col-span-full text-center py-12 text-gray-500">No hay grupos. Crea el primero.</div>
          )}
        </div>
      )}
    </div>
  )
}
