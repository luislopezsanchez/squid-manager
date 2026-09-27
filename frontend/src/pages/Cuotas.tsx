import { traducir } from '../i18n'
import { useEffect, useMemo, useState } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import Modal from '../components/Modal'
import { formatBytes } from '../utils/format'
import { TAMANO_UNITS, VELOCIDAD_UNITS, PERIODO_LABELS, detectarUnidad } from '../utils/quotaUnits'

// Cuota individual (por usuario, local o LDAP) -mismo modelo que ya
// gestiona ProxyUsers.tsx, se lee de la misma API acá para unificarla en
// una sola vista con las de grupo (pool compartido).
interface UserQuota {
  id: number
  username: string
  quota_bytes: number
  quota_period: 'daily' | 'weekly' | 'monthly'
  quota_action: 'cut' | 'throttle'
  quota_throttle_bytes_per_sec: number | null
  quota_bytes_used: number
  quota_period_started_at: string | null
  quota_action_applied: boolean
}

// Pool compartido de un grupo entero -ver app/models/group_quota.py: solo
// admite grupos locales, porque un grupo LDAP no tiene una lista de
// miembros consultable localmente.
interface GroupQuota {
  id: number
  group_name: string
  quota_bytes: number
  quota_period: 'daily' | 'weekly' | 'monthly'
  quota_action: 'cut' | 'throttle'
  quota_throttle_bytes_per_sec: number | null
  quota_bytes_used: number
  quota_period_started_at: string | null
  quota_action_applied: boolean
}

interface Group {
  id: number
  name: string
  source: string
  members: string[]
}

type Fila =
  | { tipo: 'usuario'; nombre: string; cuota: UserQuota }
  | { tipo: 'grupo'; nombre: string; cuota: GroupQuota; miembros: number }

type Filtro = 'todas' | 'usuario' | 'grupo'

function estadoDe(cuota: { quota_action_applied: boolean; quota_action: string }): 'cortada' | 'limitada' | 'activa' {
  if (!cuota.quota_action_applied) return 'activa'
  return cuota.quota_action === 'throttle' ? 'limitada' : 'cortada'
}

function PillEstado({ estado }: { estado: 'cortada' | 'limitada' | 'activa' }) {
  const clases = estado === 'cortada' ? 'pill-danger' : estado === 'limitada' ? 'pill-warn' : 'pill-ok'
  const texto = estado === 'cortada' ? traducir('Cortada') : estado === 'limitada' ? traducir('Limitada') : traducir('Activa')
  return <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${clases}`}>{texto}</span>
}

function BarraConsumo({ usado, total }: { usado: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (usado / total) * 100) : 0
  return (
    <div>
      <div className="text-xs text-ink-3 mb-1 tabular">{formatBytes(usado)} / {formatBytes(total)}</div>
      <div className="w-full h-1.5 bg-line-soft rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${usado >= total ? 'bg-danger' : pct > 80 ? 'bg-warn' : 'bg-ok'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

/**
 * Formulario de "+ Nueva cuota": el primer paso es elegir si es por
 * usuario o por grupo -cambia qué se puede elegir como objetivo (un
 * nombre de usuario suelto vs. un grupo local existente) pero comparte el
 * resto de los campos (tamaño, periodo, acción). Igual patrón visual que
 * QuotaModal de ProxyUsers.tsx.
 */
function CuotaFormModal({ existente, usuariosDisponibles, gruposLocales, onClose, onSave, onRemove }: {
  existente?: Fila
  usuariosDisponibles: string[]
  gruposLocales: Group[]
  onClose: () => void
  onSave: (args: {
    tipo: 'usuario' | 'grupo'; nombre: string
    data: { quota_bytes: number; quota_period: string; quota_action: string; quota_throttle_bytes_per_sec?: number }
  }) => Promise<void>
  onRemove?: () => Promise<void>
}) {
  const [tipo, setTipo] = useState<'usuario' | 'grupo'>(existente?.tipo || 'usuario')
  const [nombre, setNombre] = useState(existente?.nombre || '')
  const cuotaExistente = existente?.cuota
  const tamanoUnidadInicial = cuotaExistente ? detectarUnidad(cuotaExistente.quota_bytes, TAMANO_UNITS) : 1073741824
  const [tamano, setTamano] = useState(
    cuotaExistente ? Math.round((cuotaExistente.quota_bytes / tamanoUnidadInicial) * 100) / 100 : 5
  )
  const [tamanoUnidad, setTamanoUnidad] = useState(tamanoUnidadInicial)
  const [periodo, setPeriodo] = useState(cuotaExistente?.quota_period || 'monthly')
  const [accion, setAccion] = useState(cuotaExistente?.quota_action || 'cut')
  const velocidadUnidadInicial = cuotaExistente?.quota_throttle_bytes_per_sec
    ? detectarUnidad(cuotaExistente.quota_throttle_bytes_per_sec, VELOCIDAD_UNITS)
    : 1024
  const [velocidad, setVelocidad] = useState(
    cuotaExistente?.quota_throttle_bytes_per_sec
      ? Math.round((cuotaExistente.quota_throttle_bytes_per_sec / velocidadUnidadInicial) * 100) / 100
      : 128
  )
  const [velocidadUnidad, setVelocidadUnidad] = useState(velocidadUnidadInicial)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const esEdicion = !!existente

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    if (!nombre.trim()) { setErr(tipo === 'usuario' ? traducir('Elegí un usuario.') : traducir('Elegí un grupo.')); return }
    setBusy(true)
    try {
      await onSave({
        tipo, nombre: nombre.trim(),
        data: {
          quota_bytes: Math.round(tamano * tamanoUnidad),
          quota_period: periodo,
          quota_action: accion,
          quota_throttle_bytes_per_sec: accion === 'throttle' ? Math.round(velocidad * velocidadUnidad) : undefined,
        },
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
    <Modal
      onClose={onClose}
      maxWidth="max-w-xl"
      title={esEdicion
        ? traducir('Editar cuota de "{n}"', { n: existente!.nombre })
        : traducir('Nueva cuota de navegación')}
    >
      <form onSubmit={handleSubmit}>
        {!esEdicion && (
          <div className="field">
            <span className="field-label block mb-1.5">{traducir("Tipo")}</span>
            <div className="flex gap-2 mb-2">
              <button type="button"
                onClick={() => { setTipo('usuario'); setNombre('') }}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border ${tipo === 'usuario' ? 'border-brand-700 bg-brand-50 text-brand-700' : 'border-line'}`}>
                {traducir("Por usuario")}
              </button>
              <button type="button"
                onClick={() => { setTipo('grupo'); setNombre('') }}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border ${tipo === 'grupo' ? 'border-brand-700 bg-brand-50 text-brand-700' : 'border-line'}`}>
                {traducir("Por grupo (pool compartido)")}
              </button>
            </div>
          </div>
        )}

        <div className="field">
          <label htmlFor="cuota-nombre" className="field-label">
            {tipo === 'usuario' ? traducir("Usuario") : traducir("Grupo local")}
          </label>
          {esEdicion ? (
            <input id="cuota-nombre" className="input" value={nombre} disabled />
          ) : tipo === 'usuario' ? (
            <input id="cuota-nombre" className="input" list="cuotas-usuarios-datalist" value={nombre}
              onChange={e => setNombre(e.target.value)} placeholder={traducir("Nombre de usuario")} autoFocus required />
          ) : (
            <select id="cuota-nombre" className="input" value={nombre} onChange={e => setNombre(e.target.value)} required>
              <option value="">{traducir("Elegí un grupo…")}</option>
              {gruposLocales.map(g => <option key={g.id} value={g.name}>{g.name} ({g.members.length})</option>)}
            </select>
          )}
          {!esEdicion && tipo === 'usuario' && (
            <datalist id="cuotas-usuarios-datalist">
              {usuariosDisponibles.map(u => <option key={u} value={u} />)}
            </datalist>
          )}
          {!esEdicion && tipo === 'grupo' && gruposLocales.length === 0 && (
            <p className="field-help mt-1">{traducir("No hay grupos locales creados todavía (Gestión → Grupos).")}</p>
          )}
        </div>

        <div className="field">
          <label htmlFor="cuota-size" className="field-label">{traducir("Tamaño de la cuota")}</label>
          <div className="flex gap-2">
            <input id="cuota-size" type="number" min="0.1" step="0.1" value={tamano}
              onChange={e => setTamano(parseFloat(e.target.value) || 0)} className="input flex-1" required />
            <select value={tamanoUnidad} onChange={e => setTamanoUnidad(parseInt(e.target.value))} className="input w-28">
              {TAMANO_UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          {tipo === 'grupo' && (
            <p className="field-help mt-1">{traducir("Este cupo se comparte entre todos los integrantes del grupo, no es por persona.")}</p>
          )}
        </div>
        <div className="field">
          <label htmlFor="cuota-period" className="field-label">{traducir("Periodo")}</label>
          <select id="cuota-period" value={periodo} onChange={e => setPeriodo(e.target.value as any)} className="input">
            <option value="daily">{traducir("Diario")}</option>
            <option value="weekly">{traducir("Semanal")}</option>
            <option value="monthly">{traducir("Mensual")}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="cuota-action" className="field-label">{traducir("Al agotarse")}</label>
          <select id="cuota-action" value={accion} onChange={e => setAccion(e.target.value as any)} className="input">
            <option value="cut">
              {tipo === 'grupo' ? traducir("Deshabilitar a todos los integrantes") : traducir("Cortar la navegación hasta el próximo periodo")}
            </option>
            <option value="throttle">{traducir("Limitar la velocidad en vez de cortar")}</option>
          </select>
        </div>
        {accion === 'throttle' && (
          <div className="field">
            <label htmlFor="cuota-throttle" className="field-label">{traducir("Velocidad límite")}</label>
            <div className="flex gap-2">
              <input id="cuota-throttle" type="number" min="1" step="1" value={velocidad}
                onChange={e => setVelocidad(parseFloat(e.target.value) || 0)} className="input flex-1" required />
              <select value={velocidadUnidad} onChange={e => setVelocidadUnidad(parseInt(e.target.value))} className="input w-28">
                {VELOCIDAD_UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
          </div>
        )}
        {err && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
        <div className="flex gap-2 mt-2">
          {esEdicion && onRemove && (
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
    </Modal>
  )
}

/** "Aplicar por miembro": crea/reemplaza la MISMA cuota individual a cada
 * integrante actual del grupo, en vez de compartir un único pool -reusa
 * el endpoint /api/quotas/bulk que ya existe, sin backend nuevo. */
function AplicarPorMiembroModal({ grupo, onClose, onApplied }: {
  grupo: Group
  onClose: () => void
  onApplied: (mensaje: string) => void
}) {
  const [tamano, setTamano] = useState(1)
  const [tamanoUnidad, setTamanoUnidad] = useState(1073741824)
  const [periodo, setPeriodo] = useState('monthly')
  const [accion, setAccion] = useState('cut')
  const [velocidad, setVelocidad] = useState(128)
  const [velocidadUnidad, setVelocidadUnidad] = useState(1024)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    if (grupo.members.length === 0) { setErr(traducir("Este grupo no tiene integrantes.")); return }
    setBusy(true)
    try {
      const result = await api.setQuotaBulk(grupo.members, {
        quota_bytes: Math.round(tamano * tamanoUnidad),
        quota_period: periodo,
        quota_action: accion,
        quota_throttle_bytes_per_sec: accion === 'throttle' ? Math.round(velocidad * velocidadUnidad) : undefined,
      })
      notificarCambioPendiente()
      onApplied(traducir("Cuota aplicada a {n} de {t} integrantes.", { n: result.aplicadas.length, t: grupo.members.length }))
      onClose()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal onClose={onClose} maxWidth="max-w-xl" title={traducir('Aplicar cuota individual a cada integrante de "{n}"', { n: grupo.name })}>
      <p className="text-sm text-ink-3 mb-4">
        {traducir("A diferencia del pool compartido, acá cada integrante recibe su PROPIA cuota (no comparten un único cupo). Reemplaza la cuota individual que ya tuviera cada uno.")}
      </p>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="bulk-size" className="field-label">{traducir("Tamaño de la cuota, por persona")}</label>
          <div className="flex gap-2">
            <input id="bulk-size" type="number" min="0.1" step="0.1" value={tamano}
              onChange={e => setTamano(parseFloat(e.target.value) || 0)} className="input flex-1" required />
            <select value={tamanoUnidad} onChange={e => setTamanoUnidad(parseInt(e.target.value))} className="input w-28">
              {TAMANO_UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="bulk-period" className="field-label">{traducir("Periodo")}</label>
          <select id="bulk-period" value={periodo} onChange={e => setPeriodo(e.target.value)} className="input">
            <option value="daily">{traducir("Diario")}</option>
            <option value="weekly">{traducir("Semanal")}</option>
            <option value="monthly">{traducir("Mensual")}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="bulk-action" className="field-label">{traducir("Al agotarse")}</label>
          <select id="bulk-action" value={accion} onChange={e => setAccion(e.target.value)} className="input">
            <option value="cut">{traducir("Cortar la navegación hasta el próximo periodo")}</option>
            <option value="throttle">{traducir("Limitar la velocidad en vez de cortar")}</option>
          </select>
        </div>
        {accion === 'throttle' && (
          <div className="field">
            <label htmlFor="bulk-throttle" className="field-label">{traducir("Velocidad límite")}</label>
            <div className="flex gap-2">
              <input id="bulk-throttle" type="number" min="1" step="1" value={velocidad}
                onChange={e => setVelocidad(parseFloat(e.target.value) || 0)} className="input flex-1" required />
              <select value={velocidadUnidad} onChange={e => setVelocidadUnidad(parseInt(e.target.value))} className="input w-28">
                {VELOCIDAD_UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
          </div>
        )}
        {err && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
        <div className="flex gap-2 mt-2">
          <button type="button" onClick={onClose} disabled={busy}
            className="flex-1 px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">
            {traducir("Cancelar")}
          </button>
          <button type="submit" disabled={busy} className="flex-1 btn btn-primary disabled:opacity-50">
            {busy ? traducir('Aplicando…') : traducir('Aplicar a {n} integrantes', { n: grupo.members.length })}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function Cuotas() {
  const [userQuotas, setUserQuotas] = useState<UserQuota[]>([])
  const [groupQuotas, setGroupQuotas] = useState<GroupQuota[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [usuariosDisponibles, setUsuariosDisponibles] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [filtro, setFiltro] = useState<Filtro>('todas')
  const [search, setSearch] = useState('')
  const [formFor, setFormFor] = useState<Fila | 'nueva' | null>(null)
  const [bulkFor, setBulkFor] = useState<Group | null>(null)
  const { showToast, ToastContainer } = useToast()

  const load = () => {
    Promise.all([
      api.listQuotas().catch(() => []),
      api.listGroupQuotas().catch(() => []),
      api.listGroups().catch(() => []),
      api.listUsers().catch(() => []),
      api.listLdapUsers().catch(() => []),
    ]).then(([uq, gq, gr, local, ldap]) => {
      setUserQuotas(uq)
      setGroupQuotas(gq)
      setGroups(gr)
      setUsuariosDisponibles([
        ...local.map((u: any) => u.username),
        ...ldap.map((u: any) => u.username),
      ])
      setLoadError(false)
    }).catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  // Refresco corto en segundo plano: el consumo de cada cuota cambia con
  // la navegación de quien la tiene, no con nada que el admin haga en esta
  // página -sin esto, la barra de cada fila quedaba desactualizada hasta
  // que se recargaba la página a mano (ver quota_service._tick, corre cada
  // pocos segundos del lado del backend). `load()` ya es "silencioso" para
  // llamadas después de la primera: `loading` solo se pone en true en el
  // useState inicial, nunca de nuevo, así que un refresco de fondo no hace
  // parpadear la pantalla ni molesta si hay un modal abierto.
  useEffect(() => {
    load()
    const interval = setInterval(load, 8000)
    return () => clearInterval(interval)
  }, [])

  const filas: Fila[] = useMemo(() => {
    const gruposPorNombre = new Map(groups.map(g => [g.name, g]))
    return [
      ...userQuotas.map((cuota): Fila => ({ tipo: 'usuario', nombre: cuota.username, cuota })),
      ...groupQuotas.map((cuota): Fila => ({
        tipo: 'grupo', nombre: cuota.group_name, cuota,
        miembros: gruposPorNombre.get(cuota.group_name)?.members.length ?? 0,
      })),
    ]
  }, [userQuotas, groupQuotas, groups])

  const term = search.trim().toLowerCase()
  // Ordenadas por consumo (más cerca del límite primero): en una empresa
  // con muchas cuotas configuradas, lo urgente de mirar es quién está por
  // agotarla, no el orden alfabético en que se crearon.
  const filasFiltradas = filas
    .filter(f => {
      if (filtro !== 'todas' && f.tipo !== filtro) return false
      if (term && !f.nombre.toLowerCase().includes(term)) return false
      return true
    })
    .sort((a, b) => {
      const ratio = (f: Fila) => f.cuota.quota_bytes > 0 ? f.cuota.quota_bytes_used / f.cuota.quota_bytes : 0
      return ratio(b) - ratio(a)
    })

  const enRiesgo = filas.filter(f => {
    const c = f.cuota
    return !c.quota_action_applied && c.quota_bytes > 0 && c.quota_bytes_used / c.quota_bytes >= 0.8
  }).length
  const activasAhora = filas.filter(f => f.cuota.quota_action_applied).length

  const gruposLocales = groups.filter(g => g.source === 'local')
  const gruposLocalesSinCuota = gruposLocales.filter(g => !groupQuotas.some(gq => gq.group_name === g.name))

  const handleSave = async (args: {
    tipo: 'usuario' | 'grupo'; nombre: string
    data: { quota_bytes: number; quota_period: string; quota_action: string; quota_throttle_bytes_per_sec?: number }
  }) => {
    if (args.tipo === 'usuario') await api.setQuota(args.nombre, args.data)
    else await api.setGroupQuota(args.nombre, args.data)
    notificarCambioPendiente()
    showToast(traducir("Cuota guardada correctamente"))
    load()
  }

  const handleRemove = async (fila: Fila) => {
    if (fila.tipo === 'usuario') await api.removeQuota(fila.nombre)
    else await api.removeGroupQuota(fila.nombre)
    notificarCambioPendiente()
    showToast(traducir("Cuota quitada correctamente"))
    load()
  }

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Cuotas de navegación")}</h1>
          <p className="page-sub">{traducir("Límites de consumo por usuario o compartidos por un grupo entero")}</p>
        </div>
        <button onClick={() => setFormFor('nueva')} className="btn btn-primary">{traducir('+ Nueva cuota')}</button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="card p-4">
          <p className="text-xs text-ink-3 mb-1">{traducir("Cuotas configuradas")}</p>
          <p className="text-2xl font-bold text-ink">{filas.length}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-ink-3 mb-1">{traducir("En riesgo (≥80%)")}</p>
          <p className={`text-2xl font-bold ${enRiesgo > 0 ? 'text-warn' : 'text-ink'}`}>{enRiesgo}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-ink-3 mb-1">{traducir("Cortadas o limitadas ahora")}</p>
          <p className={`text-2xl font-bold ${activasAhora > 0 ? 'text-danger' : 'text-ink'}`}>{activasAhora}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex gap-1 bg-line-soft/60 rounded-lg p-1">
          {(['todas', 'usuario', 'grupo'] as Filtro[]).map(f => (
            <button key={f} onClick={() => setFiltro(f)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${filtro === f ? 'bg-white shadow-sm text-brand-700' : 'text-ink-3 hover:text-ink-2'}`}>
              {f === 'todas' ? traducir('Todas') : f === 'usuario' ? traducir('Por usuario') : traducir('Por grupo')}
            </button>
          ))}
        </div>
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder={traducir("Buscar por nombre de usuario o de grupo…")}
          className="input flex-1 min-w-[200px] max-w-sm" />
      </div>

      {loading ? (
        <LoadingState />
      ) : loadError && filas.length === 0 ? (
        <ErrorState onRetry={load} />
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left">{traducir("Nombre")}</th>
                <th className="text-left">{traducir("Tipo")}</th>
                <th className="text-left">{traducir("Consumo")}</th>
                <th className="text-left">{traducir("Periodo")}</th>
                <th className="text-left">{traducir("Al agotarse")}</th>
                <th className="text-left">{traducir("Estado")}</th>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {filasFiltradas.map(fila => (
                <tr key={`${fila.tipo}-${fila.nombre}`}>
                  <td className="px-5 py-3 font-medium text-ink">
                    {fila.nombre}
                    {fila.tipo === 'grupo' && (
                      <span className="text-ink-3 font-normal"> · {traducir("{n} integrantes", { n: fila.miembros })}</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-sm text-ink-2">
                    {fila.tipo === 'usuario' ? traducir('Usuario') : traducir('Grupo (compartido)')}
                  </td>
                  <td className="px-5 py-3 min-w-[160px]">
                    <BarraConsumo usado={fila.cuota.quota_bytes_used} total={fila.cuota.quota_bytes} />
                  </td>
                  <td className="px-5 py-3 text-sm">{PERIODO_LABELS[fila.cuota.quota_period] || fila.cuota.quota_period}</td>
                  <td className="px-5 py-3 text-sm">
                    {fila.cuota.quota_action === 'throttle' ? traducir('Limitar velocidad') : traducir('Cortar')}
                  </td>
                  <td className="px-5 py-3"><PillEstado estado={estadoDe(fila.cuota)} /></td>
                  <td className="px-5 py-3 text-right space-x-3 whitespace-nowrap">
                    {fila.tipo === 'grupo' && (
                      <button onClick={() => setBulkFor(groups.find(g => g.name === fila.nombre) || null)}
                        className="text-brand-700 hover:underline text-sm font-medium">
                        {traducir("Por miembro…")}
                      </button>
                    )}
                    <button onClick={() => setFormFor(fila)} className="text-brand-700 hover:underline text-sm font-medium">
                      {traducir("Editar")}
                    </button>
                  </td>
                </tr>
              ))}
              {filasFiltradas.length === 0 && (
                <tr><td colSpan={7} className="px-5 py-12 text-center text-ink-3">
                  {filas.length === 0
                    ? traducir("No hay ninguna cuota de navegación configurada todavía.")
                    : traducir("Ninguna cuota coincide con el filtro.")}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {formFor && (
        <CuotaFormModal
          existente={formFor === 'nueva' ? undefined : formFor}
          usuariosDisponibles={usuariosDisponibles}
          gruposLocales={formFor === 'nueva' ? gruposLocalesSinCuota : gruposLocales}
          onClose={() => setFormFor(null)}
          onSave={handleSave}
          onRemove={formFor !== 'nueva' ? () => handleRemove(formFor) : undefined}
        />
      )}
      {bulkFor && (
        <AplicarPorMiembroModal
          grupo={bulkFor}
          onClose={() => setBulkFor(null)}
          onApplied={(mensaje) => { showToast(mensaje); load() }}
        />
      )}
    </div>
  )
}
