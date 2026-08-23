import { useState, useEffect, useMemo, useRef } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface LocalUser {
  source: 'local'
  id: number
  username: string
  enabled: boolean
  expires_at: string | null
  created_at: string
}

interface LdapUserRow {
  source: 'ldap'
  id: number
  username: string
  enabled: boolean
  display_name: string | null
  email: string | null
  created_at: string | null
}

type UnifiedUser = LocalUser | LdapUserRow

/**
 * Los usuarios LDAP importados antes de este cambio no tienen `created_at`
 * en el navegador hasta que se recargue la página con el backend nuevo, y
 * un registro corrupto igual podría no traerlo — mejor mostrar un guion que
 * el confuso "Invalid Date" de `new Date(undefined)`.
 */
function formatFecha(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('es-ES')
}

/**
 * Copia al portapapeles con reserva: la Clipboard API exige un contexto
 * seguro (HTTPS o localhost) y este panel puede servirse por HTTP plano en
 * la red interna, donde `navigator.clipboard` falla en silencio. El método
 * viejo con un textarea oculto no tiene esa restricción.
 */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // sigue al método de reserva
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

/** Campo de solo lectura con botón de copiar, para mostrar una contraseña nueva. */
function CopyField({ value, onCopied }: { value: string; onCopied: () => void }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    const ok = await copyToClipboard(value)
    if (ok) {
      setCopied(true)
      onCopied()
      setTimeout(() => setCopied(false), 2000)
    } else {
      onCopied()
    }
  }
  return (
    <div className="flex gap-2">
      <input readOnly value={value} onFocus={e => e.target.select()}
        className="input font-mono text-sm flex-1" />
      <button type="button" onClick={handleCopy}
        className={`px-4 py-2 rounded-lg font-medium text-sm transition ${
          copied ? 'bg-ok text-white' : 'bg-brand-700 text-white hover:bg-brand-600'
        }`}>
        {copied ? 'Copiado' : 'Copiar'}
      </button>
    </div>
  )
}

/**
 * Modal de contraseña de un usuario local: generar una automática o
 * establecer una propia. Antes solo existía la generación automática y el
 * resultado se mostraba en un `alert()` sin forma de copiarlo.
 */
function PasswordModal({ username, onClose, onSetPassword, onGenerate }: {
  username: string
  onClose: () => void
  onSetPassword: (password: string) => Promise<void>
  onGenerate: () => Promise<string>
}) {
  const [mode, setMode] = useState<'choose' | 'manual' | 'result'>('choose')
  const [manualPassword, setManualPassword] = useState('')
  const [result, setResult] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const handleGenerate = async () => {
    setBusy(true)
    setErr('')
    try {
      const pass = await onGenerate()
      setResult(pass)
      setMode('result')
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setErr('')
    try {
      await onSetPassword(manualPassword)
      setResult(manualPassword)
      setMode('result')
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-1">Contraseña de "{username}"</h2>

        {mode === 'choose' && (
          <>
            <p className="text-sm text-ink-3 mb-5">Elegí cómo asignar la nueva contraseña.</p>
            <div className="space-y-3">
              <button onClick={handleGenerate} disabled={busy}
                className="w-full btn btn-primary disabled:opacity-50">
                {busy ? 'Generando…' : 'Generar automática'}
              </button>
              <button onClick={() => setMode('manual')} disabled={busy}
                className="w-full px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">
                Establecer una propia
              </button>
            </div>
            {err && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
            <button onClick={onClose} className="mt-4 text-sm text-ink-3 hover:text-ink-2 w-full text-center">
              Cancelar
            </button>
          </>
        )}

        {mode === 'manual' && (
          <form onSubmit={handleManualSubmit}>
            <label className="field-label block mb-1.5 mt-4">Contraseña nueva</label>
            <input type="text" value={manualPassword} onChange={e => setManualPassword(e.target.value)}
              className="input font-mono" minLength={8} required autoFocus
              placeholder="Al menos 8 caracteres" />
            {err && <div className="mt-3 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
            <div className="flex gap-2 mt-4">
              <button type="button" onClick={() => setMode('choose')}
                className="flex-1 px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">
                Atrás
              </button>
              <button type="submit" disabled={busy} className="flex-1 btn btn-primary disabled:opacity-50">
                {busy ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </form>
        )}

        {mode === 'result' && (
          <>
            <p className="text-sm text-ink-3 mb-3 mt-2">
              Guardala ahora: no se puede volver a ver una vez que cierres esta ventana.
            </p>
            <CopyField value={result} onCopied={() => {}} />
            <button onClick={onClose} className="mt-5 btn btn-primary w-full">
              Listo
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default function ProxyUsers() {
  const [localUsers, setLocalUsers] = useState<LocalUser[]>([])
  const [ldapUsers, setLdapUsers] = useState<LdapUserRow[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState<'all' | 'local' | 'ldap'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [passwordModalFor, setPasswordModalFor] = useState<LocalUser | null>(null)
  // Nombre -> grupos a los que pertenece. La membresía se guarda por nombre
  // de usuario, no por id, así que sirve igual para locales y para LDAP.
  const [groupsByUser, setGroupsByUser] = useState<Map<string, string[]>>(new Map())
  // Acciones "en vuelo" por fila, para poder deshabilitar el botón exacto que
  // se apretó y mostrar que está trabajando. Sin esto, bloquear a alguien
  // (que reinicia Squid para purgar credenciales, unos segundos) no daba
  // ninguna señal visual: parecía que el botón no hacía nada, e invitaba a
  // volver a apretarlo — lo que de hecho pasó y encadenó varias acciones
  // reales sobre las mismas cuentas.
  // La comprobación tiene que ser síncrona: `useState` no basta, porque su
  // actualización es asíncrona y varios clics disparados antes del primer
  // re-render leen todos el mismo estado "no pendiente" — es exactamente lo
  // que pasó al probar esto: tres clics seguidos en el mismo botón dispararon
  // tres peticiones reales. El ref se actualiza en el acto; el estado solo
  // se usa para forzar el re-render que muestra el botón deshabilitado.
  const pendingRef = useRef<Set<string>>(new Set())
  const [, forceRender] = useState(0)
  const rowKey = (u: { source: string; id: number }) => `${u.source}-${u.id}`
  const isPending = (u: { source: string; id: number }) => pendingRef.current.has(rowKey(u))
  const setRowPending = (u: { source: string; id: number }, on: boolean) => {
    if (on) pendingRef.current.add(rowKey(u)); else pendingRef.current.delete(rowKey(u))
    forceRender(v => v + 1)
  }
  const { showToast, ToastContainer } = useToast()

  const loadUsers = () => {
    Promise.all([
      api.listUsers().catch(() => []),
      api.listLdapUsers().catch(() => []),
      api.listGroups().catch(() => []),
    ]).then(([local, ldap, groups]) => {
      setLocalUsers(local.map((u: any) => ({ ...u, source: 'local' as const })))
      setLdapUsers(ldap.map((u: any) => ({ ...u, source: 'ldap' as const })))

      const map = new Map<string, string[]>()
      for (const g of groups as { name: string; members: string[] }[]) {
        for (const username of g.members) {
          const actuales = map.get(username) ?? []
          actuales.push(g.name)
          map.set(username, actuales)
        }
      }
      setGroupsByUser(map)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { loadUsers() }, [])

  // Tabla unificada: local y LDAP son la misma cosa desde el punto de vista
  // de "quién puede navegar por el proxy", solo cambia de dónde vienen las
  // credenciales. Verlos por separado obligaba a ir a dos páginas distintas
  // para responder una pregunta tan simple como "¿quién tiene acceso hoy?".
  const allUsers: UnifiedUser[] = useMemo(
    () => [...localUsers, ...ldapUsers].sort((a, b) => a.username.localeCompare(b.username)),
    [localUsers, ldapUsers]
  )

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase()
    return allUsers.filter(u => {
      if (sourceFilter !== 'all' && u.source !== sourceFilter) return false
      if (statusFilter === 'enabled' && !u.enabled) return false
      if (statusFilter === 'disabled' && u.enabled) return false
      if (!q) return true
      const haystack = u.source === 'ldap'
        ? `${u.username} ${u.display_name ?? ''} ${u.email ?? ''}`
        : u.username
      return haystack.toLowerCase().includes(q)
    })
  }, [allUsers, search, sourceFilter, statusFilter])

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

  const handleToggle = async (u: UnifiedUser) => {
    if (isPending(u)) return
    setRowPending(u, true)
    // Bloquear a alguien purga la caché de credenciales reiniciando Squid,
    // que tarda varios segundos. Sin este aviso, el botón deshabilitado y
    // el texto "Aplicando…" pueden pasar desapercibidos igual.
    if (u.enabled) showToast('Aplicando… puede tardar unos segundos (reinicia Squid)', 'info')
    try {
      const result = u.source === 'local' ? await api.toggleUser(u.id) : await api.toggleLdapUser(u.id)
      loadUsers()
      showToast(`Usuario "${result.username}" ${result.enabled ? 'activado' : 'desactivado'}`)
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setRowPending(u, false)
    }
  }

  const handleDelete = async (u: LocalUser) => {
    if (isPending(u)) return
    if (!confirm('¿Eliminar este usuario?')) return
    setRowPending(u, true)
    showToast('Eliminando… puede tardar unos segundos (reinicia Squid)', 'info')
    try {
      await api.deleteUser(u.id)
      loadUsers()
      showToast('Usuario eliminado correctamente')
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setRowPending(u, false)
    }
  }

  const enabledCount = allUsers.filter(u => u.enabled).length

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Usuarios</h1>
          <p className="text-sm text-ink-3 mt-1">
            {allUsers.length} en total · {enabledCount} pueden navegar ahora mismo
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn btn-primary"
          >
            {showForm ? 'Cancelar' : '+ Nuevo Usuario Local'}
          </button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-xs text-blue-800">
        <strong>Bloquear acceso</strong> deshabilita al usuario: no puede navegar hasta que lo vuelvas a habilitar.
        Es la única forma de interrumpir a alguien de verdad — cambiar solo la contraseña no lo hace, porque el
        navegador reenvía la que ya tiene guardada sin preguntar nada mientras siga siendo válida.
        La validación de Squid vive <strong>{`${2} horas`}</strong> por defecto (configurable en <em>credentialsttl</em>).
        Los usuarios <strong>LDAP</strong> se sincronizan desde <em>LDAP / Active Directory</em>, pero se habilitan
        y deshabilitan desde aquí.
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="field-label block mb-1.5">Usuario</label>
              <input
                type="text" value={newUser.username}
                onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                className="input"
                required
              />
            </div>
            <div>
              <label className="field-label block mb-1.5">Contraseña</label>
              <input
                type="password" value={newUser.password}
                onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                className="input"
                required
              />
            </div>
          </div>
          {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <button type="submit" className="mt-4 btn btn-primary">
            Crear Usuario
          </button>
        </form>
      )}

      {/* Búsqueda y filtros: antes había que abrir dos páginas distintas
          (Usuarios y LDAP) para saber quién tenía acceso. */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Buscar por usuario, nombre o email…"
          className="input flex-1"
        />
        <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value as any)} className="input sm:w-44">
          <option value="all">Todos los orígenes</option>
          <option value="local">Solo locales</option>
          <option value="ldap">Solo LDAP</option>
        </select>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value as any)} className="input sm:w-44">
          <option value="all">Cualquier estado</option>
          <option value="enabled">Solo habilitados</option>
          <option value="disabled">Solo deshabilitados</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-ink-3">Cargando...</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left">Usuario</th>
                <th className="text-left">Origen</th>
                <th className="text-left">Estado</th>
                <th className="text-left">Grupos</th>
                <th className="text-left">Creado</th>
                <th className="text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {filteredUsers.map(u => (
                <tr key={`${u.source}-${u.id}`} className="hover:bg-brand-50">
                  <td className="px-6 py-4 font-medium text-ink">
                    {u.username}
                    {u.source === 'ldap' && u.display_name && (
                      <span className="block text-xs font-normal text-ink-3">{u.display_name}</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                      u.source === 'local' ? 'bg-brand-50 text-brand-700' : 'bg-purple-50 text-purple-700'
                    }`}>
                      {u.source === 'local' ? 'Local' : 'LDAP'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                      u.enabled ? 'pill-ok' : 'pill-danger'
                    }`}>
                      {u.enabled ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {(groupsByUser.get(u.username) ?? []).length === 0 ? (
                      <span className="text-xs text-ink-3">—</span>
                    ) : (
                      <div className="flex flex-wrap gap-1 max-w-[220px]">
                        {(groupsByUser.get(u.username) ?? []).map(g => (
                          <span key={g} className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-line-soft text-ink-2">
                            {g}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-ink-3">
                    {formatFecha(u.created_at)}
                  </td>
                  <td className="px-6 py-4 text-right space-x-2 whitespace-nowrap">
                    <button onClick={() => handleToggle(u)}
                      disabled={isPending(u)}
                      className="text-primary-600 hover:text-primary-800 text-sm font-medium disabled:opacity-50 disabled:cursor-wait"
                      title={u.enabled ? 'Bloquea su acceso a internet hasta que lo habilites' : 'Permite que navegue a través del proxy'}>
                      {isPending(u) ? 'Aplicando…' : (u.enabled ? 'Bloquear acceso' : 'Habilitar acceso')}
                    </button>
                    {u.source === 'local' && (
                      <>
                        <button onClick={() => setPasswordModalFor(u)}
                          disabled={isPending(u)}
                          className="text-amber-600 hover:text-amber-800 text-sm font-medium disabled:opacity-50"
                          title="Genera una contraseña nueva, o establece una tú mismo">
                          Contraseña
                        </button>
                        <button onClick={() => handleDelete(u)}
                          disabled={isPending(u)}
                          className="text-danger hover:text-danger text-sm font-medium disabled:opacity-50 disabled:cursor-wait">
                          {isPending(u) ? 'Eliminando…' : 'Eliminar'}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {filteredUsers.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-ink-3">
                    {allUsers.length === 0
                      ? 'No hay usuarios. Crea el primero o sincroniza LDAP.'
                      : 'Ningún usuario coincide con el filtro.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {passwordModalFor && (
        <PasswordModal
          username={passwordModalFor.username}
          onClose={() => { setPasswordModalFor(null); loadUsers() }}
          onGenerate={async () => {
            const result = await api.resetPassword(passwordModalFor.id)
            return result.new_password
          }}
          onSetPassword={async (password) => {
            await api.updateUser(passwordModalFor.id, { password })
          }}
        />
      )}
    </div>
  )
}
