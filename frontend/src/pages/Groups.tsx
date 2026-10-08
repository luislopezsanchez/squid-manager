import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { DatalistUsuarios } from '../hooks/useSugerenciasUsuarios'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import RequiereAplicar from '../components/RequiereAplicar'
import Modal from '../components/Modal'
import { IconSpinner, IconFolder, IconTrash } from '../components/Icons'
import { normalizarNombreAcl } from '../utils/aclNames'
import { confirmar } from '../components/ConfirmDialog'

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

type FormGroup = {
  name: string; description: string; no_bump: boolean
  source: 'local' | 'ldap'; ldap_group_name: string; ldap_group_nested: boolean
}
const FORM_VACIO: FormGroup = {
  name: '', description: '', no_bump: false,
  source: 'local', ldap_group_name: '', ldap_group_nested: false,
}

function GroupFormModal({ newGroup, setNewGroup, ldapEnabled, ldapGroups, ldapNombreManual, setLdapNombreManual, onClose, onSubmit }: {
  newGroup: FormGroup
  setNewGroup: (g: FormGroup) => void
  ldapEnabled: boolean
  ldapGroups: string[]
  ldapNombreManual: boolean
  setLdapNombreManual: (v: boolean) => void
  onClose: () => void
  onSubmit: (e: React.FormEvent) => void
}) {
  return (
    <Modal title={traducir('Nuevo grupo')} onClose={onClose} maxWidth="max-w-2xl">
      <datalist id="ldap-group-options">
        {ldapGroups.map(g => <option key={g} value={g} />)}
      </datalist>
      <form onSubmit={onSubmit}>
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
              required autoFocus
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

        <div className="mt-5 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <button type="submit" className="btn btn-primary">{traducir("Crear Grupo")}</button>
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">{traducir("Cancelar")}</button>
          </div>
          <RequiereAplicar />
        </div>
      </form>
    </Modal>
  )
}

export default function Groups() {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [newGroup, setNewGroup] = useState<FormGroup>(FORM_VACIO)
  const [newMember, setNewMember] = useState<Record<number, string>>({})
  // Grupo abierto en el detalle (modal): ahí se gestionan sus miembros.
  const [abierto, setAbierto] = useState<number | null>(null)
  const [ldapEnabled, setLdapEnabled] = useState(false)
  const [ldapGroups, setLdapGroups] = useState<string[]>([])
  const [ldapNombreManual, setLdapNombreManual] = useState(false)
  const [search, setSearch] = useState('')
  const { showToast, ToastContainer } = useToast()

  const loadGroups = () => {
    api.listGroups().then(r => { setGroups(r); setLoadError(false) })
      .catch(() => { showToast(traducir("Error al cargar grupos"), 'error'); setLoadError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadGroups()
    api.getLdapConfig().then(c => {
      setLdapEnabled(!!c.enabled)
      // Solo tiene sentido pedir grupos si LDAP está habilitado -si no, el
      // backend responde 400 igual que con cualquier otra búsqueda al directorio.
      if (c.enabled) api.listLdapGroups().then(r => {
        setLdapGroups(r.groups)
        if (r.truncado) showToast(traducir("El directorio tiene {n} grupos y solo se listan los primeros {m}. Escribe el nombre del grupo a mano.", { n: r.total ?? r.groups.length, m: r.groups.length }), 'warning')
      }).catch(() => {})
    }).catch(() => {})
  }, [])

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
      setShowForm(false)
      loadGroups()
      showToast(`Grupo "${newGroup.name}" creado`)
    } catch (err: any) { showToast(`Error: ${err.message}`, 'error') }
  }

  const handleDelete = async (id: number, name: string) => {
    if (!(await confirmar(`¿Eliminar el grupo "${name}"?`))) return
    try {
      await api.deleteGroup(id)
      notificarCambioPendiente()
      loadGroups()
      showToast(`Grupo "${name}" eliminado`)
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  // Añadir/quitar miembros es OPTIMISTA: la pantalla cambia al instante y, si
  // el servidor falla, se vuelve a cargar el estado real y se avisa. El
  // servidor confirma el cambio en la base de datos al momento y aplica la
  // configuración de Squid en segundo plano, así que no hay nada que esperar.
  const handleAddMember = async (groupId: number) => {
    const username = (newMember[groupId] || '').trim()
    if (!username) return
    const grupo = groups.find(g => g.id === groupId)
    if (grupo?.members.includes(username)) {
      showToast(`"${username}" ${traducir("ya está en el grupo")}`, 'warning')
      return
    }
    setGroups(prev => prev.map(g => g.id === groupId ? { ...g, members: [...g.members, username] } : g))
    setNewMember(prev => ({ ...prev, [groupId]: '' }))
    try {
      await api.addGroupMember(groupId, username)
      notificarCambioPendiente()
    } catch (e: any) {
      loadGroups()
      showToast(`Error: ${e.message}`, 'error')
    }
  }

  const handleRemoveMember = async (groupId: number, username: string) => {
    setGroups(prev => prev.map(g => g.id === groupId ? { ...g, members: g.members.filter(m => m !== username) } : g))
    try {
      await api.removeGroupMember(groupId, username)
      notificarCambioPendiente()
    } catch (e: any) {
      loadGroups()
      showToast(`Error: ${e.message}`, 'error')
    }
  }

  const term = search.trim().toLowerCase()
  const filteredGroups = term
    ? groups.filter(g =>
        g.name.toLowerCase().includes(term) ||
        (g.description ?? '').toLowerCase().includes(term) ||
        g.members.some(m => m.toLowerCase().includes(term))
      )
    : groups

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title">{traducir("Grupos de Usuarios")}</h1>
        <button
          onClick={() => { setNewGroup(FORM_VACIO); setLdapNombreManual(false); setShowForm(true) }}
          className="btn btn-primary"
        >
          {traducir('+ Nuevo Grupo')}
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-xs text-blue-800">
        <strong>{traducir("Grupos: políticas por conjunto de usuarios.")}</strong>{" "}
        {traducir("Cada grupo genera una ACL proxy_auth en Squid. Para aplicar una política, crea una regla de acceso que referencie el nombre del grupo (ej. allow ventas).")}
      </div>

      {showForm && (
        <GroupFormModal
          newGroup={newGroup} setNewGroup={setNewGroup}
          ldapEnabled={ldapEnabled} ldapGroups={ldapGroups}
          ldapNombreManual={ldapNombreManual} setLdapNombreManual={setLdapNombreManual}
          onClose={() => setShowForm(false)}
          onSubmit={handleCreate}
        />
      )}

      {groups.length > 0 && (
        <div className="mb-4">
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={traducir("Buscar por nombre, descripción o miembro…")}
            className="input w-full sm:max-w-sm"
          />
        </div>
      )}

      {loading ? (
        <LoadingState />
      ) : loadError && groups.length === 0 ? (
        <ErrorState onRetry={loadGroups} />
      ) : (
        <div className="grid gap-x-4 gap-y-5" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))' }}>
          {filteredGroups.map(group => (
            <button key={group.id} onClick={() => setAbierto(group.id)} className="folder-card group"
              title={group.description || group.name}>
              <div className="flex items-start gap-2.5">
                <IconFolder className="w-6 h-6 flex-none text-brand-600" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-ink truncate">{group.name}</h3>
                  <p className="text-xs text-ink-3 truncate min-h-[16px]">{group.description || '\u00A0'}</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 mt-3 min-h-[20px]">
                {group.source === 'ldap' && (
                  <span className="text-[10.5px] px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 font-medium">{traducir("LDAP / AD")}</span>
                )}
                {group.no_bump && (
                  <span className="text-[10.5px] px-1.5 py-0.5 rounded bg-warn-soft text-warn font-medium">{traducir("HTTPS sin interceptar")}</span>
                )}
              </div>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-line-soft">
                {group.source === 'ldap' ? (
                  <span className="text-xs text-ink-3">{traducir("Miembros en el directorio")}</span>
                ) : (
                  <>
                    <div className="flex -space-x-1.5">
                      {group.members.slice(0, 4).map(m => (
                        <span key={m} title={m} className="avatar-sq !w-6 !h-6 !text-[10px] ring-2 ring-white bg-brand-50 text-brand-700">{m.slice(0, 2).toUpperCase()}</span>
                      ))}
                    </div>
                    <span className="text-xs text-ink-3 tabular">
                      {group.members.length === 0 ? traducir("Sin miembros") : traducir("{n} miembros", { n: group.members.length })}
                    </span>
                  </>
                )}
              </div>
            </button>
          ))}
          {filteredGroups.length === 0 && (
            <div className="col-span-full text-center py-12 text-ink-3">
              {groups.length === 0
                ? traducir("No hay grupos. Crea el primero.")
                : traducir("Ningún grupo coincide con la búsqueda.")}
            </div>
          )}
        </div>
      )}

      {(() => {
        const group = groups.find(g => g.id === abierto)
        if (!group) return null
        return (
          <Modal title={group.name} onClose={() => setAbierto(null)} maxWidth="max-w-lg">
            {group.description && <p className="text-sm text-ink-3 -mt-2 mb-3">{group.description}</p>}
            <div className="flex flex-wrap gap-1.5 mb-4">
              {group.source === 'ldap' && <span className="text-[11px] px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 font-medium">{traducir("LDAP / AD")}</span>}
              {group.no_bump && (
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-warn-soft text-warn font-medium"
                  title={traducir("El tráfico HTTPS de este grupo no se descifra. El bloqueo por dominio le sigue afectando.")}>{traducir("HTTPS sin interceptar")}</span>
              )}
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
                <div className="text-xs font-medium uppercase tracking-wide text-ink-3 mb-2">{traducir("Miembros")} ({group.members.length})</div>
                <div className="flex flex-wrap gap-2 mb-4 max-h-56 overflow-y-auto">
                  {group.members.map(m => (
                    <span key={m} className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 px-2 py-1 rounded-full text-xs font-medium">
                      {m}
                      <button onClick={() => handleRemoveMember(group.id, m)} aria-label={`${traducir("Quitar")} ${m}`}
                        className="text-brand-600 hover:text-danger w-3.5 h-3.5 flex items-center justify-center">×</button>
                    </span>
                  ))}
                  {group.members.length === 0 && <span className="text-xs text-ink-3">{traducir("Sin miembros")}</span>}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text" autoFocus
                    value={newMember[group.id] || ''}
                    onChange={e => setNewMember(prev => ({ ...prev, [group.id]: e.target.value }))}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddMember(group.id) } }}
                    className="input flex-1"
                    placeholder={traducir("nombre de usuario (local o LDAP)")}
                    list="member-options"
                  />
                  <DatalistUsuarios id="member-options" texto={newMember[group.id] || ''} />
                  <button onClick={() => handleAddMember(group.id)} className="btn btn-primary">{traducir("Añadir")}</button>
                </div>
              </>
            )}

            <div className="mt-6 pt-4 border-t border-line-soft flex justify-between items-center">
              <button onClick={async () => { await handleDelete(group.id, group.name); setAbierto(null) }}
                className="btn btn-outline text-danger"><IconTrash />{traducir("Eliminar grupo")}</button>
              <button onClick={() => setAbierto(null)} className="btn btn-primary">{traducir("Cerrar")}</button>
            </div>
          </Modal>
        )
      })()}
    </div>
  )
}
