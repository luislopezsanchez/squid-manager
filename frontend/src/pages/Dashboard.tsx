import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { IconActivity, IconAlert, IconArrowDown, IconArrowUp, IconBackup, IconBolt, IconCheck, IconDashboard, IconGauge, IconLink, IconUsers, IconInfo } from '../components/Icons'
import { api, canWrite } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import { formatBytes, formatRate, formatNumber } from '../utils/format'
import { monotonePath, niceCeilBytes } from '../utils/chart'

interface TimelinePoint {
  time: string
  timestamp: number
  rx_bytes: number
  tx_bytes: number
  total_bytes: number
  requests: number
  denied: number
  connections: number
  mem_percent: number
  cache_hit_ratio: number | null
}

interface DashboardData {
  traffic: {
    rx_bytes_per_second: number
    tx_bytes_per_second: number
    total_bytes_per_second: number
    rx_avg_60s: number
    tx_avg_60s: number
    rx_total: number
    tx_total: number
    total_requests_60s: number
    denied_requests_60s: number
    requests_per_minute: number
    http_codes: { '2xx': number; '3xx': number; '4xx': number; '5xx': number; 'other': number }
    active_ips: string[]
    active_users: string[]
    cache_hits: number
    cache_misses: number
    cache_hit_ratio: number | null
    cache_bytes_saved: number
    latency_avg_ms: number | null
    latency_p50_ms: number | null
    latency_p95_ms: number | null
  }
  top_users: { user: string; bytes: number; requests: number }[]
  top_domains: { domain: string; requests: number; bytes: number }[]
  top_blocked: { domain: string; requests: number; bytes: number }[]
  top_blocked_users: {
    users: { user: string; blocked_requests: number; account_status: 'enabled' | 'disabled' | 'unknown' }[]
    anonymous_blocked: number
  }
  system: {
    cpu: { percent: number; load_1?: number; load_5?: number; load_15?: number }
    memory: { total: number; used: number; percent: number }
    disk: { total: number; used: number; free: number; percent: number }
    swap: { total: number; used: number; free: number; percent: number }
  }
  timeline: TimelinePoint[]
  connections: {
    time: string; ip: string; user: string; method: string
    domain: string; status: number; bytes: number; denied: boolean
  }[]
  squid_uptime: number | null
  quotas_en_riesgo: number
}

// monotonePath/niceCeilBytes se movieron a utils/chart.ts: Tendencias.tsx
// los necesita igual, y una segunda copia se hubiera podido desincronizar.

/** Tooltip de información: icono ℹ que muestra un texto al pasar el mouse.
 *  `position` controla si el tooltip aparece arriba o abajo del icono:
 *  las tarjetas de la fila superior están pegadas al borde del área de
 *  contenido, así que un tooltip hacia arriba se corta fuera de pantalla. */
function InfoTip({ text, position = 'top' }: { text: string; position?: 'top' | 'bottom' }) {
  const posClass = position === 'bottom'
    ? 'top-full mt-1.5'
    : 'bottom-full mb-1.5'
  return (
    <span className="relative inline-flex items-center group">
      <IconInfo className="w-3.5 h-3.5 text-ink-3 opacity-60 hover:opacity-100 cursor-help" />
      <span className={`absolute right-0 ${posClass} hidden group-hover:block
                       bg-brand-900 text-white text-xs px-3 py-2 rounded-lg
                       whitespace-normal shadow-lg z-30 pointer-events-none`}
            style={{ maxWidth: '280px', minWidth: '160px' }}>
        {text}
      </span>
    </span>
  )
}

/**
 * Mini gráfico de tendencia para las tarjetas de resumen.
 *
 * El valor instantáneo por sí solo no dice si el número viene subiendo,
 * bajando o lleva plano un rato; esta silueta es la que aporta ese contexto.
 */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) {
    return <div className="h-9 flex items-end text-[11px] text-ink-3">{traducir("Recogiendo datos…")}</div>
  }

  const max = Math.max(...values)
  const min = Math.min(...values)
  const range = max - min || 1
  const step = 100 / (values.length - 1)
  const points = values.map((v, i): [number, number] => [i * step, 100 - ((v - min) / range) * 92 - 4])
  const line = monotonePath(points)
  const area = `${line} L100,100 L0,100 Z`
  const gradId = `spark-${color.replace(/[^a-zA-Z0-9]/g, '')}`

  return (
    <svg className="w-full h-9" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke"
            strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

/** Indicador circular con múltiples segmentos, mismo estilo visual que Gauge.
 *  Mismas dimensiones (116px), mismo strokeWidth (9), misma tipografía y
 *  disposición del centro (icono + valor + label) y el detail debajo.
 *  La única diferencia: en vez de un arco de un color, varios arcos
 *  proporcionales cada uno con su color. Pensado para "Salud de las
 *  peticiones" — así coincide visualmente con CPU/RAM/Disco/SWAP. */
function MultiGauge({ segments, total, label, detail, Icon }: {
  segments: { count: number; color: string }[]
  total: number
  label: string
  detail: string
  Icon: (p: { className?: string }) => JSX.Element
}) {
  const size = 100
  const stroke = 9
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
                  stroke="var(--line-soft)" strokeWidth={stroke} />
          {total > 0 && segments.map((seg, i) => {
            if (seg.count === 0) return null
            const pct = seg.count / total
            const dash = pct * circumference
            const el = (
              <circle key={i} cx={size / 2} cy={size / 2} r={radius} fill="none"
                      stroke={seg.color} strokeWidth={stroke} strokeLinecap="round"
                      strokeDasharray={`${dash} ${circumference - dash}`}
                      strokeDashoffset={-offset}
                      style={{ transition: 'stroke-dasharray .6s ease' }} />
            )
            offset += dash
            return el
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span className="stat-icon" style={{ width: 22, height: 22 }}><Icon /></span>
          <span className="text-lg font-extrabold leading-none tabular" style={{ color: 'var(--ink)' }}>
            {formatNumber(total)}
          </span>
          <span className="text-[10px] font-semibold text-ink-3">{label}</span>
        </div>
      </div>
      {detail && <span className="text-[11px] text-ink-3 mt-2 tabular">{detail}</span>}
    </div>
  )
}

/** Formatea segundos de uptime como "Xd Yh Zm" o "Yh Zm" o "Zm". */
function formatUptime(segundos: number | null | undefined): string {
  if (segundos == null || segundos < 0) return '—'
  const d = Math.floor(segundos / 86400)
  const h = Math.floor((segundos % 86400) / 3600)
  const m = Math.floor((segundos % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [userSort, setUserSort] = useState<'bytes' | 'requests'>('bytes')
  const [dirty, setDirty] = useState(false)
  const [applying, setApplying] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { showToast, ToastContainer } = useToast()

  const loadData = () => {
    // Las métricas en vivo (tráfico, peticiones, conexiones, caché, sistema,
    // salud) salen del dashboard unificado, que lee los últimos 60s del
    // access.log y el buffer de network stats. Los rankings TOP, en cambio,
    // son acumulativos: con 60s casi siempre salen vacíos o con un único
    // registro. Por eso se piden SIEMPRE sobre las últimas 24h, sin selector
    // de tiempo que confunda -cada métrica usa la ventana que le conviene.
    Promise.all([
      api.getDashboard(),
      api.getTopUsers(10, '24h', 'bytes'),
      api.getTopDomains(10, false, '24h'),
      api.getTopDomains(10, true, '24h'),
      api.getTopBlockedUsers(10, '24h'),
    ]).then(([dash, users, domains, blocked, blockedUsers]) => {
      setData({
        ...dash,
        top_users: users,
        top_domains: domains,
        top_blocked: blocked,
        top_blocked_users: blockedUsers,
      })
      setLoadError(false)
    }).catch(e => {
      // Sin esto, un fallo (sesión vencida, red caída, timeout) dejaba
      // `data` en null para siempre: la pantalla se quedaba en "Cargando
      // métricas..." sin ningún aviso -solo se veía en la consola.
      console.error(e)
      setLoadError(true)
    }).finally(() => setLoading(false))
    // Se consulta aparte de /dashboard: es un dato de configuración, no de
    // tráfico, y conviene poder refrescarlo también justo después de aplicar
    // sin esperar al siguiente ciclo de las métricas.
    api.getPending().then(r => setDirty(r.dirty)).catch(() => {})
  }

  const handleApply = async () => {
    setApplying(true)
    try {
      const result = await api.applyConfig()
      if (result.status === 'ok') {
        setDirty(false)
      } else {
        // El backend rechazó el cambio (config inválida, DNS que no responde,
        // etc.) sin aplicar nada: "pending" sigue en true, así que había que
        // decir por qué en vez de solo volver a mostrar el mismo aviso sin
        // explicación -era exactamente lo que hacía este botón antes-.
        showToast(result.message, 'warning')
      }
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setApplying(false)
    }
  }

  useEffect(() => {
    loadData()
    if (autoRefresh) {
      intervalRef.current = setInterval(loadData, 5000)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [autoRefresh])

  if (loading) return <LoadingState text={traducir("Cargando métricas...")} />
  if (!data) return <ErrorState text={traducir("No se pudieron cargar las métricas del panel. Revisá la conexión o volvé a intentar.")} onRetry={loadData} />

  const t = data.traffic
  const s = data.system
  const timeline = data.timeline
  // Tope del eje redondeado, y nunca por debajo de 1 KB/s: con el proxy en
  // reposo la escala se calculaba sobre unos pocos bytes y las marcas salían
  // con cifras como "887.3 B/s", que no dicen nada.
  const maxBytes = niceCeilBytes(Math.max(...timeline.map(p => p.total_bytes), 0))

  // Series para los mini gráficos de las tarjetas de resumen.
  const sparkTraffic = timeline.map(p => p.total_bytes)
  const sparkRequests = timeline.map(p => p.requests)
  const sparkConnections = timeline.map(p => p.connections)
  // Los tramos sin peticiones cacheables llegan como null. Dibujarlos como 0
  // se ve como una caída real a "0% de aciertos", cuando en realidad no hubo
  // nada que cachear — así que se arrastra el último valor real conocido en
  // vez de cortar a cero; solo si TODAVÍA no hay ningún dato real se usa 0.
  const sparkCache: number[] = (() => {
    let ultimo = 0
    return timeline.map(p => {
      if (p.cache_hit_ratio !== null) ultimo = p.cache_hit_ratio
      return ultimo
    })
  })()

  // Ordenación explícita del top de usuarios: antes se mostraban las dos
  // cifras sin indicar cuál mandaba en el orden.
  const sortedUsers = [...data.top_users].sort((a, b) =>
    userSort === 'bytes' ? b.bytes - a.bytes : b.requests - a.requests
  )
  const topUserValue = Math.max(
    ...sortedUsers.map(u => (userSort === 'bytes' ? u.bytes : u.requests)), 1
  )

  // Puntos del gráfico de área: el ancho de banda es una magnitud continua,
  // así que se dibuja como área y no como barras sueltas.
  //
  // La posición horizontal sale del instante de cada muestra, no de su índice:
  // las muestras se toman cuando el panel consulta, y si se espacian de forma
  // irregular repartirlas por igual desplazaría los picos en el tiempo.
  const spanStart = timeline.length ? timeline[0].timestamp : 0
  const spanEnd = timeline.length ? timeline[timeline.length - 1].timestamp : 0
  const span = spanEnd - spanStart || 1
  const xFor = (p: TimelinePoint, i: number) =>
    span > 1 ? ((p.timestamp - spanStart) / span) * 100 : (i / Math.max(timeline.length - 1, 1)) * 100

  const chartPath = (key: 'rx_bytes' | 'tx_bytes') => {
    if (timeline.length < 2) return { line: '', area: '' }
    const pts = timeline.map((p, i): [number, number] => [xFor(p, i), 100 - (p[key] / maxBytes) * 100])
    const line = monotonePath(pts)
    return { line, area: `${line} L100,100 L0,100 Z` }
  }
  const rxPath = chartPath('rx_bytes')
  const txPath = chartPath('tx_bytes')

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-2xl font-bold" style={{ color: '#0A2C48' }}>{traducir("Dashboard")}</h1>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Sistema, versión minimalista: permanente en el header, en todas
              las resoluciones -ya no existe una tarjeta "Sistema" aparte (ver
              el comentario en la fila de Tráfico, más abajo), así que este es
              el único lugar donde se muestran estos datos. Los mismos iconos
              que ya usan los gauges que tenía esa tarjeta, sin el color
              por-métrica: a este tamaño (14px) un círculo de progreso no se
              lee, así que se prioriza el número. */}
          <div className="flex items-center gap-2.5 text-ink-3 text-xs bg-line-soft border border-line rounded-full px-3 py-1.5">
            <span className="flex items-center gap-1">
              <IconBolt className="w-3.5 h-3.5" />
              <span className="font-bold text-ink-2 tabular">{s.cpu.percent}%</span>
              <span className="text-[10px]">CPU</span>
            </span>
            <span className="w-px h-3.5 bg-line" />
            <span className="flex items-center gap-1">
              <IconActivity className="w-3.5 h-3.5" />
              <span className="font-bold text-ink-2 tabular">{s.memory.percent}%</span>
              <span className="text-[10px]">RAM</span>
            </span>
            <span className="w-px h-3.5 bg-line" />
            <span className="flex items-center gap-1">
              <IconBackup className="w-3.5 h-3.5" />
              <span className="font-bold text-ink-2 tabular">{s.disk.percent}%</span>
              <span className="text-[10px]">{traducir("Disco")}</span>
            </span>
            {s.swap && s.swap.total > 0 && (
              <>
                <span className="w-px h-3.5 bg-line" />
                <span className="flex items-center gap-1">
                  <IconActivity className="w-3.5 h-3.5" />
                  <span className="font-bold text-ink-2 tabular">{s.swap.percent}%</span>
                  <span className="text-[10px]">SWAP</span>
                </span>
              </>
            )}
            <span className="w-px h-3.5 bg-line" />
            <span className="flex items-center gap-1">
              <IconCheck className="w-3.5 h-3.5" />
              <span className="font-bold text-ink-2 tabular">{formatUptime(data.squid_uptime)}</span>
            </span>
          </div>

          {autoRefresh && (
            <span className="flex items-center gap-1 text-xs text-ok">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>{traducir("EN VIVO")}</span>
          )}
          <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded"
              style={{ accentColor: '#0B497C' }}
            />{traducir("Auto-actualizar (5s)")}</label>
        </div>
      </div>

      {/* Aviso de refresco fallido: si ya había datos en pantalla, un fallo
          puntual (red, timeout) no debe tirar todo el dashboard -se sigue
          mostrando lo último conocido, solo se avisa que no es lo más
          reciente. El caso "nunca cargó" no llega acá: ese corta antes,
          ver el `if (!data)` de más arriba. */}
      {loadError && (
        <div className="card p-3 mb-6 flex items-center gap-2 border text-sm"
             style={{ borderColor: 'var(--warn)', background: 'var(--warn-soft)' }}>
          <span className="flex-none" style={{ color: 'var(--warn)' }}><IconAlert className="w-4 h-4" /></span>
          <span style={{ color: 'var(--warn)' }}>{traducir("No se pudo actualizar el panel; mostrando los últimos datos conocidos.")}</span>
        </div>
      )}

      {/* Aviso de cambios sin aplicar: la barra lateral ya lo indica en todo
          momento, pero aquí es donde se nota si algo dejó de reflejarse en
          el tráfico real — vale la pena repetirlo en el punto donde se mira
          primero. */}
      {dirty && (
        <div className="card p-4 mb-6 flex items-center gap-3 border"
             style={{ borderColor: 'var(--warn)', background: 'var(--warn-soft)' }}>
          <span className="stat-icon flex-none" style={{ background: 'transparent', color: 'var(--warn)' }}>
            <IconAlert />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold" style={{ color: 'var(--warn)' }}>{traducir("Hay cambios sin aplicar")}</p>
            <p className="text-xs text-ink-2">{traducir("Algo se modificó (ACLs, reglas, grupos o configuración) y todavía no se aplicó a Squid: lo que ves en este dashboard puede no coincidir con lo que el proxy está usando ahora mismo.")}</p>
          </div>
          {canWrite() && (
            <button
              onClick={handleApply}
              disabled={applying}
              className="flex-none px-4 py-2 rounded-lg text-sm font-bold text-white transition disabled:opacity-60"
              style={{ background: 'var(--warn)' }}
            >
              {applying ? traducir('Aplicando…') : traducir('Aplicar ahora')}
            </button>
          )}
        </div>
      )}

      {/* Aviso de cuotas por agotarse: solo aparece si hay alguien en esa
          situación -a diferencia de las 4 tarjetas de arriba, que siempre
          se muestran, esto ocuparía espacio en blanco la mayor parte del
          tiempo si fuera una tarjeta fija. */}
      {data.quotas_en_riesgo > 0 && (
        <Link to="/users" className="card p-4 mb-6 flex items-center gap-3 border hover:brightness-95 transition"
              style={{ borderColor: 'var(--warn)', background: 'var(--warn-soft)' }}>
          <span className="stat-icon flex-none" style={{ background: 'transparent', color: 'var(--warn)' }}>
            <IconUsers />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold" style={{ color: 'var(--warn)' }}>
              {data.quotas_en_riesgo === 1
                ? traducir("1 usuario está por agotar su cuota de navegación")
                : traducir("{n} usuarios están por agotar su cuota de navegación", { n: data.quotas_en_riesgo })}
            </p>
            <p className="text-xs text-ink-2">{traducir("Ya consumieron 80% o más de su límite del periodo. Ver en Gestión → Usuarios.")}</p>
          </div>
        </Link>
      )}

      {/* Métricas principales - 5 tarjetas con tendencia.
          Con un grid de columnas fijas (1/2/3/5), 5 tarjetas nunca reparten
          parejo salvo en 1 o 5 columnas: en el rango intermedio (p.ej. una
          laptop de 1366px, que cae justo en 3 columnas) sobra media fila
          vacía -eso es lo que se veía "deformado". Con flex-wrap en cambio
          cada fila se reparte el ancho disponible entre las tarjetas que
          entran en ELLA, así que una fila incompleta (2 tarjetas, o 1 sola)
          se estira para ocupar todo el ancho en vez de dejar un hueco -se
          ve bien en cualquier resolución sin tener que afinar breakpoints
          a mano para este número impar de tarjetas. */}
      {/* Por debajo de 2xl (1536px) las 5 tarjetas se achican en vez de
          amontonarse en menos columnas: min-w bajó de 230 a 150 (entran las
          5 sin envolver en el ancho de una laptop), padding/tipografía/icono
          se reducen con 2xl: y el sparkline se oculta -es lo que más espacio
          pedía y, a diferencia del número, no es algo que se pierda de
          vista: la tendencia real está en el gráfico grande de más abajo.
          El corte es 2xl y no xl a propósito: a un ancho apenas mayor a
          1280px (ej. 1300-1400px) el modo "completo" (texto sm, icono
          32px) no entraba cómodo -el título se cortaba con "..." o, peor,
          envolvía a dos líneas de forma dispareja entre tarjetas. Recién a
          partir de 1536px hay margen real para el tamaño completo; entre
          1280 y 1536 estas tarjetas siguen compactas aunque la fila de
          Tráfico+Sistema de abajo (que corta en xl) ya haya pasado a dos
          columnas -son anchos disponibles distintos (1/5 de la fila acá,
          2/5 allá), así que no tienen por qué compartir el mismo corte. */}
      <div className="flex flex-wrap gap-4 mb-6">
        <div className="card border border-line-soft flex-1 min-w-[150px] max-w-[380px] p-3 2xl:p-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <h3 className="text-[11px] 2xl:text-sm text-ink-3 truncate 2xl:whitespace-normal 2xl:overflow-visible 2xl:text-clip">{traducir("Tráfico actual")}</h3>
              <InfoTip position="bottom" text={traducir("Velocidad de datos que pasa por el proxy ahora mismo: bajada (del Internet hacia los clientes) y subida (de los clientes hacia Internet). El gráfico muestra la tendencia de los últimos minutos.")} />
            </div>
            <span className="stat-icon w-6 h-6 2xl:w-8 2xl:h-8 [&>svg]:w-3 [&>svg]:h-3 2xl:[&>svg]:w-[17px] 2xl:[&>svg]:h-[17px]"><IconDashboard /></span>
          </div>
          <p className="text-lg 2xl:text-2xl font-bold tabular truncate" style={{ color: '#0B497C' }}>{formatRate(t.total_bytes_per_second)}</p>
          <div className="hidden 2xl:block"><Sparkline values={sparkTraffic} color="#0B497C" /></div>
          <div className="flex justify-between text-[10px] 2xl:text-xs text-ink-3 gap-1">
            <span className="flex items-center gap-1 truncate"><IconArrowDown className="w-3 h-3 flex-none" />{formatRate(t.rx_bytes_per_second)}</span>
            <span className="flex items-center gap-1 truncate"><IconArrowUp className="w-3 h-3 flex-none" />{formatRate(t.tx_bytes_per_second)}</span>
          </div>
        </div>

        <div className="card border border-line-soft flex-1 min-w-[150px] max-w-[380px] p-3 2xl:p-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <h3 className="text-[11px] 2xl:text-sm text-ink-3 truncate 2xl:whitespace-normal 2xl:overflow-visible 2xl:text-clip">{traducir("Peticiones (60s)")}</h3>
              <InfoTip position="bottom" text={traducir("Cuántas solicitudes HTTP procesó el proxy en el último minuto. RPM = peticiones por minuto. OK = sirvió sin denegar; denegadas = bloqueadas por política de acceso (403/407).")} />
            </div>
            <span className="stat-icon w-6 h-6 2xl:w-8 2xl:h-8 [&>svg]:w-3 [&>svg]:h-3 2xl:[&>svg]:w-[17px] 2xl:[&>svg]:h-[17px]"><IconGauge /></span>
          </div>
          <p className="text-lg 2xl:text-2xl font-bold tabular truncate" style={{ color: '#2E93BC' }}>{formatNumber(t.total_requests_60s)}</p>
          <div className="hidden 2xl:block"><Sparkline values={sparkRequests} color="#2E93BC" /></div>
          <p className="text-[10px] 2xl:text-xs text-ink-3 truncate">
            {traducir("{ok} OK · {denegadas} denegadas", {
              ok: t.total_requests_60s - t.denied_requests_60s,
              denegadas: t.denied_requests_60s,
            })}
            <span className="ml-2 text-ink-2 font-medium">{formatNumber(t.requests_per_minute)} {traducir("rpm")}</span>
          </p>
        </div>

        <div className="card border border-line-soft flex-1 min-w-[150px] max-w-[380px] p-3 2xl:p-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <h3 className="text-[11px] 2xl:text-sm text-ink-3 truncate 2xl:whitespace-normal 2xl:overflow-visible 2xl:text-clip">{traducir("Conexiones activas")}</h3>
              <InfoTip position="bottom" text={traducir("Direcciones IP distintas que generaron tráfico en el último minuto. «Autenticados» son las que enviaron un usuario válido: una IP puede tener tráfico sin usuario (ruido de fondo del navegador) por eso son números distintos.")} />
            </div>
            <span className="stat-icon w-6 h-6 2xl:w-8 2xl:h-8 [&>svg]:w-3 [&>svg]:h-3 2xl:[&>svg]:w-[17px] 2xl:[&>svg]:h-[17px]"><IconLink /></span>
          </div>
          <p className="text-lg 2xl:text-2xl font-bold tabular truncate" style={{ color: '#0A2C48' }}>{t.active_ips.length}</p>
          <div className="hidden 2xl:block"><Sparkline values={sparkConnections} color="#0A2C48" /></div>
          {/* "IPs" y "autenticados" son poblaciones distintas: una IP puede
              generar tráfico entero sin que ninguna petición traiga un
              usuario válido (típico del ruido de fondo del navegador). Decir
              "N usuarios" ahí sugería que era un subconjunto del número de
              arriba, y "1 conexión · 0 usuarios" se leía como contradicción. */}
          <p className="text-[10px] 2xl:text-xs text-ink-3 truncate">
            {traducir(
              t.active_ips.length === 1
                ? "1 IP · {n} autenticados"
                : "{ips} IPs · {n} autenticados",
              { ips: t.active_ips.length, n: t.active_users.length },
            )}
          </p>
        </div>

        {/* Aciertos de caché: es la métrica que dice si el proxy está
            ahorrando tráfico de verdad, que es su razón de ser. Ocupa el sitio
            de la RAM del proxy, que ya se muestra en la tarjeta Sistema. */}
        <div className="card border border-line-soft flex-1 min-w-[150px] max-w-[380px] p-3 2xl:p-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <h3 className="text-[11px] 2xl:text-sm text-ink-3 truncate 2xl:whitespace-normal 2xl:overflow-visible 2xl:text-clip">{traducir("Aciertos de caché (60s)")}</h3>
              <InfoTip position="bottom" text={traducir("Porcentaje de peticiones que Squid sirvió desde su caché sin ir a Internet. Más alto = menos tráfico saliente y respuestas más rápidas. «Sin peticiones cacheables» significa que no hubo contenido cacheable, no que la caché falle.")} />
            </div>
            <span className="stat-icon w-6 h-6 2xl:w-8 2xl:h-8 [&>svg]:w-3 [&>svg]:h-3 2xl:[&>svg]:w-[17px] 2xl:[&>svg]:h-[17px]"><IconBolt /></span>
          </div>
          {/* Igual que el resto de las tarjetas: sin datos se muestra como 0,
              no con un símbolo especial. El subtítulo de abajo ya aclara que
              es "sin peticiones cacheables" y no un acierto real del 0%. */}
          <p className="text-lg 2xl:text-2xl font-bold tabular truncate" style={{ color: '#2F9E75' }}>
            {t.cache_hit_ratio ?? 0}%
          </p>
          <div className="hidden 2xl:block"><Sparkline values={sparkCache} color="#2F9E75" /></div>
          <p className="text-[10px] 2xl:text-xs text-ink-3 tabular truncate">
            {t.cache_hit_ratio === null
              ? traducir("Sin peticiones cacheables")
              : traducir("{hits} desde caché · {fallos} al origen", {
                  hits: t.cache_hits,
                  fallos: t.cache_misses,
                })}
          </p>
        </div>

        {/* Tarjeta "Salud de las peticiones" con MultiGauge: mismo estilo
            visual que los gauges de Sistema (size=100, stroke=9,
            strokeLinecap round, icono + valor + label en el centro, detail
            debajo). La leyenda va a la derecha, vertical, para aprovechar el
            ancho de la tarjeta en la fila de 5. */}
        <div className="card border border-line-soft flex-1 min-w-[150px] max-w-[380px] flex flex-col p-3 2xl:p-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <h3 className="text-[11px] 2xl:text-sm text-ink-3 truncate 2xl:whitespace-normal 2xl:overflow-visible 2xl:text-clip">{traducir("Salud de las peticiones")}</h3>
              <InfoTip position="bottom" text={traducir("Resultado de las peticiones del último minuto. Verde (2xx) = correctas. Azul (3xx) = redirecciones. Amarillo (4xx) = error del cliente o bloqueo. Rojo (5xx) = el servidor falló.")} />
            </div>
            <span className="stat-icon w-6 h-6 2xl:w-8 2xl:h-8 [&>svg]:w-3 [&>svg]:h-3 2xl:[&>svg]:w-[17px] 2xl:[&>svg]:h-[17px]"><IconActivity /></span>
          </div>
          {(() => {
            const total = t.total_requests_60s
            const segments = [
              { count: t.http_codes['2xx'], color: '#2F9E75' },
              { count: t.http_codes['3xx'], color: '#48B3D0' },
              { count: t.http_codes['4xx'], color: '#E0A036' },
              { count: t.http_codes['5xx'], color: '#C0392F' },
              { count: t.http_codes.other, color: '#95A5A6' },
            ]
            if (total === 0) {
              return <div className="flex-1 grid place-items-center text-sm text-ink-3 py-6">{traducir("Sin peticiones")}</div>
            }
            {/* "Otros" (sin código de respuesta: conexión cortada antes de
                tiempo, cliente que aborta, etc.) se dibuja en el anillo
                (color #95A5A6, ver `segments` arriba) pero antes no tenía
                fila propia acá ni entraba en el resumen "OK · errores" de
                abajo -el total del centro no cerraba con lo que se veía
                listado, como si esas peticiones hubieran desaparecido. */}
            const legendItems = [
              { label: '2xx', desc: 'OK', count: t.http_codes['2xx'], color: '#2F9E75' },
              { label: '3xx', desc: traducir('Redir.'), count: t.http_codes['3xx'], color: '#48B3D0' },
              { label: '4xx', desc: traducir('Cliente'), count: t.http_codes['4xx'], color: '#E0A036' },
              { label: '5xx', desc: traducir('Servidor'), count: t.http_codes['5xx'], color: '#C0392F' },
              { label: traducir('Otros'), desc: traducir('Sin código'), count: t.http_codes.other, color: '#95A5A6' },
            ].filter(s => s.count > 0)
            const okCount = t.http_codes['2xx'] + t.http_codes['3xx']
            const errCount = t.http_codes['4xx'] + t.http_codes['5xx']

            return (
              <>
                {/* Compacta (debajo de xl): el anillo con leyenda no entra en
                    una tarjeta tan angosta -mismo criterio que el resto de la
                    fila, número grande + un resumen de una sola línea. */}
                <div className="2xl:hidden">
                  <p className="text-lg font-bold tabular truncate" style={{ color: 'var(--ink)' }}>{formatNumber(total)}</p>
                  <p className="flex items-center gap-1 text-[10px] text-ink-3 mt-1 truncate">
                    <span className="w-1.5 h-1.5 rounded-full flex-none" style={{ background: '#2F9E75' }} />
                    <span className="tabular">{okCount} OK</span>
                    {errCount > 0 && (
                      <>
                        <span className="w-1.5 h-1.5 rounded-full flex-none ml-1" style={{ background: '#C0392F' }} />
                        <span className="tabular">{errCount} {traducir("err")}</span>
                      </>
                    )}
                  </p>
                </div>

                {/* Completa (xl y más ancho): anillo + leyenda, como ya estaba. */}
                <div className="hidden 2xl:flex items-center gap-2 flex-1">
                  <MultiGauge
                    segments={segments}
                    total={total}
                    label={traducir("peticiones")}
                    detail=""
                    Icon={IconActivity}
                  />
                  {/* Leyenda vertical a la derecha + resumen al pie */}
                  <div className="flex flex-col gap-1.5 text-[11px] flex-1 min-w-0">
                    {legendItems.map(s => (
                      <div key={s.label} className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-sm flex-none" style={{ backgroundColor: s.color }} />
                        <span className="font-medium text-ink-2 tabular">{s.label}</span>
                        <span className="text-ink-3 text-[10px] truncate">{s.desc}</span>
                        <span className="ml-auto font-semibold tabular text-ink">{s.count}</span>
                      </div>
                    ))}
                    <div className="mt-1 pt-1.5 border-t border-line-soft text-[10px] text-ink-3 tabular">
                      {okCount} {traducir("OK")} · {errCount} {traducir("errores")}
                      {t.http_codes.other > 0 && <> · {t.http_codes.other} {traducir("otros")}</>}
                    </div>
                  </div>
                </div>
              </>
            )
          })()}
        </div>
      </div>

      {/* Tráfico de red en tiempo real: ancho completo.
          Antes compartía esta fila con la tarjeta "Sistema" (CPU/RAM/Disco/
          SWAP). Esa tarjeta se sacó de acá: sus datos ahora viven de forma
          permanente en el header, junto a "EN VIVO" (ver más arriba) -en
          cualquier resolución, no solo en las angostas. El espacio que
          liberó queda pendiente: cuando se implementen las mejoras de
          Análisis, conviene revisar qué KPI de esa sección tiene sentido
          traer acá, al lado del gráfico, en vez de dejarlo vacío para
          siempre. */}
      <div className="card p-6 flex flex-col mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-1.5">
              <h3 className="font-medium text-ink">{traducir("Tráfico de red en tiempo real")}</h3>
              <InfoTip text={traducir("Velocidad de datos que pasa por el proxy en los últimos minutos. Bajada = del Internet hacia los clientes. Subida = de los clientes hacia Internet. Cada punto es una muestra tomada cada 5 segundos.")} />
            </div>
            <span className="text-xs text-ink-3 tabular">
              {traducir("Promedio: bajada {bajada} · subida {subida}", {
                bajada: formatRate(t.rx_avg_60s),
                subida: formatRate(t.tx_avg_60s),
              })}
            </span>
          </div>

          <div className="flex gap-2" style={{ height: '220px' }}>
            {/* Eje Y */}
            <div className="flex flex-col justify-between text-[10px] text-ink-3 font-mono text-right pr-1" style={{ width: '64px' }}>
              <span>{formatRate(maxBytes)}</span>
              <span>{formatRate(maxBytes * 0.75)}</span>
              <span>{formatRate(maxBytes * 0.5)}</span>
              <span>{formatRate(maxBytes * 0.25)}</span>
              <span>0</span>
            </div>

            {/* Área del gráfico */}
            <div className="relative flex-1 overflow-hidden">
              {/* Rejilla */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
                {[0, 1, 2, 3, 4].map(i => (
                  <div key={i} className="border-t border-line-soft w-full" style={{ height: '0' }} />
                ))}
              </div>

              {timeline.length < 2 ? (
                <div className="absolute inset-0 grid place-items-center text-sm text-ink-3">{traducir("Recogiendo datos…")}</div>
              ) : (
                <>
                  <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100"
                       preserveAspectRatio="none" aria-hidden="true">
                    <defs>
                      <linearGradient id="rxGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#0B497C" stopOpacity="0.30" />
                        <stop offset="100%" stopColor="#0B497C" stopOpacity="0.03" />
                      </linearGradient>
                      <linearGradient id="txGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#48B3D0" stopOpacity="0.30" />
                        <stop offset="100%" stopColor="#48B3D0" stopOpacity="0.03" />
                      </linearGradient>
                    </defs>
                    <path d={rxPath.area} fill="url(#rxGrad)" />
                    <path d={rxPath.line} fill="none" stroke="#0B497C" strokeWidth="2"
                          vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
                    <path d={txPath.area} fill="url(#txGrad)" />
                    <path d={txPath.line} fill="none" stroke="#48B3D0" strokeWidth="2"
                          vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
                  </svg>

                  {/* Capa invisible para los tooltips: cada zona se coloca sobre
                      la posición real de su muestra, no repartida por igual. */}
                  <div className="absolute inset-0">
                    {timeline.map((point, i) => {
                      const x = xFor(point, i)
                      const width = 100 / timeline.length
                      return (
                        <div
                          key={i}
                          className="absolute top-0 h-full group"
                          style={{ left: `${Math.max(0, x - width / 2)}%`, width: `${width}%` }}
                        >
                          <div className="absolute inset-y-0 left-1/2 w-px bg-brand-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block bg-brand-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-20 pointer-events-none">
                            {point.time}<br />
                            Bajada {formatRate(point.rx_bytes)}<br />
                            Subida {formatRate(point.tx_bytes)}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Eje temporal: el rango sale de las marcas reales de las muestras. */}
          <div className="flex justify-between text-xs text-ink-3 mt-2 pl-[72px]">
            <span>{span > 90
              ? traducir("Hace {n} min", { n: Math.round(span / 60) })
              : traducir("Hace {n} s", { n: Math.round(span) })}</span>
            <span>{traducir("Ahora")}</span>
          </div>

          {/* Leyenda */}
          <div className="flex gap-4 mt-3 text-xs items-center">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#0B497C' }}></span>{traducir("Bajada")}</span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#48B3D0' }}></span>{traducir("Subida")}</span>
            <span className="text-ink-3 ml-auto tabular">
              {traducir("{puntos} puntos · {segundos}s de histórico", {
                puntos: timeline.length,
                segundos: Math.round(span),
              })}
            </span>
          </div>
        </div>


      {/* Top usuarios + Top dominios + Top bloqueados + Top usuarios bloqueados */}
      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-4 gap-4 mb-6">
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <h3 className="font-medium text-ink">{traducir("Top usuarios")}</h3>
              <InfoTip text={traducir("Quién consume más ancho de banda o hace más peticiones. Un consumo alto no es necesariamente un problema, pero es el primer lugar donde mirar si el enlace va lento o si conviene revisar una cuota.")} />
            </div>
            {/* El criterio de orden era ambiguo: se mostraban bytes y peticiones
                sin decir cuál mandaba. Ahora se elige y se ve cuál está activo. */}
            <div className="flex text-xs rounded-md overflow-hidden border border-line">
              <button
                onClick={() => setUserSort('bytes')}
                className={`px-2 py-0.5 transition ${userSort === 'bytes' ? 'bg-brand-700 text-white' : 'text-ink-3 hover:bg-brand-50'}`}
              >{traducir("Datos")}</button>
              <button
                onClick={() => setUserSort('requests')}
                className={`px-2 py-0.5 transition ${userSort === 'requests' ? 'bg-brand-700 text-white' : 'text-ink-3 hover:bg-brand-50'}`}
              >{traducir("Peticiones")}</button>
            </div>
          </div>
          <p className="text-[11px] text-ink-3 mb-4">
            {userSort === 'bytes'
              ? traducir("Ordenado por datos transferidos · últimas 24 horas")
              : traducir("Ordenado por número de peticiones · últimas 24 horas")}
          </p>
          {sortedUsers.length === 0 ? (
            <p className="text-sm text-ink-3">{traducir("Sin datos")}</p>
          ) : (
            <div className="space-y-3">
              {sortedUsers.map((u, i) => {
                const value = userSort === 'bytes' ? u.bytes : u.requests
                const share = (value / topUserValue) * 100
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white flex-none" style={{ backgroundColor: '#0B497C' }}>{i + 1}</span>
                        <span className="font-medium truncate">{u.user}</span>
                      </div>
                      <div className="text-right flex-none ml-2">
                        <span className="font-semibold tabular">
                          {userSort === 'bytes' ? formatBytes(u.bytes) : `${u.requests} req`}
                        </span>
                        <span className="text-xs text-ink-3 ml-2 tabular">
                          {userSort === 'bytes' ? `${u.requests} req` : formatBytes(u.bytes)}
                        </span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-line-soft rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-500"
                           style={{ width: `${share}%`, backgroundColor: '#48B3D0' }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <h3 className="font-medium text-ink">{traducir("Top sitios visitados")}</h3>
              <InfoTip text={traducir("Qué dominios se piden más veces. Sirve para decidir con datos reales si vale la pena sumar una ACL nueva: si algo no productivo aparece seguido aquí, es candidato a bloquear.")} />
            </div>
          </div>
          <p className="text-[11px] text-ink-3 mb-4">{traducir("Por número de peticiones · últimas 24 horas")}</p>
          {data.top_domains.length === 0 ? (
            <p className="text-sm text-ink-3">{traducir("Sin datos")}</p>
          ) : (
            <div className="space-y-2">
              {data.top_domains.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white flex-none" style={{ backgroundColor: '#48B3D0' }}>{i + 1}</span>
                    <span className="font-mono text-xs truncate">{d.domain}</span>
                  </div>
                  <span className="text-xs text-ink-3 ml-2 tabular flex-none">{d.requests}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <h3 className="font-medium text-ink">{traducir("Top sitios bloqueados")}</h3>
              <InfoTip text={traducir("Contra qué dominios está chocando la política de acceso ahora mismo. Si un dominio se repite mucho, la regla que lo bloquea está funcionando de verdad, no es solo teoría en la configuración.")} />
            </div>
          </div>
          <p className="text-[11px] text-ink-3 mb-4">{traducir("Por número de bloqueos · últimas 24 horas")}</p>
          {data.top_blocked.length === 0 ? (
            <p className="text-sm text-ink-3">{traducir("Sin bloqueos")}</p>
          ) : (
            <div className="space-y-2">
              {data.top_blocked.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white bg-red-500 flex-none">{i + 1}</span>
                    <span className="font-mono text-xs truncate">{d.domain}</span>
                  </div>
                  <span className="text-xs text-ink-3 ml-2 tabular flex-none">{d.requests}x</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Complementa a "Top sitios bloqueados": esa dice QUÉ se bloquea,
            esta dice QUIÉN choca más con la política.

            Ojo con el nombre: esto cuenta PETICIONES DENEGADAS (407/403), no
            "cuentas bloqueadas". Son cosas distintas que comparten la palabra
            "bloqueado" por casualidad del idioma — una petición puede
            denegarse por credenciales viejas cacheadas en el navegador o por
            una política de grupo, sin que la cuenta esté deshabilitada. Por
            eso cada fila lleva una insignia con el estado REAL de la cuenta,
            cruzado contra Usuarios, para no dejar la duda. */}
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <h3 className="font-medium text-ink">{traducir("Usuarios con más peticiones denegadas")}</h3>
              <InfoTip text={traducir("Quién insiste más contra la política. Unos pocos bloqueos son ruido normal (un enlace viejo, una redirección). Una cifra alta y sostenida de la misma persona sí amerita revisar su acceso. No implica que la cuenta esté deshabilitada: las denegaciones pueden ser por credenciales viejas o por política de grupo.")} />
            </div>
          </div>
          <p className="text-[11px] text-ink-3 mb-4">{traducir("Últimas 24 horas · no implica que la cuenta esté deshabilitada")}</p>
          {data.top_blocked_users.users.length === 0 ? (
            <p className="text-sm text-ink-3">{traducir("Sin peticiones denegadas")}</p>
          ) : (
            <div className="space-y-2">
              {data.top_blocked_users.users.map((u, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white bg-red-500 flex-none">{i + 1}</span>
                    <span className="font-medium truncate">{u.user}</span>
                    {u.account_status === 'disabled' && (
                      <span className="pill-danger px-1.5 py-0.5 text-[10px] font-semibold rounded-full flex-none"
                            title={traducir("La cuenta está deshabilitada en Usuarios: por eso no navega, no solo por estos intentos")}>{traducir("cuenta deshabilitada")}</span>
                    )}
                  </div>
                  <span className="text-xs text-ink-3 ml-2 tabular flex-none">{u.blocked_requests}x</span>
                </div>
              ))}
            </div>
          )}
          {/* La mayoría de los bloqueos suele venir de tráfico de fondo del
              navegador (telemetría, sondas de conectividad) que nunca manda
              credenciales — sin esta línea, la diferencia con "Top sitios
              bloqueados" se lee como que esta tarjeta está mal, no como lo
              que es: la mayoría de esos bloqueos no tiene usuario. */}
          {data.top_blocked_users.anonymous_blocked > 0 && (
            <p className="text-[11px] text-ink-3 mt-3 pt-3 border-t border-line-soft">
              {traducir(
                "+ {n} bloqueos sin usuario identificado (tráfico de fondo del navegador, sin credenciales)",
                { n: data.top_blocked_users.anonymous_blocked },
              )}
            </p>
          )}
        </div>
      </div>

      {/* Últimas conexiones */}
      <div className="card overflow-hidden">
        <div className="flex items-center gap-1.5 p-6 pb-4">
          <h3 className="font-medium text-ink">{traducir("Últimas conexiones")}</h3>
          <InfoTip text={traducir("Las peticiones más recientes registradas en el access.log de Squid. Cada fila es una transacción completa: qué IP la hizo, qué usuario (si se autenticó), a qué dominio fue, el código de respuesta y cuántos datos se transfirieron.")} />
        </div>
        <div className="overflow-x-auto">
          <table className="table-panel">
            <thead className="bg-brand-50 border-y border-line-soft">
              <tr>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Hora")}</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">IP</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Usuario")}</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Dominio")}</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Estado")}</th>
                <th className="text-right px-6 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Bytes")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.connections.map((c, i) => (
                <tr key={i} className="hover:bg-brand-50">
                  <td className="px-6 py-2 text-xs text-ink-3 font-mono">{c.time}</td>
                  <td className="px-6 py-2 text-xs font-mono text-ink-2">{c.ip}</td>
                  <td className="px-6 py-2 text-xs font-medium">{c.user}</td>
                  <td className="px-6 py-2 text-xs font-mono text-ink-2 max-w-xs truncate">{c.domain}</td>
                  <td className="px-6 py-2">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                      c.denied ? 'pill-danger' : 'pill-ok'
                    }`}>{c.status}</span>
                  </td>
                  <td className="px-6 py-2 text-right text-xs font-mono text-ink-3">{formatBytes(c.bytes)}</td>
                </tr>
              ))}
              {data.connections.length === 0 && (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-ink-3">{traducir("Sin conexiones recientes")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
