import { useState, useEffect, useRef } from 'react'
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

  if (loading || !data) return <div className="p-8 text-center text-gray-500">Cargando métricas...</div>

  const t = data.traffic
  const s = data.system
  const timeline = data.timeline
  const maxBytes = Math.max(...timeline.map(p => p.total_bytes), 1)

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#083151' }}>Dashboard</h1>
        <div className="flex items-center gap-4">
          {autoRefresh && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
              EN VIVO
            </span>
          )}
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded"
              style={{ accentColor: '#0b497c' }}
            />
            Auto-actualizar (5s)
          </label>
        </div>
      </div>

      {/* Métricas principales - 4 tarjetas */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-gray-500">Tráfico actual</h3>
            <span className="text-xl">📊</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: '#0b497c' }}>{formatRate(t.total_bytes_per_second)}</p>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>↓ {formatRate(t.rx_bytes_per_second)}</span>
            <span>↑ {formatRate(t.tx_bytes_per_second)}</span>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-gray-500">Peticiones (60s)</h3>
            <span className="text-xl">🔄</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: '#299ac2' }}>{formatNumber(t.total_requests_60s)}</p>
          <p className="text-xs text-gray-400 mt-1">
            {t.total_requests_60s - t.denied_requests_60s} OK / {t.denied_requests_60s} denegadas
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-gray-500">Conexiones activas</h3>
            <span className="text-xl">🔌</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: '#083151' }}>{t.active_ips.length}</p>
          <p className="text-xs text-gray-400 mt-1">{t.active_users.length} usuarios</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm text-gray-500">RAM del proxy</h3>
            <span className="text-xl">💾</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: s.memory.percent > 80 ? '#dc2626' : '#0b497c' }}>
            {s.memory.percent}%
          </p>
          <p className="text-xs text-gray-400 mt-1">{formatBytes(s.memory.used)} / {formatBytes(s.memory.total)}</p>
        </div>
      </div>

      {/* Gráfico de tráfico + Sistema */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Gráfico de tráfico - barras finas, más puntos */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-gray-900">Tráfico de red en tiempo real</h3>
            <span className="text-xs text-gray-400">
              Promedio: ↓{formatRate(t.rx_avg_60s)} ↑{formatRate(t.tx_avg_60s)}
            </span>
          </div>

          {/* Gráfico con eje Y */}
          <div className="flex gap-2" style={{ height: '192px' }}>
            {/* Eje Y - marcas de escala */}
            <div className="flex flex-col justify-between text-[10px] text-gray-400 font-mono text-right pr-1" style={{ width: '60px' }}>
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
                  <div key={i} className="border-t border-gray-100 w-full" style={{ height: '0' }} />
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
                          backgroundColor: total > 1000 ? '#299ac2' : '#e2e8f0',
                          minHeight: '1px',
                        }}
                      />
                      <div className="absolute bottom-full mb-1 hidden group-hover:block bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-20 pointer-events-none">
                        {point.time}<br/>
                        ↓ {formatRate(point.rx_bytes)}<br/>
                        ↑ {formatRate(point.tx_bytes)}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Eje temporal */}
          <div className="flex justify-between text-xs text-gray-400 mt-2 pl-[68px]">
            <span>Hace 5 min</span>
            <span>Hace 2.5 min</span>
            <span>Ahora</span>
          </div>

          {/* Leyenda */}
          <div className="flex gap-4 mt-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#299ac2' }}></span>
              Tráfico activo
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm bg-gray-200"></span>
              Sin tráfico
            </span>
            <span className="text-gray-400 ml-auto">
              {timeline.length} puntos · {timeline.length * 5}s de histórico
            </span>
          </div>
        </div>

        {/* Sistema */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-medium text-gray-900 mb-4">Sistema</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">CPU</span>
                <span className="font-medium">{s.cpu.percent}% {s.cpu.load_1 !== undefined ? `(${s.cpu.load_1.toFixed(2)})` : ''}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(s.cpu.percent, 100)}%`, backgroundColor: '#0b497c' }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Memoria RAM</span>
                <span className="font-medium">{s.memory.percent}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${s.memory.percent}%`, backgroundColor: s.memory.percent > 80 ? '#dc2626' : '#299ac2' }} />
              </div>
            </div>
            {s.disk.total > 0 && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">Disco (caché)</span>
                  <span className="font-medium">{s.disk.percent}%</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${s.disk.percent}%`, backgroundColor: s.disk.percent > 80 ? '#dc2626' : '#0b497c' }} />
                </div>
              </div>
            )}
            <div className="pt-2 border-t border-gray-100 text-xs text-gray-400 space-y-1">
              <div>RAM: {formatBytes(s.memory.used)} / {formatBytes(s.memory.total)}</div>
              {s.disk.total > 0 && <div>Disco: {formatBytes(s.disk.used)} / {formatBytes(s.disk.total)}</div>}
              <div>Total transferido: ↓{formatBytes(t.rx_total)} ↑{formatBytes(t.tx_total)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Top usuarios + Top dominios + Top bloqueados */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-medium text-gray-900 mb-4">👥 Top usuarios por tráfico</h3>
          {data.top_users.length === 0 ? (
            <p className="text-sm text-gray-400">Sin datos</p>
          ) : (
            <div className="space-y-2">
              {data.top_users.map((u, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white" style={{ backgroundColor: '#0b497c' }}>{i + 1}</span>
                    <span className="font-medium">{u.user}</span>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-xs">{formatBytes(u.bytes)}</div>
                    <div className="text-xs text-gray-400">{u.requests} req</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-medium text-gray-900 mb-4">🌐 Top sitios visitados</h3>
          {data.top_domains.length === 0 ? (
            <p className="text-sm text-gray-400">Sin datos</p>
          ) : (
            <div className="space-y-2">
              {data.top_domains.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white" style={{ backgroundColor: '#299ac2' }}>{i + 1}</span>
                    <span className="font-mono text-xs truncate">{d.domain}</span>
                  </div>
                  <span className="text-xs text-gray-400 ml-2">{d.requests}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-medium text-gray-900 mb-4">🚫 Top sitios bloqueados</h3>
          {data.top_blocked.length === 0 ? (
            <p className="text-sm text-gray-400">Sin bloqueos</p>
          ) : (
            <div className="space-y-2">
              {data.top_blocked.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-5 h-5 rounded-full text-xs flex items-center justify-center text-white bg-red-500">{i + 1}</span>
                    <span className="font-mono text-xs truncate">{d.domain}</span>
                  </div>
                  <span className="text-xs text-gray-400 ml-2">{d.requests}x</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Últimas conexiones */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <h3 className="font-medium text-gray-900 p-6 pb-4">📡 Últimas conexiones</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-y border-gray-100">
              <tr>
                <th className="text-left px-6 py-2 text-xs font-medium text-gray-500 uppercase">Hora</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-gray-500 uppercase">IP</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-gray-500 uppercase">Usuario</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-gray-500 uppercase">Dominio</th>
                <th className="text-left px-6 py-2 text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th className="text-right px-6 py-2 text-xs font-medium text-gray-500 uppercase">Bytes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.connections.map((c, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-6 py-2 text-xs text-gray-500 font-mono">{c.time}</td>
                  <td className="px-6 py-2 text-xs font-mono text-gray-600">{c.ip}</td>
                  <td className="px-6 py-2 text-xs font-medium">{c.user}</td>
                  <td className="px-6 py-2 text-xs font-mono text-gray-600 max-w-xs truncate">{c.domain}</td>
                  <td className="px-6 py-2">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                      c.denied ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                    }`}>{c.status}</span>
                  </td>
                  <td className="px-6 py-2 text-right text-xs font-mono text-gray-500">{formatBytes(c.bytes)}</td>
                </tr>
              ))}
              {data.connections.length === 0 && (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-400">Sin conexiones recientes</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Accesos rápidos */}
      <div className="mt-6">
        <h2 className="text-lg font-bold mb-4" style={{ color: '#083151' }}>Gestión</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { icon: '👥', label: 'Usuarios', path: '/users' },
            { icon: '🏷️', label: 'ACLs', path: '/acls' },
            { icon: '📋', label: 'Reglas', path: '/rules' },
            { icon: '🐌', label: 'Bandwidth', path: '/delay-pools' },
            { icon: '🔗', label: 'LDAP', path: '/ldap' },
            { icon: '⚙️', label: 'Config', path: '/settings' },
            { icon: '🔐', label: 'Cert SSL', path: '/certificate' },
            { icon: '📝', label: 'Auditoría', path: '/audit' },
          ].map((a, i) => (
            <button key={i} onClick={() => navigate(a.path)}
              className="bg-white rounded-xl shadow-sm p-4 border border-gray-100 hover:shadow-md transition text-center">
              <div className="text-2xl mb-1">{a.icon}</div>
              <div className="text-sm font-medium text-gray-700">{a.label}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}