import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import RequiereAplicar from '../components/RequiereAplicar'
import { normalizarNombreAcl } from '../utils/aclNames'

interface Group {
  id: number
  name: string
  description: string | null
  no_bump: boolean
  source: 'local' | 'ldap'
  ldap_group_name: string | null
  ldap_group_nested: boolean
  members: string[]
}

export default function Groups() {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [newGroup, setNewGroup] = useState({
    name: '', description: '', no_bump: false,
    source: 'local' as 'local' | 'ldap', ldap_group_name: '', ldap_group_nested: false,
  })
  const [newMember, setNewMember] = useState<Record<number, string>>({})
  const [allUsers, setAllUsers] = useState<string[]>([])
  const [ldapEnabled, setLdapEnabled] = useState(false)
  const [ldapGroups, setLdapGroups] = useState<string[]>([])
  const [ldapNombreManual, setLdapNombreManual] = useState(false)
  const { showToast, ToastContainer } = useToast()

  const loadGroups = () => {
    api.listGroups().then(r => { setGroups(r); setLoadError(false) })
      .catch(e => { showToast(traducir("Error al cargar grupos"), 'error'); setLoadError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadGroups()
    // Combinar usuarios locales + LDAP para autocompletar
    Promise.all([
      api.listUsers().then(us => us.map((u: any) => u.username)).catch(() => []),
      api.listLdapUsers().then(us => us.map((u: any) => u.username)).catch(() => []),
    ]).then(([local, ldap]) => setAllUsers([...new Set([...local, ...ldap])]))
    api.getLdapConfig().then(c => {
      setLdapEnabled(!!c.enabled)
      // Solo tiene sentido pedir grupos si LDAP está habilitado -si no, el
      // backend responde 400 igual que con cualquier otra búsqueda al directorio.
      if (c.enabled) api.listLdapGroups().then(r => setLdapGroups(r.groups)).catch(() => {})
    }).catch(() => {})
  }, [])

  const resetForm = () => {
    setNewGroup({
      name: '', description: '', no_bump: false, source: 'local', ldap_group_name: '', ldap_group_nested: false,
    })
    setLdapNombreManual(false)
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createGroup({
        name: newGroup.name, description: newGroup.description, no_bump: newGroup.no_bump,
        source: newGroup.source,
        ldap_group_name: newGroup.source === 'ldap' ? newGroup.ldap_group_name : undefined,
        ldap_group_nested: newGroup.source === 'ldap' ? newGroup.ldap_group_nested : undefined,
      })
      notificarCambioPendiente()
      resetForm()
      setShowForm(false)
      loadGroups()
      showToast(`Grupo "${newGroup.name}" creado`)
    } catch (err: any) { showToast(`Error: ${err.message}`, 'error') }
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Eliminar el grupo "${name}"?`)) return
    try {
      await api.deleteGroup(id)
      notificarCambioPendiente()
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
      <datalist id="ldap-group-options">
        {ldapGroups.map(g => <option key={g} value={g} />)}
      </datalist>
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title">{traducir("Grupos de Usuarios")}</h1>
        <button
          onClick={() => { if (!showForm) resetForm(); setShowForm(!showForm) }}
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
          <div className="field">
            <label className="field-label block mb-1.5">{traducir("Tipo de grupo")}</label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button type="button" onClick={() => setNewGroup({ ...newGroup, source: 'local' })}
                className={`text-left p-3 rounded-lg border-2 transition ${
                  newGroup.source === 'local' ? 'border-primary-500 bg-primary-50' : 'border-line hover:border-line'
                }`}>
                <p className="font-medium text-sm text-ink">{traducir("Local")}</p>
                <p className="text-xs text-ink-3 mt-1">{traducir("Elegís vos quién es miembro, uno por uno.")}</p>
              </button>
              <button type="button" disabled={!ldapEnabled}
                onClick={() => setNewGroup({ ...newGroup, source: 'ldap' })}
                className={`text-left p-3 rounded-lg border-2 transition disabled:opacity-50 disabled:cursor-not-allowed ${
                  newGroup.source === 'ldap' ? 'border-primary-500 bg-primary-50' : 'border-line hover:border-line'
                }`}>
                <p className="font-medium text-sm text-ink">{traducir("Grupo de LDAP / Active Directory")}</p>
                <p className="text-xs text-ink-3 mt-1">
                  {ldapEnabled
                    ? traducir("La pertenencia se consulta en vivo en el directorio, sin sincronizar nada.")
                    : traducir("Activá LDAP en Integraciones → LDAP para usar esta opción.")}
                </p>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <label htmlFor="group-name" className="field-label block mb-1.5">{traducir("Nombre del grupo")}</label>
              <input
                id="group-name"
                type="text" value={newGroup.name}
                onChange={e => setNewGroup({ ...newGroup, name: normalizarNombreAcl(e.target.value) })}
                className="input font-mono text-sm"
                placeholder="ventas"
                required
              />
              <p className="field-help mt-1">{traducir("El nombre que vas a usar en las reglas de acceso -no tiene que coincidir con el nombre del grupo en el directorio. Se ajusta solo a minúsculas y guiones bajos, sin espacios ni acentos.")}</p>
            </div>
            <div>
              <label htmlFor="group-description" className="field-label block mb-1.5">{traducir("Descripción")}</label>
              <input
                id="group-description"
                type="text" value={newGroup.description}
                onChange={e => setNewGroup({ ...newGroup, description: e.target.value })}
                className="input"
                placeholder={traducir("Equipo de ventas")}
              />
            </div>
          </div>

          {newGroup.source === 'ldap' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 bg-brand-50 rounded-lg p-4 border border-line-soft">
              <div>
                <label htmlFor="group-ldap-name" className="field-label block mb-1.5">{traducir("Nombre del grupo en el directorio")}</label>
                {ldapGroups.length > 0 && !ldapNombreManual ? (
                  <>
                    <select
                      id="group-ldap-name"
                      className="input font-mono text-sm"
                      value={newGroup.ldap_group_name}
                      onChange={e => setNewGroup({ ...newGroup, ldap_group_name: e.target.value })}
                      required
                    >
                      <option value="">{traducir("-- Elegir un grupo encontrado en el directorio --")}</option>
                      {ldapGroups.map(g => <option key={g} value={g}>{g}</option>)}
                    </select>
                    <button type="button" onClick={() => setLdapNombreManual(true)}
                      className="text-xs text-primary-600 hover:underline mt-1">
                      {traducir("¿No está en la lista? Escribilo a mano")}
                    </button>
                  </>
                ) : (
                  <>
                    <input
                      id="group-ldap-name"
                      type="text" value={newGroup.ldap_group_name}
                      onChange={e => setNewGroup({ ...newGroup, ldap_group_name: e.target.value })}
                      className="input font-mono text-sm"
                      placeholder={traducir("ej: Ventas, Domain Admins")}
                      list="ldap-group-options"
                      required
                    />
                    {ldapGroups.length > 0 && (
                      <button type="button" onClick={() => setLdapNombreManual(false)}
                        className="text-xs text-primary-600 hover:underline mt-1">
                        {traducir("Volver a la lista del directorio")}
                      </button>
                    )}
                  </>
                )}
                <p className="field-help mt-1">
                  {traducir("El cn o sAMAccountName exacto del grupo en Active Directory/LDAP.")}
                </p>
              </div>
              <div className="flex items-start pt-6">
                <label className="flex items-start gap-2 cursor-pointer">
                  <input type="checkbox" checked={newGroup.ldap_group_nested}
                    onChange={e => setNewGroup({ ...newGroup, ldap_group_nested: e.target.checked })}
                    className="w-4 h-4 mt-0.5" />
                  <span className="text-sm text-ink-2">
                    {traducir("Incluir subgrupos anidados")}
                    <span className="block text-xs text-ink-3">{traducir("Solo Active Directory -en otros directorios LDAP, dejá esto sin marcar.")}</span>
                  </span>
                </label>
              </div>
            </div>
          )}

          <label className={`flex items-start gap-3 mt-4 ${newGroup.source === 'ldap' ? 'opacity-50' : 'cursor-pointer'}`}>
            <input
              type="checkbox"
              checked={newGroup.no_bump}
              disabled={newGroup.source === 'ldap'}
              onChange={e => setNewGroup({ ...newGroup, no_bump: e.target.checked })}
              className="w-4 h-4 mt-0.5"
            />
            <div>
              <span className="text-sm font-medium text-ink-2">{traducir("No interceptar el HTTPS de este grupo")}</span>
              <p className="text-xs text-ink-3 mt-0.5">
                {newGroup.source === 'ldap'
                  ? traducir("Todavía no disponible para grupos de LDAP.")
                  : <>Para quien no puede instalar el certificado (móviles personales)
                    o usa herramientas que se rompen al interceptarlas (git, npm,
                    apps con <em>{traducir("certificate pinning")}</em>). Siguen autenticándose y
                    el bloqueo por dominio les sigue afectando; lo que se pierde es
                    la inspección de la URL completa y del contenido.</>}
              </p>
            </div>
          </label>

          <div className="mt-4 flex items-center gap-3">
            <button type="submit" className="btn btn-primary">{traducir("Crear Grupo")}</button>
            <RequiereAplicar />
          </div>
        </form>
      )}

      {loading ? (
        <LoadingState />
      ) : loadError && groups.length === 0 ? (
        <ErrorState onRetry={loadGroups} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {groups.map(group => (
            <div key={group.id} className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-ink">{group.name}</h3>
                    {group.source === 'ldap' && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 font-medium">
                        {traducir("LDAP / AD")}
                      </span>
                    )}
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

              {group.source === 'ldap' ? (
                <p className="text-sm text-ink-2 bg-brand-50 rounded-lg p-3">
                  {traducir("Pertenencia consultada en vivo en el directorio: ")}
                  <span className="font-mono font-medium">{group.ldap_group_name}</span>
                  {group.ldap_group_nested && (
                    <span className="block text-xs text-ink-3 mt-1">{traducir("Incluye subgrupos anidados (Active Directory)")}</span>
                  )}
                </p>
              ) : (
                <>
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
                </>
              )}
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
