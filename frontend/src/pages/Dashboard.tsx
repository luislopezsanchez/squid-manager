import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { IconActivity, IconAlert, IconArrowDown, IconArrowUp, IconBackup, IconBolt, IconDashboard, IconGauge, IconLink } from '../components/Icons'
import { api, canWrite } from '../api/client'
import { useToast } from '../components/Toast'
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
  }
  timeline: TimelinePoint[]
  connections: {
    time: string; ip: string; user: string; method: string
    domain: string; status: number; bytes: number; denied: boolean
  }[]
}

// monotonePath/niceCeilBytes se movieron a utils/chart.ts: Tendencias.tsx
// los necesita igual, y una segunda copia se hubiera podido desincronizar.

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

/** Indicador circular para las tres constantes vitales del sistema. */
function Gauge({ value, label, detail, color, Icon }: {
  value: number
  label: string
  detail: string
  color: string
  Icon: (p: { className?: string }) => JSX.Element
}) {
  const size = 116
  const stroke = 9
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  // El arco se limita a 100, pero el número muestra el valor real: la CPU
  // puede pasar del 100% cuando usa más de un núcleo.
  const arc = Math.max(0, Math.min(value, 100))

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
                  stroke="var(--line-soft)" strokeWidth={stroke} />
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
                  stroke={color} strokeWidth={stroke} strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={circumference - (arc / 100) * circumference}
                  style={{ transition: 'stroke-dashoffset .6s ease' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span className="stat-icon" style={{ width: 26, height: 26 }}><Icon /></span>
          <span className="text-xl font-extrabold leading-none tabular" style={{ color: 'var(--ink)' }}>
            {value}%
          </span>
          <span className="text-[11px] font-semibold text-ink-3">{label}</span>
        </div>
      </div>
      <span className="text-[11px] text-ink-3 mt-2 tabular">{detail}</span>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [userSort, setUserSort] = useState<'bytes' | 'requests'>('bytes')
  const [dirty, setDirty] = useState(false)
  const [applying, setApplying] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { showToast, ToastContainer } = useToast()

  const loadData = () => {
    api.getDashboard().then(setData).catch(console.error).finally(() => setLoading(false))
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

  if (loading || !data) return <div className="p-8 text-center text-ink-3">{traducir("Cargando métricas...")}</div>

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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#0A2C48' }}>{traducir("Dashboard")}</h1>
        <div className="flex items-center gap-4">
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
              {applying ? 'Aplicando…' : 'Aplicar ahora'}
            </button>
          )}
        </div>
      )}

      {/* Métricas principales - 4 tarjetas con tendencia */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm text-ink-3">{traducir("Tráfico actual")}</h3>
            <span className="stat-icon"><IconDashboard /></span>
          </div>
          <p className="text-2xl font-bold tabular" style={{ color: '#0B497C' }}>{formatRate(t.total_bytes_per_second)}</p>
          <Sparkline values={sparkTraffic} color="#0B497C" />
          <div className="flex justify-between text-xs text-ink-3">
            <span className="flex items-center gap-1"><IconArrowDown className="w-3 h-3" />{formatRate(t.rx_bytes_per_second)}</span>
            <span className="flex items-center gap-1"><IconArrowUp className="w-3 h-3" />{formatRate(t.tx_bytes_per_second)}</span>
          </div>
        </div>

        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm text-ink-3">{traducir("Peticiones (60s)")}</h3>
            <span className="stat-icon"><IconGauge /></span>
          </div>
          <p className="text-2xl font-bold tabular" style={{ color: '#2E93BC' }}>{formatNumber(t.total_requests_60s)}</p>
          <Sparkline values={sparkRequests} color="#2E93BC" />
          <p className="text-xs text-ink-3">
            {traducir("{ok} OK · {denegadas} denegadas", {
              ok: t.total_requests_60s - t.denied_requests_60s,
              denegadas: t.denied_requests_60s,
            })}
          </p>
        </div>

        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm text-ink-3">{traducir("Conexiones activas")}</h3>
            <span className="stat-icon"><IconLink /></span>
          </div>
          <p className="text-2xl font-bold tabular" style={{ color: '#0A2C48' }}>{t.active_ips.length}</p>
          <Sparkline values={sparkConnections} color="#0A2C48" />
          {/* "IPs" y "autenticados" son poblaciones distintas: una IP puede
              generar tráfico entero sin que ninguna petición traiga un
              usuario válido (típico del ruido de fondo del navegador). Decir
              "N usuarios" ahí sugería que era un subconjunto del número de
              arriba, y "1 conexión · 0 usuarios" se leía como contradicción. */}
          <p className="text-xs text-ink-3">
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
        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm text-ink-3">{traducir("Aciertos de caché (60s)")}</h3>
            <span className="stat-icon"><IconBolt /></span>
          </div>
          {/* Igual que el resto de las tarjetas: sin datos se muestra como 0,
              no con un símbolo especial. El subtítulo de abajo ya aclara que
              es "sin peticiones cacheables" y no un acierto real del 0%. */}
          <p className="text-2xl font-bold tabular" style={{ color: '#2F9E75' }}>
            {t.cache_hit_ratio ?? 0}%
          </p>
          <Sparkline values={sparkCache} color="#2F9E75" />
          <p className="text-xs text-ink-3 tabular">
            {t.cache_hit_ratio === null
              ? traducir("Sin peticiones cacheables")
              : traducir("{hits} desde caché · {fallos} al origen", {
                  hits: t.cache_hits,
                  fallos: t.cache_misses,
                })}
          </p>
        </div>
      </div>

      {/* Gráfico de tráfico + Sistema */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-ink">{traducir("Tráfico de red en tiempo real")}</h3>
            <span className="text-xs text-ink-3 tabular">
              {traducir("Promedio: bajada {bajada} · subida {subida}", {
                bajada: formatRate(t.rx_avg_60s),
                subida: formatRate(t.tx_avg_60s),
              })}
            </span>
          </div>

          <div className="flex gap-2" style={{ height: '192px' }}>
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

        {/* Sistema */}
        <div className="card p-6">
          <h3 className="font-medium text-ink mb-5">{traducir("Sistema")}</h3>
          <div className="grid grid-cols-3 gap-2">
            <Gauge
              value={s.cpu.percent}
              label="CPU"
              detail={s.cpu.load_1 !== undefined
                ? traducir("carga {n}", { n: s.cpu.load_1.toFixed(2) })
                : ''}
              color="#0B497C"
              Icon={IconBolt}
            />
            <Gauge
              value={s.memory.percent}
              label="RAM"
              detail={formatBytes(s.memory.used)}
              color={s.memory.percent > 80 ? '#C0392F' : '#48B3D0'}
              Icon={IconActivity}
            />
            <Gauge
              value={s.disk.percent}
              label={traducir("Disco")}
              detail={s.disk.total > 0 ? formatBytes(s.disk.used) : 'n/d'}
              color={s.disk.percent > 80 ? '#C0392F' : '#2F9E75'}
              Icon={IconBackup}
            />
          </div>

          <div className="pt-4 mt-4 border-t border-line-soft text-xs text-ink-3 space-y-1 tabular">
            <div>RAM: {formatBytes(s.memory.used)} / {formatBytes(s.memory.total)}</div>
            {s.disk.total > 0 && <div>{traducir("Disco: {usado} / {total}", {
              usado: formatBytes(s.disk.used),
              total: formatBytes(s.disk.total),
            })}</div>}
            <div>{traducir("Total transferido: bajada {bajada} · subida {subida}", {
              bajada: formatBytes(t.rx_total),
              subida: formatBytes(t.tx_total),
            })}</div>
            {/* Latencia de respuesta: el mejor indicador de si el proxy va
                lento. Se excluyen los túneles CONNECT (HTTPS) porque ahí el
                tiempo medido es la duración de la conexión, no la respuesta. */}
            <div>
              {t.latency_p50_ms === null
                ? traducir("Latencia: sin datos")
                : traducir("Latencia: mediana {p50} ms · p95 {p95} ms", {
                    p50: t.latency_p50_ms,
                    // El p95 puede faltar aunque haya mediana. Antes se
                    // interpolaba un null y salía «p95  ms», con el hueco.
                    p95: t.latency_p95_ms ?? '—',
                  })}
            </div>
          </div>
        </div>
      </div>

      {/* Top usuarios + Top dominios + Top bloqueados + Top usuarios bloqueados */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <div className="card p-6">
          <div className="flex items-baseline justify-between mb-1">
            <h3 className="font-medium text-ink">{traducir("Top usuarios")}</h3>
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
              ? traducir("Ordenado por datos transferidos · últimas 1.000 peticiones")
              : traducir("Ordenado por número de peticiones · últimas 1.000 peticiones")}
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
          <h3 className="font-medium text-ink mb-1">{traducir("Top sitios visitados")}</h3>
          <p className="text-[11px] text-ink-3 mb-4">{traducir("Por número de peticiones · últimas 1.000")}</p>
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
          <h3 className="font-medium text-ink mb-1">{traducir("Top sitios bloqueados")}</h3>
          <p className="text-[11px] text-ink-3 mb-4">{traducir("Por número de bloqueos · últimas 1.000")}</p>
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
          <h3 className="font-medium text-ink mb-1">{traducir("Usuarios con más peticiones denegadas")}</h3>
          <p className="text-[11px] text-ink-3 mb-4">{traducir("Últimas 1.000 · no implica que la cuenta esté deshabilitada")}</p>
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
        <h3 className="font-medium text-ink p-6 pb-4">{traducir("Últimas conexiones")}</h3>
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
