import { traducir } from '../i18n'
import { useState, useEffect, useMemo, useRef } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import { formatBytes } from '../utils/format'
import { normalizarUsername } from '../utils/usernames'

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

// Cuota de navegación -por nombre de usuario, sirve igual para uno local o
// uno importado de LDAP (ver app/models/navigation_quota.py). Se carga
// aparte (no viene con el usuario) y se cruza por `username`.
interface Quota {
  id: number
  username: string
  quota_bytes: number
  quota_period: 'daily' | 'weekly' | 'monthly'
  quota_action: 'cut' | 'throttle'
  quota_throttle_bytes_per_sec: number | null
  quota_bytes_used: number
  quota_period_started_at: string | null
}

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
            <p className="text-sm text-ink-3 mb-5">{traducir("Elegí cómo asignar la nueva contraseña.")}</p>
            <div className="space-y-3">
              <button onClick={handleGenerate} disabled={busy}
                className="w-full btn btn-primary disabled:opacity-50">
                {busy ? traducir('Generando…') : traducir('Generar automática')}
              </button>
              <button onClick={() => setMode('manual')} disabled={busy}
                className="w-full px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">{traducir("Establecer una propia")}</button>
            </div>
            {err && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
            <button onClick={onClose} className="mt-4 text-sm text-ink-3 hover:text-ink-2 w-full text-center">{traducir("Cancelar")}</button>
          </>
        )}

        {mode === 'manual' && (
          <form onSubmit={handleManualSubmit}>
            <label htmlFor="proxyuser-new-password" className="field-label block mb-1.5 mt-4">{traducir("Contraseña nueva")}</label>
            <input id="proxyuser-new-password" type="text" value={manualPassword} onChange={e => setManualPassword(e.target.value)}
              className="input font-mono" minLength={8} required autoFocus
              placeholder={traducir("Al menos 8 caracteres")} />
            {err && <div className="mt-3 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
            <div className="flex gap-2 mt-4">
              <button type="button" onClick={() => setMode('choose')}
                className="flex-1 px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">{traducir("Atrás")}</button>
              <button type="submit" disabled={busy} className="flex-1 btn btn-primary disabled:opacity-50">
                {busy ? traducir('Guardando…') : traducir('Guardar')}
              </button>
            </div>
          </form>
        )}

        {mode === 'result' && (
          <>
            <p className="text-sm text-ink-3 mb-3 mt-2">{traducir("Guardala ahora: no se puede volver a ver una vez que cierres esta ventana.")}</p>
            <CopyField value={result} onCopied={() => {}} />
            <button onClick={onClose} className="mt-5 btn btn-primary w-full">{traducir("Listo")}</button>
          </>
        )}
      </div>
    </div>
  )
}

const TAMANO_UNITS = [
  { value: 1048576, label: traducir("MB") },
  { value: 1073741824, label: traducir("GB") },
]
const VELOCIDAD_UNITS = [
  { value: 1024, label: traducir("KB/s") },
  { value: 1048576, label: traducir("MB/s") },
]
const PERIODO_LABELS: Record<string, string> = {
  daily: traducir("Diario"), weekly: traducir("Semanal"), monthly: traducir("Mensual"),
}

// Elige la unidad más legible para un valor guardado en bytes (o
// bytes/s) -sin esto, reabrir una cuota guardada en MB la mostraba
// convertida a una fracción de GB casi ilegible (ej. "0,0048828125 GB"
// para lo que en realidad eran "5 MB"), porque el editor siempre asumía
// la unidad más grande de la lista en vez de la que se había usado.
function detectarUnidad(valor: number, unidades: { value: number }[]): number {
  const ordenadas = [...unidades].sort((a, b) => b.value - a.value)
  for (const u of ordenadas) {
    if (valor >= u.value) return u.value
  }
  return ordenadas[ordenadas.length - 1]?.value ?? 1
}

/**
 * Configurar / editar / quitar la cuota de navegación de uno o varios
 * usuarios (locales o LDAP, da igual). Con más de un nombre en
 * `usernames` es el modo "aplicar en bloque": no hay valores previos que
 * precargar ni opción de "quitar" (cada usuario puede tener o no cuota
 * ya, no tiene sentido "quitarles a todos"). Mismo patrón visual que
 * PasswordModal -un diálogo aparte en vez de un formulario más en la
 * fila, porque son varios campos relacionados entre sí.
 */
function QuotaModal({ usernames, existing, onClose, onSave, onRemove }: {
  usernames: string[]
  existing?: Quota
  onClose: () => void
  onSave: (data: {
    quota_bytes: number; quota_period: string; quota_action: string
    quota_throttle_bytes_per_sec?: number
  }) => Promise<void>
  onRemove?: () => Promise<void>
}) {
  const esBulk = usernames.length > 1
  const tamanoUnidadInicial = existing ? detectarUnidad(existing.quota_bytes, TAMANO_UNITS) : 1073741824
  const [tamano, setTamano] = useState(
    existing ? Math.round((existing.quota_bytes / tamanoUnidadInicial) * 100) / 100 : 5
  )
  const [tamanoUnidad, setTamanoUnidad] = useState(tamanoUnidadInicial)
  const [periodo, setPeriodo] = useState(existing?.quota_period || 'monthly')
  const [accion, setAccion] = useState(existing?.quota_action || 'cut')
  const velocidadUnidadInicial = existing?.quota_throttle_bytes_per_sec
    ? detectarUnidad(existing.quota_throttle_bytes_per_sec, VELOCIDAD_UNITS)
    : 1024
  const [velocidad, setVelocidad] = useState(
    existing?.quota_throttle_bytes_per_sec
      ? Math.round((existing.quota_throttle_bytes_per_sec / velocidadUnidadInicial) * 100) / 100
      : 128
  )
  const [velocidadUnidad, setVelocidadUnidad] = useState(velocidadUnidadInicial)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await onSave({
        quota_bytes: Math.round(tamano * tamanoUnidad),
        quota_period: periodo,
        quota_action: accion,
        quota_throttle_bytes_per_sec: accion === 'throttle' ? Math.round(velocidad * velocidadUnidad) : undefined,
      })
      onClose()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const handleRemove = async () => {
    if (!onRemove) return
    setBusy(true)
    setErr('')
    try {
      await onRemove()
      onClose()
    } catch (e: any) {
      setErr(e.message)
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold mb-1">
          {esBulk
            ? traducir("Aplicar cuota a {n} usuarios", { n: usernames.length })
            : traducir("Cuota de navegación de \"{u}\"", { u: usernames[0] })}
        </h2>
        <p className="text-sm text-ink-3 mb-5">
          {esBulk
            ? traducir("Se aplica la misma configuración a todos los seleccionados, reemplazando la cuota que ya tuvieran.")
            : traducir("Límite de datos por periodo. Se resetea solo al empezar el siguiente.")}
        </p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="quota-size" className="field-label">{traducir("Tamaño de la cuota")}</label>
            <div className="flex gap-2">
              <input id="quota-size" type="number" min="0.1" step="0.1" value={tamano}
                onChange={e => setTamano(parseFloat(e.target.value) || 0)} className="input flex-1" required />
              <select value={tamanoUnidad} onChange={e => setTamanoUnidad(parseInt(e.target.value))} className="input w-28">
                {TAMANO_UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="quota-period" className="field-label">{traducir("Periodo")}</label>
            <select id="quota-period" value={periodo} onChange={e => setPeriodo(e.target.value as any)} className="input">
              <option value="daily">{traducir("Diario")}</option>
              <option value="weekly">{traducir("Semanal")}</option>
              <option value="monthly">{traducir("Mensual")}</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="quota-action" className="field-label">{traducir("Al agotarse")}</label>
            <select id="quota-action" value={accion} onChange={e => setAccion(e.target.value as any)} className="input">
              <option value="cut">{traducir("Cortar la navegación hasta el próximo periodo")}</option>
              <option value="throttle">{traducir("Limitar la velocidad en vez de cortar")}</option>
            </select>
          </div>
          {accion === 'throttle' && (
            <div className="field">
              <label htmlFor="quota-throttle" className="field-label">{traducir("Velocidad límite")}</label>
              <div className="flex gap-2">
                <input id="quota-throttle" type="number" min="1" step="1" value={velocidad}
                  onChange={e => setVelocidad(parseFloat(e.target.value) || 0)} className="input flex-1" required />
                <select value={velocidadUnidad} onChange={e => setVelocidadUnidad(parseInt(e.target.value))} className="input w-28">
                  {VELOCIDAD_UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
              </div>
            </div>
          )}
          {err && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
          <div className="flex gap-2 mt-2">
            {existing && onRemove && (
              <button type="button" onClick={handleRemove} disabled={busy}
                className="btn btn-danger disabled:opacity-50">{traducir("Quitar cuota")}</button>
            )}
            <button type="button" onClick={onClose} disabled={busy}
              className="flex-1 px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">
              {traducir("Cancelar")}
            </button>
            <button type="submit" disabled={busy} className="flex-1 btn btn-primary disabled:opacity-50">
              {busy ? traducir('Guardando…') : traducir('Guardar')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function ProxyUsers() {
  const [localUsers, setLocalUsers] = useState<LocalUser[]>([])
  const [ldapUsers, setLdapUsers] = useState<LdapUserRow[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState<'all' | 'local' | 'ldap'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [passwordModalFor, setPasswordModalFor] = useState<LocalUser | null>(null)
  // null = cerrado; string[] con 1 elemento = editar la cuota de ese
  // usuario; con más de uno = aplicar la misma cuota en bloque.
  const [quotaModalFor, setQuotaModalFor] = useState<string[] | null>(null)
  // Nombre -> grupos a los que pertenece. La membresía se guarda por nombre
  // de usuario, no por id, así que sirve igual para locales y para LDAP.
  const [groupsByUser, setGroupsByUser] = useState<Map<string, string[]>>(new Map())
  // Nombre -> cuota, si tiene una configurada. Igual que groupsByUser: se
  // carga aparte y se cruza por username, sirve para locales y LDAP por
  // igual.
  const [quotasByUser, setQuotasByUser] = useState<Map<string, Quota>>(new Map())
  // Selección para aplicar una cuota a varios usuarios de una vez -sin
  // esto, ponerle una cuota a 50 usuarios importados de AD era repetir el
  // mismo formulario 50 veces.
  const [selected, setSelected] = useState<Set<string>>(new Set())
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
    setLoading(true)
    // Cada llamada absorbe su propio error (que LDAP falle no debería tapar
    // la lista local, ni al revés) -pero eso significa que un fallo total
    // (los 4 servicios caídos a la vez, ej. bajo el límite de peticiones)
    // antes se veía como "no hay usuarios", sin ninguna pista de que en
    // realidad la carga falló. `usersFailed` distingue ambos casos: solo
    // importa si las dos listas de usuarios (no grupos/cuotas, que son
    // metadata secundaria) fallaron de verdad.
    let usersFailed = false
    Promise.all([
      api.listUsers().catch(() => { usersFailed = true; return [] }),
      api.listLdapUsers().catch(() => { usersFailed = true; return [] }),
      api.listGroups().catch(() => []),
      api.listQuotas().catch(() => []),
    ]).then(([local, ldap, groups, quotas]) => {
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

      setQuotasByUser(new Map((quotas as Quota[]).map(q => [q.username, q])))
      setLoadError(usersFailed && local.length === 0 && ldap.length === 0)
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
    if (u.enabled) showToast(traducir("Aplicando… puede tardar unos segundos (reinicia Squid)"), 'info')
    try {
      const result = u.source === 'local' ? await api.toggleUser(u.id) : await api.toggleLdapUser(u.id)
      loadUsers()
      showToast(`Usuario "${result.username}" ${result.enabled ? traducir('activado') : traducir('desactivado')}`)
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setRowPending(u, false)
    }
  }

  const handleDelete = async (u: LocalUser) => {
    if (isPending(u)) return
    if (!confirm(traducir("¿Eliminar este usuario?"))) return
    setRowPending(u, true)
    showToast(traducir("Eliminando… puede tardar unos segundos (reinicia Squid)"), 'info')
    try {
      await api.deleteUser(u.id)
      // Borrar un usuario que estaba en un grupo quita su membresía de las
      // ACLs del squid.conf -eso sí requiere Aplicar cambios-, pero uno sin
      // grupo no. Se notifica siempre: más barato que un GET de más al
      // topbar que dejar pasar el caso en que sí hacía falta.
      notificarCambioPendiente()
      loadUsers()
      showToast(traducir("Usuario eliminado correctamente"))
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setRowPending(u, false)
    }
  }

  const handleSaveQuota = async (data: {
    quota_bytes: number; quota_period: string; quota_action: string
    quota_throttle_bytes_per_sec?: number
  }) => {
    if (!quotaModalFor) return
    if (quotaModalFor.length > 1) {
      const result = await api.setQuotaBulk(quotaModalFor, data)
      notificarCambioPendiente()
      loadUsers()
      setSelected(new Set())
      if (result.errores.length > 0) {
        showToast(traducir("{n} cuotas aplicadas, {m} con error: {detalle}", {
          n: result.aplicadas.length, m: result.errores.length, detalle: result.errores.join('; '),
        }), 'error')
      } else {
        showToast(traducir("Cuota aplicada a {n} usuarios", { n: result.aplicadas.length }))
      }
      return
    }
    const username = quotaModalFor[0]
    await api.setQuota(username, data)
    notificarCambioPendiente()
    loadUsers()
    showToast(traducir("Cuota de \"{u}\" guardada", { u: username }))
  }

  const handleRemoveQuota = async () => {
    if (!quotaModalFor || quotaModalFor.length !== 1) return
    const username = quotaModalFor[0]
    await api.removeQuota(username)
    notificarCambioPendiente()
    loadUsers()
    showToast(traducir("Cuota de \"{u}\" quitada", { u: username }))
  }

  const toggleSelected = (username: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(username)) next.delete(username); else next.add(username)
      return next
    })
  }

  const toggleSelectedTodos = () => {
    setSelected(prev =>
      prev.size === filteredUsers.length ? new Set() : new Set(filteredUsers.map(u => u.username))
    )
  }

  const enabledCount = allUsers.filter(u => u.enabled).length

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Usuarios")}</h1>
          <p className="text-sm text-ink-3 mt-1">
            {allUsers.length} en total · {enabledCount} pueden navegar ahora mismo
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn btn-primary"
          >
            {showForm ? traducir('Cancelar') : traducir('+ Nuevo Usuario Local')}
          </button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-xs text-blue-800">
        <strong>{traducir("Bloquear acceso")}</strong> deshabilita al usuario: no puede navegar hasta que lo vuelvas a habilitar.
        Es la única forma de interrumpir a alguien de verdad — cambiar solo la contraseña no lo hace, porque el
        navegador reenvía la que ya tiene guardada sin preguntar nada mientras siga siendo válida.
        La validación de Squid vive <strong>{`${2} horas`}</strong> por defecto (configurable en <em>credentialsttl</em>).
        Los usuarios <strong>LDAP</strong> se sincronizan desde <em>{traducir("LDAP / Active Directory")}</em>{traducir(", pero se habilitan y deshabilitan desde aquí.")}</div>

      {showForm && (
        <form onSubmit={handleCreate} className="card p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="proxyuser-username" className="field-label block mb-1.5">{traducir("Usuario")}</label>
              <input
                id="proxyuser-username"
                type="text" value={newUser.username}
                onChange={e => setNewUser({ ...newUser, username: normalizarUsername(e.target.value) })}
                className="input font-mono text-sm"
                required
              />
              <p className="field-help mt-1">{traducir("Solo letras, números, punto, guion y guion bajo, sin espacios ni acentos.")}</p>
            </div>
            <div>
              <label htmlFor="proxyuser-password" className="field-label block mb-1.5">{traducir("Contraseña")}</label>
              <input
                id="proxyuser-password"
                type="password" value={newUser.password}
                onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                className="input"
                required
              />
            </div>
          </div>
          {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <button type="submit" className="mt-4 btn btn-primary">{traducir("Crear Usuario")}</button>
        </form>
      )}

      {/* Búsqueda y filtros: antes había que abrir dos páginas distintas
          (Usuarios y LDAP) para saber quién tenía acceso. */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={traducir("Buscar por usuario, nombre o email…")}
          className="input flex-1"
        />
        <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value as any)} className="input sm:w-44">
          <option value="all">{traducir("Todos los orígenes")}</option>
          <option value="local">{traducir("Solo locales")}</option>
          <option value="ldap">{traducir("Solo LDAP")}</option>
        </select>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value as any)} className="input sm:w-44">
          <option value="all">{traducir("Cualquier estado")}</option>
          <option value="enabled">{traducir("Solo habilitados")}</option>
          <option value="disabled">{traducir("Solo deshabilitados")}</option>
        </select>
      </div>

      {/* Barra de acción en bloque: solo aparece con algo seleccionado, para
          no ocupar espacio el resto del tiempo. Poner una cuota a 50
          usuarios uno por uno era justo la queja que motivó esto. */}
      {selected.size > 0 && (
        <div className="flex items-center justify-between bg-brand-50 border border-brand-200 rounded-lg px-4 py-2.5 mb-4">
          <span className="text-sm font-medium text-brand-700">
            {traducir("{n} seleccionados", { n: selected.size })}
          </span>
          <div className="flex items-center gap-3">
            <button onClick={() => setQuotaModalFor(Array.from(selected))} className="btn btn-primary btn-sm">
              {traducir("Aplicar cuota a los seleccionados")}
            </button>
            <button onClick={() => setSelected(new Set())} className="text-sm text-ink-3 hover:text-ink-2">
              {traducir("Cancelar selección")}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <LoadingState />
      ) : loadError ? (
        <ErrorState onRetry={loadUsers} />
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left px-2">
                  <input type="checkbox" checked={filteredUsers.length > 0 && selected.size === filteredUsers.length}
                    onChange={toggleSelectedTodos} title={traducir("Seleccionar todos")} />
                </th>
                <th className="text-left">{traducir("Usuario")}</th>
                <th className="text-left">{traducir("Origen")}</th>
                <th className="text-left">{traducir("Estado")}</th>
                <th className="text-left">{traducir("Grupos")}</th>
                <th className="text-left">{traducir("Cuota")}</th>
                <th className="text-left">{traducir("Creado")}</th>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {filteredUsers.map(u => (
                <tr key={`${u.source}-${u.id}`} className="hover:bg-brand-50">
                  <td className="px-2 py-4">
                    <input type="checkbox" checked={selected.has(u.username)} onChange={() => toggleSelected(u.username)} />
                  </td>
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
                  <td className="px-6 py-4">
                    {(() => {
                      const cuota = quotasByUser.get(u.username)
                      if (!cuota) {
                        return (
                          <button onClick={() => setQuotaModalFor([u.username])} className="text-xs text-brand-700 hover:underline">
                            {traducir("Configurar")}
                          </button>
                        )
                      }
                      return (
                        <button onClick={() => setQuotaModalFor([u.username])} className="text-left group" title={traducir("Editar cuota")}>
                          <div className="text-xs text-ink-2 group-hover:text-brand-700">
                            {formatBytes(cuota.quota_bytes_used)} / {formatBytes(cuota.quota_bytes)}
                            <span className="text-ink-3"> · {PERIODO_LABELS[cuota.quota_period] || cuota.quota_period}</span>
                          </div>
                          <div className="w-28 h-1.5 rounded-full bg-line-soft mt-1 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${cuota.quota_bytes_used >= cuota.quota_bytes ? 'bg-danger' : cuota.quota_bytes_used / cuota.quota_bytes > 0.8 ? 'bg-warn' : 'bg-ok'}`}
                              style={{ width: `${Math.min(100, (cuota.quota_bytes_used / cuota.quota_bytes) * 100)}%` }}
                            />
                          </div>
                        </button>
                      )
                    })()}
                  </td>
                  <td className="px-6 py-4 text-sm text-ink-3">
                    {formatFecha(u.created_at)}
                  </td>
                  <td className="px-6 py-4 text-right space-x-2 whitespace-nowrap">
                    <button onClick={() => handleToggle(u)}
                      disabled={isPending(u)}
                      className="text-primary-600 hover:text-primary-800 text-sm font-medium disabled:opacity-50 disabled:cursor-wait"
                      title={u.enabled ? traducir('Bloquea su acceso a internet hasta que lo habilites') : traducir('Permite que navegue a través del proxy')}>
                      {isPending(u) ? 'Aplicando…' : (u.enabled ? 'Bloquear acceso' : 'Habilitar acceso')}
                    </button>
                    {u.source === 'local' && (
                      <>
                        <button onClick={() => setPasswordModalFor(u)}
                          disabled={isPending(u)}
                          className="text-amber-600 hover:text-amber-800 text-sm font-medium disabled:opacity-50"
                          title={traducir("Genera una contraseña nueva, o establece una tú mismo")}>{traducir("Contraseña")}</button>
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
                  <td colSpan={8} className="px-6 py-12 text-center text-ink-3">
                    {allUsers.length === 0
                      ? traducir('No hay usuarios. Crea el primero o sincroniza LDAP.') : traducir('Ningún usuario coincide con el filtro.')}
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

      {quotaModalFor && (
        <QuotaModal
          usernames={quotaModalFor}
          existing={quotaModalFor.length === 1 ? quotasByUser.get(quotaModalFor[0]) : undefined}
          onClose={() => setQuotaModalFor(null)}
          onSave={handleSaveQuota}
          onRemove={quotaModalFor.length === 1 ? handleRemoveQuota : undefined}
        />
      )}
    </div>
  )
}
