import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { useNavigate } from 'react-router-dom'

interface DashboardData {
  traffic: {
    total_requests: number
    allowed_requests: number
    denied_requests: number
    total_bytes: number
    bytes_per_second: number
    active_connections: number
    active_users: number
    active_ips: string[]
  }
  top_users: { user: string; bytes: number; requests: number }[]
  top_domains: { domain: string; requests: number; bytes: number }[]
  top_blocked: { domain: string; requests: number; bytes: number }[]
  system: {
    cpu: { load_1: number; load_5: number; load_15: number }
    memory: { total: number; used: number; available: number; percent: number }
    disk: { total: number; used: number; free: number; percent: number }
  }
  timeline: { time: string; bytes: number; requests: number; denied: number }[]
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
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

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

  // Calcular altura máxima del gráfico
  const maxBytes = Math.max(...data.timeline.map(p => p.bytes), 1)

  return (
    <div className="p-8">
      {/* Header con auto-refresh */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#083151' }}>Dashboard</h1>
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

      {/* Métricas principales - 4 tarjetas */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Tráfico actual"
          value={formatBytes(t.bytes_per_second) + '/s'}
          sub={`${formatBytes(t.total_bytes)} en 60s`}
          color="#0b497c"
          icon="📊"
        />
        <MetricCard
          title="Peticiones (60s)"
          value={formatNumber(t.total_requests)}
          sub={`${t.allowed_requests} OK / ${t.denied_requests} denegadas`}
          color="#299ac2"
          icon="🔄"
        />
        <MetricCard
          title="Conexiones activas"
          value={t.active_connections.toString()}
          sub={`${t.active_users} usuarios`}
          color="#083151"
          icon="🔌"
        />
        <MetricCard
          title="RAM del proxy"
          value={s.memory.percent + '%'}
          sub={`${formatBytes(s.memory.used)} / ${formatBytes(s.memory.total)}`}
          color={s.memory.percent > 80 ? '#dc2626' : '#0b497c'}
          icon="💾"
        />
      </div>

      {/* Gráfico de tráfico + Sistema */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Gráfico de tráfico (2/3) */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-medium text-gray-900 mb-4">Tráfico por segundo (últimos 60s)</h3>
          <div className="flex items-end gap-1 h-40">
            {data.timeline.map((point, i) => (
              <div key={i} className="flex-1 flex flex-col items-center group relative">
                {/* Bar */}
                <div
                  className="w-full rounded-t transition-all hover:opacity-80"
                  style={{
                    height: `${Math.max((point.bytes / maxBytes) * 100, 2)}%`,
                    backgroundColor: point.denied > 0 ? '#dc2626' : '#299ac2',
                    minHeight: '4px',
                  }}
                />
                {/* Tooltip */}
                <div className="absolute bottom-full mb-2 hidden group-hover:block bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                  {point.time} | {formatBytes(point.bytes)} | {point.requests} req
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-2">
            <span>Hace 60s</span>
            <span>Ahora</span>
          </div>
          <div className="flex gap-4 mt-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ backgroundColor: '#299ac2' }}></span>
              Tráfico permitido
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-red-600"></span>
              Con denegaciones
            </span>
          </div>
        </div>

        {/* Sistema (1/3) */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-medium text-gray-900 mb-4">Sistema</h3>
          <div className="space-y-4">
            {/* CPU */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">CPU Load</span>
                <span className="font-medium">{s.cpu.load_1?.toFixed(2) || 'N/A'}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${Math.min((s.cpu.load_1 || 0) * 25, 100)}%`, backgroundColor: '#0b497c' }}
                />
              </div>
            </div>
            {/* RAM */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Memoria RAM</span>
                <span className="font-medium">{s.memory.percent}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${s.memory.percent}%`, backgroundColor: s.memory.percent > 80 ? '#dc2626' : '#299ac2' }}
                />
              </div>
            </div>
            {/* Disco */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Disco (caché)</span>
                <span className="font-medium">{s.disk.percent}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${s.disk.percent}%`, backgroundColor: s.disk.percent > 80 ? '#dc2626' : '#0b497c' }}
                />
              </div>
            </div>
            <div className="pt-2 border-t border-gray-100 text-xs text-gray-400 space-y-1">
              <div>RAM: {formatBytes(s.memory.used)} / {formatBytes(s.memory.total)}</div>
              <div>Disco: {formatBytes(s.disk.used)} / {formatBytes(s.disk.total)}</div>
              <div>Swap load: {s.cpu.load_5?.toFixed(2)} / {s.cpu.load_15?.toFixed(2)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Top usuarios + Top dominios + Top bloqueados */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Top usuarios */}
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

        {/* Top dominios visitados */}
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

        {/* Top dominios bloqueados */}
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
                    }`}>
                      {c.status}
                    </span>
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
            <button
              key={i}
              onClick={() => navigate(a.path)}
              className="bg-white rounded-xl shadow-sm p-4 border border-gray-100 hover:shadow-md transition text-center"
            >
              <div className="text-2xl mb-1">{a.icon}</div>
              <div className="text-sm font-medium text-gray-700">{a.label}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function MetricCard({ title, value, sub, color, icon }: { title: string; value: string; sub: string; color: string; icon: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm text-gray-500">{title}</h3>
        <span className="text-xl">{icon}</span>
      </div>
      <p className="text-2xl font-bold" style={{ color }}>{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  )
}