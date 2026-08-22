import { useState, useEffect, useCallback } from 'react'
import { api, getToken } from '../api/client'
import { useToast } from '../components/Toast'

interface LogEntry {
  timestamp: number
  time: string
  elapsed_ms: number
  client_ip: string
  action: string
  status: number
  bytes: number
  method: string
  url: string
  domain: string
  user: string
  hierarchy: string
  content_type: string
  denied: boolean
}

interface LogStats {
  total_entries: number
  users: string[]
  statuses: number[]
  top_domains: string[]
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function statusColor(status: number): string {
  if (status >= 200 && status < 300) return 'bg-green-100 text-green-700'
  if (status >= 300 && status < 400) return 'bg-blue-100 text-blue-700'
  if (status >= 400 && status < 500) return 'bg-red-100 text-red-700'
  if (status >= 500) return 'bg-orange-100 text-orange-700'
  return 'bg-gray-100 text-gray-600'
}

export default function LogsViewer() {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [stats, setStats] = useState<LogStats | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const limit = 100

  // Filtros
  const [fUser, setFUser] = useState('')
  const [fStatus, setFStatus] = useState('')
  const [fDomain, setFDomain] = useState('')
  const [fDenied, setFDenied] = useState(false)

  const { showToast, ToastContainer } = useToast()

  const loadLogs = useCallback(() => {
    setLoading(true)
    api.getLogs({
      limit, offset,
      user: fUser || undefined,
      status: fStatus ? Number(fStatus) : undefined,
      domain: fDomain || undefined,
      denied: fDenied,
    }).then(data => {
      setEntries(data.entries)
      setTotal(data.total)
    }).catch(e => showToast(e.message, 'error')).finally(() => setLoading(false))
  }, [offset, fUser, fStatus, fDomain, fDenied])

  const loadStats = useCallback(() => {
    api.getLogStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => { loadLogs(); loadStats() }, [loadLogs, loadStats])

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => { loadLogs(); loadStats() }, 5000)
    return () => clearInterval(id)
  }, [autoRefresh, loadLogs, loadStats])

  const handleExport = () => {
    const token = getToken()
    const url = api.exportLogsCsv({ user: fUser || undefined, status: fStatus ? Number(fStatus) : undefined, domain: fDomain || undefined, denied: fDenied })
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        const u = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = u
        a.download = `squid-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '')}.csv`
        a.click()
        URL.revokeObjectURL(u)
        showToast('Logs exportados a CSV', 'success')
      })
      .catch(() => showToast('Error exportando logs', 'error'))
  }

  const handleResetFilters = () => {
    setFUser(''); setFStatus(''); setFDomain(''); setFDenied(false); setOffset(0)
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#083151' }}>Logs de Squid</h1>
        <div className="flex items-center gap-4">
          {autoRefresh && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
              EN VIVO
            </span>
          )}
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded" style={{ accentColor: '#0b497c' }} />
            Auto-actualizar (5s)
          </label>
          <button onClick={handleExport}
            className="px-4 py-2 text-white rounded-lg text-sm font-medium" style={{ backgroundColor: '#0b497c' }}>
            ⬇ Exportar CSV
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Usuario</label>
            <select value={fUser} onChange={e => { setFUser(e.target.value); setOffset(0) }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
              <option value="">Todos</option>
              {stats?.users.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Estado HTTP</label>
            <select value={fStatus} onChange={e => { setFStatus(e.target.value); setOffset(0) }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
              <option value="">Todos</option>
              {stats?.statuses.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Dominio</label>
            <input type="text" value={fDomain} placeholder="ej: youtube.com"
              onChange={e => { setFDomain(e.target.value); setOffset(0) }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input type="checkbox" checked={fDenied} onChange={e => { setFDenied(e.target.checked); setOffset(0) }}
                className="w-4 h-4 rounded" style={{ accentColor: '#dc2626' }} />
              Solo bloqueados
            </label>
          </div>
          <div className="flex items-end">
            <button onClick={handleResetFilters}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
              Limpiar filtros
            </button>
          </div>
        </div>
      </div>

      {/* Resumen */}
      {stats && (
        <div className="flex gap-4 mb-6 text-sm">
          <div className="bg-white rounded-lg border border-gray-100 px-4 py-2">
            <span className="text-gray-500">Total entradas: </span>
            <span className="font-bold text-gray-800">{stats.total_entries}</span>
          </div>
          <div className="bg-white rounded-lg border border-gray-100 px-4 py-2">
            <span className="text-gray-500">Mostrando: </span>
            <span className="font-bold text-gray-800">{total} filtradas</span>
          </div>
        </div>
      )}

      {/* Tabla de logs */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100 sticky top-0">
              <tr>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Hora</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">IP</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Usuario</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Método</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Dominio</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th className="text-right px-4 py-2 text-xs font-medium text-gray-500 uppercase">Bytes</th>
                <th className="text-right px-4 py-2 text-xs font-medium text-gray-500 uppercase">Tiempo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {entries.map((e, i) => (
                <tr key={i} className={`hover:bg-gray-50 ${e.denied ? 'bg-red-50/40' : ''}`}>
                  <td className="px-4 py-2 text-xs text-gray-500 font-mono whitespace-nowrap">{e.time}</td>
                  <td className="px-4 py-2 text-xs font-mono text-gray-600">{e.client_ip}</td>
                  <td className="px-4 py-2 text-xs font-medium">{e.user}</td>
                  <td className="px-4 py-2 text-xs font-mono text-gray-600">{e.method}</td>
                  <td className="px-4 py-2 text-xs font-mono text-gray-600 max-w-xs truncate" title={e.url}>{e.domain}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor(e.status)}`}>{e.status}</span>
                  </td>
                  <td className="px-4 py-2 text-right text-xs font-mono text-gray-500">{formatBytes(e.bytes)}</td>
                  <td className="px-4 py-2 text-right text-xs font-mono text-gray-400">{e.elapsed_ms}ms</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={8} className="px-6 py-8 text-center text-gray-400">Sin resultados con estos filtros</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Paginación */}
      <div className="flex items-center justify-between mt-4 text-sm">
        <span className="text-gray-500">Mostrando {offset + 1}–{Math.min(offset + limit, total)} de {total}</span>
        <div className="flex gap-2">
          <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}
            className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50">← Anterior</button>
          <button onClick={() => setOffset(offset + limit)} disabled={offset + limit >= total}
            className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50">Siguiente →</button>
        </div>
      </div>

      <ToastContainer />
    </div>
  )
}