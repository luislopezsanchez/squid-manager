import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface Group {
  id: number
  name: string
  description: string | null
  no_bump: boolean
  members: string[]
}

export default function Groups() {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [newGroup, setNewGroup] = useState({ name: '', description: '', no_bump: false })
  const [newMember, setNewMember] = useState<Record<number, string>>({})
  const [allUsers, setAllUsers] = useState<string[]>([])
  const { showToast, ToastContainer } = useToast()

  const loadGroups = () => {
    api.listGroups().then(setGroups).catch(e => showToast(traducir("Error al cargar grupos"), 'error')).finally(() => setLoading(false))
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
      await api.createGroup({ name: newGroup.name, description: newGroup.description, no_bump: newGroup.no_bump })
      setNewGroup({ name: '', description: '', no_bump: false })
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
    <div className="p-6 md:p-7">
      <ToastContainer />
      <datalist id="member-options">
        {allUsers.map(u => <option key={u} value={u} />)}
      </datalist>
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title">{traducir("Grupos de Usuarios")}</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn btn-primary"
        >
          {showForm ? traducir('Cancelar') : traducir('+ Nuevo Grupo')}
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-xs text-blue-800">
        <strong>{traducir("Grupos: políticas por conjunto de usuarios.")}</strong> Cada grupo genera una ACL{" "}
        <code>proxy_auth</code> en Squid. Para aplicar una política, crea una <strong>{traducir("regla de acceso")}</strong>{" "}
        que referencie el nombre del grupo (ej. <code>{traducir("allow ventas")}</code>).
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="field-label block mb-1.5">{traducir("Nombre del grupo")}</label>
              <input
                type="text" value={newGroup.name}
                onChange={e => setNewGroup({ ...newGroup, name: e.target.value })}
                className="input"
                placeholder="ventas"
                required
              />
            </div>
            <div>
              <label className="field-label block mb-1.5">{traducir("Descripción")}</label>
              <input
                type="text" value={newGroup.description}
                onChange={e => setNewGroup({ ...newGroup, description: e.target.value })}
                className="input"
                placeholder={traducir("Equipo de ventas")}
              />
            </div>
          </div>

          <label className="flex items-start gap-3 mt-4 cursor-pointer">
            <input
              type="checkbox"
              checked={newGroup.no_bump}
              onChange={e => setNewGroup({ ...newGroup, no_bump: e.target.checked })}
              className="w-4 h-4 mt-0.5"
            />
            <div>
              <span className="text-sm font-medium text-ink-2">{traducir("No interceptar el HTTPS de este grupo")}</span>
              <p className="text-xs text-ink-3 mt-0.5">
                Para quien no puede instalar el certificado (móviles personales)
                o usa herramientas que se rompen al interceptarlas (git, npm,
                apps con <em>{traducir("certificate pinning")}</em>). Siguen autenticándose y
                el bloqueo por dominio les sigue afectando; lo que se pierde es
                la inspección de la URL completa y del contenido.
              </p>
            </div>
          </label>

          <button type="submit" className="mt-4 btn btn-primary">{traducir("Crear Grupo")}</button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12 text-ink-3">{traducir("Cargando...")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {groups.map(group => (
            <div key={group.id} className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-ink">{group.name}</h3>
                    {group.no_bump && (
                      <span
                        className="text-[11px] px-1.5 py-0.5 rounded bg-warn-soft text-warn font-medium"
                        title={traducir("El tráfico HTTPS de este grupo no se descifra. El bloqueo por dominio le sigue afectando.")}
                      >{traducir("HTTPS sin interceptar")}</span>
                    )}
                  </div>
                  {group.description && <p className="text-sm text-ink-3">{group.description}</p>}
                </div>
                <button onClick={() => handleDelete(group.id, group.name)}
                  className="text-danger hover:text-danger text-sm">{traducir("Eliminar")}</button>
              </div>

              <div className="flex flex-wrap gap-2 mb-4">
                {group.members.map(m => (
                  <span key={m} className="inline-flex items-center gap-1 bg-primary-50 text-primary-800 px-2 py-1 rounded-full text-xs font-medium">
                    {m}
                    <button onClick={() => handleRemoveMember(group.id, m)} className="text-primary-500 hover:text-danger">×</button>
                  </span>
                ))}
                {group.members.length === 0 && (
                  <span className="text-xs text-ink-3">{traducir("Sin miembros")}</span>
                )}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={newMember[group.id] || ''}
                  onChange={e => setNewMember(prev => ({ ...prev, [group.id]: e.target.value }))}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddMember(group.id) } }}
                  className="flex-1 px-3 py-1.5 border border-line rounded-lg text-sm"
                  placeholder={traducir("nombre de usuario (local o LDAP)")}
                  list="member-options"
                />
                <button onClick={() => handleAddMember(group.id)}
                  className="btn btn-primary btn-sm">{traducir("Añadir")}</button>
              </div>
            </div>
          ))}
          {groups.length === 0 && (
            <div className="col-span-full text-center py-12 text-ink-3">{traducir("No hay grupos. Crea el primero.")}</div>
          )}
        </div>
      )}
    </div>
  )
}
