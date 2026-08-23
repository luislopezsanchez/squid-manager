import { useState, useEffect, useRef } from 'react'
import { IconArrowDown, IconArrowUp, IconAudit, IconBackup, IconDashboard, IconGauge, IconLink, IconLock, IconRules, IconSettings, IconTag, IconUsers } from '../components/Icons'
import { api } from '../api/client'
import { useNavigate } from 'react-router-dom'

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
  }
  top_users: { user: string; bytes: number; requests: number }[]
  top_domains: { domain: string; requests: number; bytes: number }[]
  top_blocked: { domain: string; requests: number; bytes: number }[]
  system: {
    cpu: { percent: number; load_1?: number; load_5?: number; load_15?: number }
    memory: { total: number; used: number; percent: number }
    disk: { total: number; used: number; free: number; percent: number }
  }
  timeline: { time: string; rx_bytes: number; tx_bytes: number; total_bytes: number }[]
  connections: {
    time: string; ip: string; user: string; method: string
    domain: string; status: number; bytes: number; denied: boolean
  }[]
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatRate(bytesPerSec: number): string {
  if (bytesPerSec === 0) return '0 B/s'
  return formatBytes(bytesPerSec) + '/s'
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toString()
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const navigate = useNavigate()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = () => {
    api.getDashboard().then(setData).catch(console.error).finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
    if (autoRefresh) {
      intervalRef.current = setInterval(loadData, 5000)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [autoRefresh])

  if (loading || !data) return <div className="p-8 text-center text-ink-3">Cargando métricas...</div>

  const t = data.traffic
  const s = data.system
  const timeline = data.timeline
  const maxBytes = Math.max(...timeline.map(p => p.total_bytes), 1)

  return (
    <div className="p-6 md:p-7">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#0A2C48' }}>Dashboard</h1>
        <div className="flex items-center gap-4">
          {autoRefresh && (
            <span className="flex items-center gap-1 text-xs text-ok">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
              EN VIVO
            </span>
          )}
          <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded"
              style={{ accentColor: '#0B497C' }}
            />
            Auto-actualizar (5s)
          </label>
        </div>
      </div>

      {/* Métricas principales - 4 tarjetas */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-ink-3">Tráfico actual</h3>
            <span className="stat-icon"><IconDashboard /></span>
          </div>
          <p className="text-2xl font-bold" style={{ color: '#0B497C' }}>{formatRate(t.total_bytes_per_second)}</p>
          <div className="flex justify-between text-xs text-ink-3 mt-1">
            <span className="flex items-center gap-1"><IconArrowDown className="w-3 h-3" />{formatRate(t.rx_bytes_per_second)}</span>
            <span className="flex items-center gap-1"><IconArrowUp className="w-3 h-3" />{formatRate(t.tx_bytes_per_second)}</span>
          </div>
        </div>

        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-ink-3">Peticiones (60s)</h3>
            <span className="stat-icon"><IconGauge /></span>
          </div>
          <p className="text-2xl font-bold" style={{ color: '#48B3D0' }}>{formatNumber(t.total_requests_60s)}</p>
          <p className="text-xs text-ink-3 mt-1">
            {t.total_requests_60s - t.denied_requests_60s} OK / {t.denied_requests_60s} denegadas
          </p>
        </div>

        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-ink-3">Conexiones activas</h3>
            <span className="stat-icon"><IconLink /></span>
          </div>
          <p className="text-2xl font-bold" style={{ color: '#0A2C48' }}>{t.active_ips.length}</p>
          <p className="text-xs text-ink-3 mt-1">{t.active_users.length} usuarios</p>
        </div>

        <div className="card p-5 border border-line-soft">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-ink-3">RAM del proxy</h3>
            <span className="stat-icon"><IconBackup /></span>
          </div>
          <p className="text-2xl font-bold" style={{ color: s.memory.percent > 80 ? '#dc2626' : '#0B497C' }}>
            {s.memory.percent}%
          </p>
          <p className="text-xs text-ink-3 mt-1">{formatBytes(s.memory.used)} / {formatBytes(s.memory.total)}</p>
        </div>
      </div>

      {/* Gráfico de tráfico + Sistema */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Gráfico de tráfico - barras finas, más puntos */}
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-ink">Tráfico de red en tiempo real</h3>
            <span className="text-xs text-ink-3">
              Promedio: bajada {formatRate(t.rx_avg_60s)} · subida {formatRate(t.tx_avg_60s)}
            </span>
          </div>

          {/* Gráfico con eje Y */}
          <div className="flex gap-2" style={{ height: '192px' }}>
            {/* Eje Y - marcas de escala */}
            <div className="flex flex-col justify-between text-[10px] text-ink-3 font-mono text-right pr-1" style={{ width: '60px' }}>
              <span>{formatRate(maxBytes)}</span>
              <span>{formatRate(maxBytes * 0.75)}</span>
              <span>{formatRate(maxBytes * 0.5)}</span>
              <span>{formatRate(maxBytes * 0.25)}</span>
              <span>0</span>
            </div>

            {/* Área del gráfico */}
            <div className="relative flex-1 overflow-hidden">
              {/* Líneas horizontales de referencia */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
                {[0, 1, 2, 3, 4].map(i => (
                  <div key={i} className="border-t border-line-soft w-full" style={{ height: '0' }} />
                ))}
              </div>

              {/* Barras */}
              <div className="flex items-end justify-end h-full gap-px relative">
                {timeline.map((point, i) => {
                  const total = point.total_bytes || (point.rx_bytes + point.tx_bytes)
                  const heightPercent = Math.max((total / maxBytes) * 100, 0.5)
                  return (
                    <div key={i} className="flex flex-col justify-end items-center group relative h-full flex-shrink-0" style={{ width: '4px' }}>
                      <div
                        className="w-full rounded-sm transition-all duration-300"
                        style={{
                          height: `${heightPercent}%`,
                          backgroundColor: total > 1000 ? '#48B3D0' : '#e2e8f0',
                          minHeight: '1px',
                        }}
                      />
                      <div className="absolute bottom-full mb-1 hidden group-hover:block bg-brand-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-20 pointer-events-none">
                        {point.time}<br/>
                        Bajada {formatRate(point.rx_bytes)}<br/>
                        Subida {formatRate(point.tx_bytes)}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Eje temporal */}
          <div className="flex justify-between text-xs text-ink-3 mt-2 pl-[68px]">
            <span>Hace 5 min</span>
            <span>Hace 2.5 min</span>
            <span>Ahora</span>
          </div>

          {/* Leyenda */}
          <div className="flex gap-4 mt-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#48B3D0' }}></span>
              Tráfico activo
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm bg-line"></span>
              Sin tráfico
            </span>
            <span className="text-ink-3 ml-auto">
              {timeline.length} puntos · {timeline.length * 5}s de histórico
            </span>
          </div>
        </div>

        {/* Sistema */}
        <div className="card p-6">
          <h3 className="font-medium text-ink mb-4">Sistema</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-ink-2">CPU</span>
                <span className="font-medium">{s.cpu.percent}% {s.cpu.load_1 !== undefined ? `(${s.cpu.load_1.toFixed(2)})` : ''}</span>
              </div>
              <div className="h-2 bg-line-soft rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(s.cpu.percent, 100)}%`, backgroundColor: '#0B497C' }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-ink-2">Memoria RAM</span>
                <span className="font-medium">{s.memory.percent}%</span>
              </div>
              <div className="h-2 bg-line-soft rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${s.memory.percent}%`, backgroundColor: s.memory.percent > 80 ? '#dc2626' : '#48B3D0' }} />
              </div>
            </div>
            {s.disk.total > 0 && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-ink-2">Disco (caché)</span>
                  <span className="font-medium">{s.disk.percent}%</span>
                </div>
                <div className="h-2 bg-line-soft rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${s.disk.percent}%`, backgroundColor: s.disk.percent > 80 ? '#dc2626' : '#0B497C' }} />
                </div>
              </div>
            )}
            <div className="pt-2 border-t border-line-soft text-xs text-ink-3 space-y-1">
              <div>RAM: {formatBytes(s.memory.used)} / {formatBytes(s.memory.total)}</div>
              {s.disk.total > 0 && <div>Disco: {formatBytes(s.disk.used)} / {formatBytes(s.disk.total)}</div>}
              <div>Total transferido: bajada {formatBytes(t.rx_total)} · subida {formatBytes(t.tx_total)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Top usuarios + Top dominios + Top bloqueados */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="card p-6">
          <h3 className="font-medium text-ink mb-4">Top usuarios por tráfico</h3>
          {data.top_users.length === 0 ? (
            <p className="text-sm text-ink-3">Sin datos</p>
          ) : (
            <div className="space-y-2">
              {data.top_users.map((u, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white" style={{ backgroundColor: '#0B497C' }}>{i + 1}</span>
                    <span className="font-medium">{u.user}</span>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-xs">{formatBytes(u.bytes)}</div>
                    <div className="text-xs text-ink-3">{u.requests} req</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-6">
          <h3 className="font-medium text-ink mb-4">Top sitios visitados</h3>
          {data.top_domains.length === 0 ? (
            <p className="text-sm text-ink-3">Sin datos</p>
          ) : (
            <div className="space-y-2">
              {data.top_domains.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white" style={{ backgroundColor: '#48B3D0' }}>{i + 1}</span>
                    <span className="font-mono text-xs truncate">{d.domain}</span>
                  </div>
                  <span className="text-xs text-ink-3 ml-2">{d.requests}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-6">
          <h3 className="font-medium text-ink mb-4">Top sitios bloqueados</h3>
          {data.top_blocked.length === 0 ? (
            <p className="text-sm text-ink-3">Sin bloqueos</p>
          ) : (
            <div className="space-y-2">
              {data.top_blocked.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white bg-red-500">{i + 1}</span>
                    <span className="font-mono text-xs truncate">{d.domain}</span>
                  </div>
                  <span className="text-xs text-ink-3 ml-2">{d.requests}x</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Últimas conexiones */}
      <div className="card overflow-hidden">
        <h3 className="font-medium text-ink p-6 pb-4">Últimas conexiones</h3>
        <div className="overflow-x-auto">
          <table className="table-panel">
            <thead className="bg-brand-50 border-y border-line-soft">
              <tr>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">Hora</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">IP</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">Usuario</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">Dominio</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-ink-3 uppercase">Estado</th>
                <th className="text-right px-6 py-2 text-xs font-medium text-ink-3 uppercase">Bytes</th>
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
                <tr><td colSpan={6} className="px-6 py-8 text-center text-ink-3">Sin conexiones recientes</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Accesos rápidos */}
      <div className="mt-6">
        <h2 className="text-lg font-bold mb-4" style={{ color: '#0A2C48' }}>Gestión</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { Icon: IconUsers, label: 'Usuarios', path: '/users' },
            { Icon: IconTag, label: 'ACLs', path: '/acls' },
            { Icon: IconRules, label: 'Reglas', path: '/rules' },
            { Icon: IconGauge, label: 'Ancho de banda', path: '/delay-pools' },
            { Icon: IconLink, label: 'LDAP', path: '/ldap' },
            { Icon: IconSettings, label: 'Configuración', path: '/settings' },
            { Icon: IconLock, label: 'Certificado', path: '/certificate' },
            { Icon: IconAudit, label: 'Auditoría', path: '/audit' },
          ].map((a, i) => (
            <button key={i} onClick={() => navigate(a.path)}
              className="card p-4 hover:shadow-lg hover:border-brand-200 transition text-center group">
              <div className="stat-icon mx-auto mb-2 group-hover:bg-brand-100 transition"><a.Icon /></div>
              <div className="text-sm font-medium text-ink-2">{a.label}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}