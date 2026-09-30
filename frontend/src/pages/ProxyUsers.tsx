import { traducir } from '../i18n'
import { useState, useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import { IconClose, IconEdit, IconKey, IconTrash, IconBan, IconCheck, IconDownload, IconUpload, IconSpinner, IconChevronUp, IconChevronDown } from '../components/Icons'
import Modal from '../components/Modal'
import { formatBytes } from '../utils/format'
import { normalizarUsername } from '../utils/usernames'
import Pagination from '../components/Pagination'
import { usePaginacion } from '../hooks/usePaginacion'
import { TAMANO_UNITS, VELOCIDAD_UNITS, PERIODO_LABELS, detectarUnidad } from '../utils/quotaUnits'
import { confirmar } from '../components/ConfirmDialog'
import { CredencialesModal, ImportarUsuariosModal } from '../components/UsuariosMasivo'
import { useDescarga } from '../utils/descarga'

interface LocalUser {
  source: 'local'
  id: number
  username: string
  // Mismo campo que LdapUserRow.display_name -acá lo escribe el admin a
  // mano al crear el usuario, en vez de venir sincronizado de un
  // directorio.
  display_name: string | null
  email?: string | null
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
  quota_next_reset?: string | null
}

/**
 * Los usuarios LDAP importados antes de este cambio no tienen `created_at`
 * en el navegador hasta que se recargue la página con el backend nuevo, y
 * un registro corrupto igual podría no traerlo — mejor mostrar un guion que
 * el confuso "Invalid Date" de `new Date(undefined)`.
 */
function formatFechaHora(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value.endsWith('Z') || value.includes('+') ? value : value + 'Z')
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' })
}

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

// Antes era un <form> siempre incrustado en la página, que aparecía como
// una tabla más entre el aviso y el listado -mismo cambio de criterio que
// ya se hizo con "Agregar nodo" en Panel Central: un modal separa
// claramente la acción de "estoy creando algo nuevo" de la lista de abajo.
// Pedido en vivo, 2026-09-27.
function ModalCrearUsuario({ newUser, setNewUser, error, onSave, onClose }: {
  newUser: { username: string; display_name: string; email: string; password: string }
  setNewUser: (v: { username: string; display_name: string; email: string; password: string }) => void
  error: string
  onSave: (e: React.FormEvent) => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-lg shadow-lg overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line-soft">
          <h2 className="text-lg font-bold text-ink">{traducir("Nuevo usuario local")}</h2>
          <button onClick={onClose} aria-label={traducir("Cerrar")}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-ink-3 hover:bg-line-soft hover:text-ink transition flex-none">
            <IconClose className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={onSave} className="px-6 py-4">
          <div className="space-y-4">
            <div>
              <label htmlFor="proxyuser-username" className="field-label block mb-1.5">{traducir("Usuario")}</label>
              <input
                id="proxyuser-username"
                type="text" value={newUser.username}
                onChange={e => setNewUser({ ...newUser, username: normalizarUsername(e.target.value) })}
                className="input font-mono text-sm"
                required autoFocus
              />
              <p className="field-help mt-1">{traducir("Solo letras, números, punto, guion y guion bajo, sin espacios ni acentos.")}</p>
            </div>
            <div>
              <label htmlFor="proxyuser-display-name" className="field-label block mb-1.5">{traducir("Nombre para mostrar")}</label>
              <input
                id="proxyuser-display-name"
                type="text" value={newUser.display_name}
                onChange={e => setNewUser({ ...newUser, display_name: e.target.value })}
                className="input" placeholder={traducir("ej: Juan Pérez")}
              />
              <p className="field-help mt-1">{traducir("Opcional -mismo campo que ya usan los usuarios LDAP, para identificar a la persona además del usuario.")}</p>
            </div>
            <div>
              <label htmlFor="proxyuser-email" className="field-label block mb-1.5">{traducir("Correo electrónico")}</label>
              <input
                id="proxyuser-email"
                type="email" value={newUser.email}
                onChange={e => setNewUser({ ...newUser, email: e.target.value })}
                className="input" placeholder="usuario@empresa.com"
              />
              <p className="field-help mt-1">{traducir("Opcional. Sirve para identificar a la persona; si no lo pones, queda en blanco.")}</p>
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
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn btn-outline">{traducir("Cancelar")}</button>
            <button type="submit" className="btn btn-primary">{traducir("Crear Usuario")}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

/** Editar el nombre para mostrar de un usuario local ya creado -antes solo
 * se podía poner al crearlo, sin forma de corregirlo después. */
function ModalEditarUsuario({ username, displayName, email, onClose, onSave }: {
  username: string
  displayName: string
  email: string
  onClose: () => void
  onSave: (displayName: string, email: string) => Promise<void>
}) {
  const [value, setValue] = useState(displayName)
  const [correo, setCorreo] = useState(email)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await onSave(value, correo)
      onClose()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={traducir('Editar usuario "{u}"', { u: username })} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label htmlFor="edit-display-name" className="field-label block mb-1.5">{traducir("Nombre para mostrar")}</label>
        <input
          id="edit-display-name"
          type="text" value={value} onChange={e => setValue(e.target.value)}
          className="input" placeholder={traducir("ej: Juan Pérez")} autoFocus
        />
        <label htmlFor="edit-email" className="field-label block mb-1.5 mt-4">{traducir("Correo electrónico")}</label>
        <input id="edit-email" type="email" value={correo} onChange={e => setCorreo(e.target.value)}
          className="input" placeholder="usuario@empresa.com" />
        {err && <div className="mt-3 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
        <div className="mt-5 flex items-center gap-3">
          <button type="submit" disabled={busy} className="btn btn-primary disabled:opacity-50">
            {busy ? traducir('Guardando…') : traducir('Guardar')}
          </button>
          <button type="button" onClick={onClose} className="text-sm text-ink-3 hover:text-ink-2">{traducir("Cancelar")}</button>
        </div>
      </form>
    </Modal>
  )
}

/** Encabezado de columna que ordena la tabla al hacer clic (otro clic invierte). */
function ThOrden<K extends string>({ clave, orden, onClick, children }: {
  clave: K
  orden: { clave: K; asc: boolean }
  onClick: (k: K) => void
  children: React.ReactNode
}) {
  const activo = orden.clave === clave
  return (
    <th className="text-left" aria-sort={activo ? (orden.asc ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => onClick(clave)}
        className={`inline-flex items-center gap-1 uppercase tracking-[inherit] font-bold hover:text-ink ${activo ? 'text-ink' : ''}`}>
        {children}
        {activo
          ? (orden.asc ? <IconChevronUp className="w-3 h-3" /> : <IconChevronDown className="w-3 h-3" />)
          : <span className="w-3 h-3 opacity-25"><IconChevronDown className="w-3 h-3" /></span>}
      </button>
    </th>
  )
}

export default function ProxyUsers() {
  const [localUsers, setLocalUsers] = useState<LocalUser[]>([])
  const [ldapUsers, setLdapUsers] = useState<LdapUserRow[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', display_name: '', email: '', password: '' })
  const [error, setError] = useState('')
  // La búsqueda vive en la URL (?q=...), no solo en useState: así
  // sobrevive a un F5 -antes se perdía en cada recarga real de la página,
  // aunque el sondeo silencioso de más abajo ya no la perdiera con cada
  // refresco de datos. Pedido en vivo, 2026-09-27 (segunda vez que se pide
  // esto mismo).
  const [urlParams, setUrlParams] = useSearchParams()
  const [search, setSearchState] = useState(() => urlParams.get('q') || '')
  const setSearch = (v: string) => {
    setSearchState(v)
    setUrlParams(prev => {
      const next = new URLSearchParams(prev)
      if (v) next.set('q', v)
      else next.delete('q')
      return next
    }, { replace: true })
  }
  const [sourceFilter, setSourceFilter] = useState<'all' | 'local' | 'ldap'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  // Mismo patrón que `search` (?q=...): vive en la URL para que el enlace
  // "ver todos" de la tarjeta "Usuarios conectados ahora" del Dashboard
  // pueda entrar directo con el filtro ya puesto (/users?conectado=1), en
  // vez de un modal con su propia lista y buscador -pedido en vivo,
  // 2026-09-28.
  const [connectedFilter, setConnectedFilterState] = useState<'all' | 'connected'>(
    () => urlParams.get('conectado') === '1' ? 'connected' : 'all'
  )
  const setConnectedFilter = (v: 'all' | 'connected') => {
    setConnectedFilterState(v)
    setUrlParams(prev => {
      const next = new URLSearchParams(prev)
      if (v === 'connected') next.set('conectado', '1')
      else next.delete('conectado')
      return next
    }, { replace: true })
  }
  // Quién está conectado ahora mismo (para el filtro de arriba) -se carga
  // junto con grupos/cuotas, mismo criterio: metadata secundaria que no
  // debe retrasar mostrar la lista de usuarios en sí.
  const [connectedUsers, setConnectedUsers] = useState<Set<string>>(new Set())
  const [passwordModalFor, setPasswordModalFor] = useState<LocalUser | null>(null)
  const [editModalFor, setEditModalFor] = useState<LocalUser | null>(null)
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
  // Orden de la tabla: clic en el encabezado alterna ascendente/descendente.
  type ClaveOrden = 'usuario' | 'origen' | 'estado' | 'conexion' | 'grupos' | 'cuota' | 'creado'
  const [orden, setOrden] = useState<{ clave: ClaveOrden; asc: boolean }>({ clave: 'usuario', asc: true })
  const alternarOrden = (clave: ClaveOrden) =>
    setOrden(o => o.clave === clave ? { clave, asc: !o.asc } : { clave, asc: true })
  const [credenciales, setCredenciales] = useState<{ usuario: string; password: string }[] | null>(null)
  const [importarAbierto, setImportarAbierto] = useState(false)
  const [formatoExport, setFormatoExport] = useState<'csv' | 'xlsx'>('xlsx')
  const [masivoBusy, setMasivoBusy] = useState(false)
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
  const { descargando: exportando, descargar, etiqueta: etiquetaExport } = useDescarga(showToast)

  const loadUsers = (silent = false) => {
    // silent=true (sondeo periódico, ver el useEffect de más abajo): no
    // vuelve a mostrar la pantalla de carga -eso vaciaba la tabla cada
    // pocos segundos-, solo refresca los datos por detrás. Antes la única
    // forma de ver el consumo de cuota actualizado era recargar la página
    // entera a mano, y eso perdía la búsqueda/filtro en curso -eran, en el
    // fondo, el mismo problema: no había ningún refresco en vivo. Pedido
    // en vivo, 2026-09-27.
    if (!silent) setLoading(true)
    // Cada llamada absorbe su propio error (que LDAP falle no debería tapar
    // la lista local, ni al revés) -pero eso significa que un fallo total
    // (los 2 servicios caídos a la vez, ej. bajo el límite de peticiones)
    // antes se veía como "no hay usuarios", sin ninguna pista de que en
    // realidad la carga falló. `usersFailed` distingue ambos casos.
    let usersFailed = false
    Promise.all([
      api.listUsers().catch(() => { usersFailed = true; return [] }),
      api.listLdapUsers().catch(() => { usersFailed = true; return [] }),
    ]).then(([local, ldap]) => {
      // Un sondeo silencioso que falla (red caída un instante, token por
      // vencer) no debe vaciar la tabla que ya se veía bien: se deja todo
      // como estaba y se reintenta en el próximo ciclo, sin mostrar ni un
      // error ni una lista vacía de la nada.
      if (silent && usersFailed) return
      setLocalUsers(local.map((u: any) => ({ ...u, source: 'local' as const })))
      setLdapUsers(ldap.map((u: any) => ({ ...u, source: 'ldap' as const })))
      setLoadError(usersFailed && local.length === 0 && ldap.length === 0)
    }).finally(() => setLoading(false))

    // Grupos y cuotas son metadata secundaria (solo alimentan el badge de
    // grupo y la barra de cuota de cada fila) -se piden aparte, en vez de
    // en el mismo Promise.all de arriba, para que esperarlas no retrase
    // mostrar la lista de usuarios en sí. Antes las cuatro llamadas se
    // esperaban todas juntas, así que la más lenta de las cuatro (no
    // siempre la misma) demoraba la tabla entera aunque los usuarios ya
    // estuvieran listos.
    Promise.all([
      api.listGroups().catch(() => []),
      api.listQuotas().catch(() => []),
      // Endpoint liviano a propósito (no /panel/dashboard completo, que
      // calcula de más para lo que hace falta acá): pedir el dashboard
      // entero cada 8s desde esta pantalla -encima del propio sondeo de
      // 5s del Dashboard, si estaba abierto a la vez- alcanzaba a saturar
      // el pool de conexiones bajo carga real. Se vio en vivo, 2026-09-28:
      // Usuarios tardaba 10+ segundos en cargar y el filtro de conectados
      // llegaba vacío porque esa llamada pesada directamente fallaba por
      // lenta. Ver routes/metrics.py::usuarios_conectados_route.
      api.getUsuariosConectados().catch(() => []),
    ]).then(([groups, quotas, conectados]) => {
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
      setConnectedUsers(new Set(conectados as string[]))
    })
  }

  useEffect(() => {
    loadUsers()
    const interval = setInterval(() => loadUsers(true), 8000)
    return () => clearInterval(interval)
  }, [])

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
    const filtrados = allUsers.filter(u => {
      if (sourceFilter !== 'all' && u.source !== sourceFilter) return false
      if (statusFilter === 'enabled' && !u.enabled) return false
      if (statusFilter === 'disabled' && u.enabled) return false
      if (connectedFilter === 'connected' && !connectedUsers.has(u.username)) return false
      if (!q) return true
      // El correo cuenta para todos (locales y LDAP): se puede buscar a alguien por su email.
      const haystack = `${u.username} ${u.display_name ?? ''} ${u.email ?? ''}`
      return haystack.toLowerCase().includes(q)
    })
    // Orden elegido con el clic en el encabezado (por defecto, por usuario).
    // Los empates se resuelven siempre por nombre para que el orden sea estable.
    const valor = (u: UnifiedUser): number | string => {
      switch (orden.clave) {
        case 'origen': return u.source
        case 'estado': return u.enabled ? 1 : 0
        case 'conexion': return connectedUsers.has(u.username) ? 1 : 0
        case 'grupos': return (groupsByUser.get(u.username) ?? []).length
        case 'cuota': {
          const c = quotasByUser.get(u.username)
          return c && c.quota_bytes ? c.quota_bytes_used / c.quota_bytes : -1
        }
        case 'creado': return u.created_at ? new Date(u.created_at).getTime() : 0
        default: return u.username.toLowerCase()
      }
    }
    const signo = orden.asc ? 1 : -1
    return filtrados.sort((a, b) => {
      const va = valor(a), vb = valor(b)
      const c = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb))
      return c !== 0 ? c * signo : a.username.localeCompare(b.username)
    })
  }, [allUsers, search, sourceFilter, statusFilter, connectedFilter, connectedUsers, orden, groupsByUser, quotasByUser])

  const hayFiltros = search.trim() !== '' || sourceFilter !== 'all' || statusFilter !== 'all' || connectedFilter !== 'all'
  const limpiarFiltros = () => {
    setSearch(''); setSourceFilter('all'); setStatusFilter('all'); setConnectedFilter('all')
  }

  // Paginado en el cliente, no en el servidor: la lista ya se trae entera
  // (local + LDAP combinados, ver loadUsers) porque la búsqueda y los
  // filtros de arriba necesitan verla completa para funcionar -paginar en
  // el servidor hubiera significado perder la búsqueda entre páginas, o
  // rehacer toda esa lógica del lado del backend. Acá solo se corta cuántas
  // filas se DIBUJAN a la vez -con cientos de usuarios (LDAP importa
  // fácil esa cantidad) renderizar la tabla entera de golpe era lento y
  // poco práctico para navegar. Pedido en vivo, 2026-09-27.
  const USUARIOS_POR_PAGINA = 50
  const { pagina, setPagina, totalPaginas } = usePaginacion(filteredUsers.length, USUARIOS_POR_PAGINA)
  useEffect(() => { setPagina(0) }, [search, sourceFilter, statusFilter])
  const usuariosPagina = filteredUsers.slice(
    pagina * USUARIOS_POR_PAGINA, (pagina + 1) * USUARIOS_POR_PAGINA,
  )

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api.createUser({
        username: newUser.username,
        display_name: newUser.display_name.trim() || undefined,
        email: newUser.email.trim() || undefined,
        password: newUser.password,
        enabled: true,
      })
      setNewUser({ username: '', display_name: '', email: '', password: '' })
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
    if (!(await confirmar(traducir("¿Eliminar este usuario?")))) return
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

  // Acciones en bloque sobre la selección. Todas piden confirmación antes de
  // aplicarse; el backend hace el lote entero con un solo reinicio de Squid.
  const accionMasiva = async (accion: 'enable' | 'disable' | 'delete' | 'reset_password') => {
    const nombres = Array.from(selected)
    const n = nombres.length
    const textos = {
      enable: [traducir("¿Habilitar a {n} usuarios seleccionados? Podrán volver a navegar.", { n }), traducir("Habilitar"), 'normal'],
      disable: [traducir("¿Deshabilitar a {n} usuarios seleccionados? Dejarán de poder navegar hasta que los habilites.", { n }), traducir("Deshabilitar"), 'peligro'],
      delete: [traducir("¿Eliminar a {n} usuarios seleccionados? Se borran del sistema y de sus grupos, y no se puede deshacer. Los usuarios LDAP se omiten: se gestionan en el directorio.", { n }), traducir("Eliminar"), 'peligro'],
      reset_password: [traducir("¿Generar credenciales nuevas para {n} usuarios seleccionados? Sus contraseñas actuales dejarán de funcionar y verás las nuevas una sola vez. Los usuarios LDAP se omiten.", { n }), traducir("Generar credenciales"), 'peligro'],
    } as const
    const [mensaje, etiqueta, tono] = textos[accion]
    if (!(await confirmar(mensaje, { confirmar: etiqueta, tono: tono as 'normal' | 'peligro' }))) return
    setMasivoBusy(true)
    try {
      const r = await api.bulkUsers(accion, nombres)
      notificarCambioPendiente()
      loadUsers()
      setSelected(new Set())
      if (r.credenciales?.length) setCredenciales(r.credenciales)
      const aviso = r.omitidos?.length
        ? traducir("{ok} usuarios procesados, {om} omitidos: {detalle}", { ok: r.ok.length, om: r.omitidos.length, detalle: r.omitidos.slice(0, 3).map((o: any) => `${o.usuario} (${o.motivo})`).join('; ') })
        : traducir("{ok} usuarios procesados", { ok: r.ok.length })
      showToast(aviso, r.omitidos?.length ? 'warning' : 'success')
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setMasivoBusy(false)
    }
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
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button onClick={() => setImportarAbierto(true)} className="btn btn-outline" title={traducir("Carga masiva de usuarios desde un archivo CSV, Excel o de texto")}>
            <IconUpload />{traducir("Importar")}
          </button>
          <div className="inline-flex">
            <select value={formatoExport} onChange={e => setFormatoExport(e.target.value as 'csv' | 'xlsx')}
              className="input rounded-r-none w-[88px]" aria-label={traducir("Formato de exportación")}>
              <option value="xlsx">Excel</option>
              <option value="csv">CSV</option>
            </select>
            <button onClick={() => descargar(api.exportUsersUrl(formatoExport), `usuarios-${new Date().toISOString().slice(0, 10)}.${formatoExport}`, traducir('Usuarios exportados'))}
              disabled={exportando} className="btn btn-outline rounded-l-none border-l-0"
              title={traducir("Descarga la lista de usuarios (sin contraseñas)")}>
              {exportando ? <IconSpinner className="animate-spin" /> : <IconDownload />}{exportando ? etiquetaExport : traducir("Exportar")}
            </button>
          </div>
          <button
            onClick={() => { setNewUser({ username: '', display_name: '', email: '', password: '' }); setError(''); setShowForm(true) }}
            className="btn btn-primary"
          >
            {traducir('+ Nuevo Usuario Local')}
          </button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-6 text-xs text-blue-800">
        <strong>{traducir("Bloquear acceso")}</strong>{" "}
        {traducir("deshabilita al usuario: no puede navegar hasta que lo vuelvas a habilitar. Es la única forma de interrumpir a alguien de verdad — cambiar solo la contraseña no lo hace, porque el navegador reenvía la que ya tiene guardada sin preguntar nada mientras siga siendo válida. La validación de Squid vive 2 horas por defecto (configurable en credentialsttl).")}{" "}
        {traducir("Los usuarios LDAP se sincronizan desde LDAP / Active Directory, pero se habilitan y deshabilitan desde aquí.")}</div>

      {showForm && (
        <ModalCrearUsuario
          newUser={newUser} setNewUser={setNewUser} error={error}
          onSave={handleCreate} onClose={() => setShowForm(false)}
        />
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
        <select value={connectedFilter} onChange={e => setConnectedFilter(e.target.value as any)} className="input sm:w-44">
          <option value="all">{traducir("Conectados o no")}</option>
          <option value="connected">{traducir("Solo conectados ahora")}</option>
        </select>
        {hayFiltros && (
          <button onClick={limpiarFiltros} className="btn btn-outline flex-none" title={traducir("Quita la búsqueda y todos los filtros")}>
            <IconClose />{traducir("Limpiar filtros")}
          </button>
        )}
      </div>

      {/* Barra de acción en bloque: solo aparece con algo seleccionado, para
          no ocupar espacio el resto del tiempo. Poner una cuota a 50
          usuarios uno por uno era justo la queja que motivó esto. */}
      {selected.size > 0 && (
        <div className="flex items-center justify-between bg-brand-50 border border-brand-200 rounded-lg px-4 py-2.5 mb-4">
          <span className="text-sm font-medium text-brand-700">
            {traducir("{n} seleccionados", { n: selected.size })}
          </span>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <button onClick={() => setQuotaModalFor(Array.from(selected))} disabled={masivoBusy} className="btn btn-primary btn-sm">
              {traducir("Aplicar cuota")}
            </button>
            <button onClick={() => accionMasiva('enable')} disabled={masivoBusy} className="btn btn-outline btn-sm"><IconCheck />{traducir("Habilitar")}</button>
            <button onClick={() => accionMasiva('disable')} disabled={masivoBusy} className="btn btn-outline btn-sm"><IconBan />{traducir("Deshabilitar")}</button>
            <button onClick={() => accionMasiva('reset_password')} disabled={masivoBusy} className="btn btn-outline btn-sm"><IconKey />{traducir("Generar credenciales")}</button>
            <button onClick={() => accionMasiva('delete')} disabled={masivoBusy} className="btn btn-danger btn-sm"><IconTrash />{traducir("Eliminar")}</button>
            {masivoBusy && <IconSpinner className="animate-spin w-4 h-4 text-ink-3" />}
            <button onClick={() => setSelected(new Set())} className="text-sm text-ink-3 hover:text-ink-2 ml-1">
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
                <ThOrden clave="usuario" orden={orden} onClick={alternarOrden}>{traducir("Usuario")}</ThOrden>
                <ThOrden clave="origen" orden={orden} onClick={alternarOrden}>{traducir("Origen")}</ThOrden>
                <ThOrden clave="estado" orden={orden} onClick={alternarOrden}>{traducir("Estado")}</ThOrden>
                <ThOrden clave="conexion" orden={orden} onClick={alternarOrden}>{traducir("Conexión")}</ThOrden>
                <ThOrden clave="grupos" orden={orden} onClick={alternarOrden}>{traducir("Grupos")}</ThOrden>
                <ThOrden clave="cuota" orden={orden} onClick={alternarOrden}>{traducir("Cuota")}</ThOrden>
                <ThOrden clave="creado" orden={orden} onClick={alternarOrden}>{traducir("Creado")}</ThOrden>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {usuariosPagina.map(u => (
                <tr key={`${u.source}-${u.id}`} className="hover:bg-brand-50">
                  <td className="px-2 py-4">
                    <input type="checkbox" checked={selected.has(u.username)} onChange={() => toggleSelected(u.username)} />
                  </td>
                  <td className="px-6 py-4 font-medium text-ink">
                    <span className="inline-flex items-center gap-1.5">
                      {connectedUsers.has(u.username) && (
                        <span
                          className="w-1.5 h-1.5 rounded-full bg-ok flex-none"
                          title={traducir("Conectado ahora")}
                        />
                      )}
                      {u.username}
                    </span>
                    {u.display_name && (
                      <span className="block text-xs font-normal text-ink-3">{u.display_name}</span>
                    )}
                    {u.email && (
                      <span className="block text-xs font-normal text-ink-3">{u.email}</span>
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
                      {u.enabled ? traducir('Activo') : traducir('Inactivo')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {/* Columna aparte del punto verde de la columna "Usuario"
                        (ese es para el vistazo rápido al escanear la lista;
                        acá es un estado explícito, mismo criterio que la
                        columna "Estado" de al lado) -pedido en vivo,
                        2026-09-28. */}
                    <span className={`inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full ${
                      connectedUsers.has(u.username) ? 'pill-ok' : 'bg-line-soft text-ink-3'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full flex-none ${connectedUsers.has(u.username) ? 'bg-ok' : 'bg-ink-3'}`} />
                      {connectedUsers.has(u.username) ? traducir('En línea') : traducir('Desconectado')}
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
                          {cuota.quota_next_reset && (
                            <div className="text-[11px] text-ink-3">{traducir("Se restablece")} {formatFechaHora(cuota.quota_next_reset)}</div>
                          )}
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
                  <td className="px-6 py-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1">
                      {u.source === 'local' && (
                        <button onClick={() => setEditModalFor(u)}
                          className="btn-icon" title={traducir('Editar')}>
                          <IconEdit />
                        </button>
                      )}
                      <button onClick={() => handleToggle(u)}
                        disabled={isPending(u)}
                        className="btn-icon"
                        title={isPending(u) ? traducir('Aplicando…') : u.enabled ? traducir('Bloquea su acceso a internet hasta que lo habilites') : traducir('Permite que navegue a través del proxy')}>
                        {u.enabled ? <IconBan /> : <IconCheck />}
                      </button>
                      {u.source === 'local' && (
                        <>
                          <button onClick={() => setPasswordModalFor(u)}
                            disabled={isPending(u)}
                            className="btn-icon"
                            title={traducir("Genera una contraseña nueva, o establece una tú mismo")}>
                            <IconKey />
                          </button>
                          <button onClick={() => handleDelete(u)}
                            disabled={isPending(u)}
                            className="btn-icon btn-icon-danger"
                            title={isPending(u) ? traducir('Eliminando…') : traducir('Eliminar')}>
                            <IconTrash />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filteredUsers.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-6 py-12 text-center text-ink-3">
                    {allUsers.length === 0
                      ? traducir('No hay usuarios. Crea el primero o sincroniza LDAP.') : traducir('Ningún usuario coincide con el filtro.')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {filteredUsers.length > 0 && (
        <div className="mt-4">
          <Pagination pagina={pagina} totalPaginas={totalPaginas} total={filteredUsers.length}
            porPagina={USUARIOS_POR_PAGINA} onChange={setPagina} />
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

      {editModalFor && (
        <ModalEditarUsuario
          username={editModalFor.username}
          displayName={editModalFor.display_name ?? ''}
          email={editModalFor.email ?? ''}
          onClose={() => setEditModalFor(null)}
          onSave={async (displayName, email) => {
            await api.updateUser(editModalFor.id, { display_name: displayName || null, email })
            showToast(traducir('Usuario actualizado correctamente'))
            loadUsers()
          }}
        />
      )}

      {credenciales && <CredencialesModal credenciales={credenciales} onClose={() => setCredenciales(null)} />}

      {importarAbierto && (
        <ImportarUsuariosModal
          onClose={() => setImportarAbierto(false)}
          onImportado={(r) => {
            notificarCambioPendiente()
            loadUsers()
            showToast(traducir("Importación lista: {c} creados, {a} actualizados", { c: r.creados, a: r.actualizados }))
            if (r.credenciales.length) setCredenciales(r.credenciales)
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
