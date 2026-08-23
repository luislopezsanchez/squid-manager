import { useState, useEffect, useCallback } from 'react'
import { IconChevronLeft, IconChevronRight, IconDownload } from '../components/Icons'
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
  if (status >= 200 && status < 300) return 'pill-ok'
  if (status >= 300 && status < 400) return 'pill-info'
  if (status >= 400 && status < 500) return 'pill-danger'
  if (status >= 500) return 'bg-orange-100 text-orange-700'
  return 'pill-mute'
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
    <div className="p-6 md:p-7">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" style={{ color: '#0A2C48' }}>Logs de Squid</h1>
        <div className="flex items-center gap-4">
          {autoRefresh && (
            <span className="flex items-center gap-1 text-xs text-ok">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
              EN VIVO
            </span>
          )}
          <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 rounded" style={{ accentColor: '#0B497C' }} />
            Auto-actualizar (5s)
          </label>
          <button onClick={handleExport}
            className="px-4 py-2 text-white rounded-lg text-sm font-medium" style={{ backgroundColor: '#0B497C' }}>
            <IconDownload /> Exportar CSV
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="card p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs font-medium text-ink-3 mb-1">Usuario</label>
            <select value={fUser} onChange={e => { setFUser(e.target.value); setOffset(0) }}
              className="input text-sm">
              <option value="">Todos</option>
              {stats?.users.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-3 mb-1">Estado HTTP</label>
            <select value={fStatus} onChange={e => { setFStatus(e.target.value); setOffset(0) }}
              className="input text-sm">
              <option value="">Todos</option>
              {stats?.statuses.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-3 mb-1">Dominio</label>
            <input type="text" value={fDomain} placeholder="ej: youtube.com"
              onChange={e => { setFDomain(e.target.value); setOffset(0) }}
              className="input text-sm" />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
              <input type="checkbox" checked={fDenied} onChange={e => { setFDenied(e.target.checked); setOffset(0) }}
                className="w-4 h-4 rounded" style={{ accentColor: '#dc2626' }} />
              Solo bloqueados
            </label>
          </div>
          <div className="flex items-end">
            <button onClick={handleResetFilters}
              className="input text-sm text-ink-2 hover:bg-brand-50">
              Limpiar filtros
            </button>
          </div>
        </div>
      </div>

      {/* Resumen */}
      {stats && (
        <div className="flex gap-4 mb-6 text-sm">
          <div className="bg-white rounded-lg border border-line-soft px-4 py-2">
            <span className="text-ink-3">Total entradas: </span>
            <span className="font-bold text-ink">{stats.total_entries}</span>
          </div>
          <div className="bg-white rounded-lg border border-line-soft px-4 py-2">
            <span className="text-ink-3">Mostrando: </span>
            <span className="font-bold text-ink">{total} filtradas</span>
          </div>
        </div>
      )}

      {/* Tabla de logs */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="table-panel">
            <thead className="bg-brand-50 border-b border-line-soft sticky top-0">
              <tr>
                <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Hora</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">IP</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Usuario</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Método</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Dominio</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Estado</th>
                <th className="text-right px-4 py-2 text-xs font-medium text-ink-3 uppercase">Bytes</th>
                <th className="text-right px-4 py-2 text-xs font-medium text-ink-3 uppercase">Tiempo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {entries.map((e, i) => (
                <tr key={i} className={`hover:bg-brand-50 ${e.denied ? 'bg-red-50/40' : ''}`}>
                  <td className="px-4 py-2 text-xs text-ink-3 font-mono whitespace-nowrap">{e.time}</td>
                  <td className="px-4 py-2 text-xs font-mono text-ink-2">{e.client_ip}</td>
                  <td className="px-4 py-2 text-xs font-medium">{e.user}</td>
                  <td className="px-4 py-2 text-xs font-mono text-ink-2">{e.method}</td>
                  <td className="px-4 py-2 text-xs font-mono text-ink-2 max-w-xs truncate" title={e.url}>{e.domain}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor(e.status)}`}>{e.status}</span>
                  </td>
                  <td className="px-4 py-2 text-right text-xs font-mono text-ink-3">{formatBytes(e.bytes)}</td>
                  <td className="px-4 py-2 text-right text-xs font-mono text-ink-3">{e.elapsed_ms}ms</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={8} className="px-6 py-8 text-center text-ink-3">Sin resultados con estos filtros</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Paginación */}
      <div className="flex items-center justify-between mt-4 text-sm">
        <span className="text-ink-3">Mostrando {offset + 1}–{Math.min(offset + limit, total)} de {total}</span>
        <div className="flex gap-2">
          <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}
            className="px-3 py-1.5 border border-line rounded-lg disabled:opacity-40 hover:bg-brand-50 inline-flex items-center gap-1.5"><IconChevronLeft className="w-3.5 h-3.5" />Anterior</button>
          <button onClick={() => setOffset(offset + limit)} disabled={offset + limit >= total}
            className="px-3 py-1.5 border border-line rounded-lg disabled:opacity-40 hover:bg-brand-50 inline-flex items-center gap-1.5">Siguiente<IconChevronRight className="w-3.5 h-3.5" /></button>
        </div>
      </div>

      <ToastContainer />
    </div>
  )
}