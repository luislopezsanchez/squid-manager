import { traducir } from '../i18n'
import { useState, useEffect, useCallback } from 'react'
import { IconChevronLeft, IconChevronRight, IconDownload, IconArchive } from '../components/Icons'
import { api, getToken } from '../api/client'
import { useToast } from '../components/Toast'

interface MesIndice {
  year: number
  month: number
  file: string
  size_bytes: number
  total_lines?: number
  date_range?: { first: string | null; last: string | null }
  unique_users?: number
  unique_domains?: number
  status_codes?: Record<string, number>
  top_domains?: { domain: string; count: number }[]
  top_users?: { user: string; count: number }[]
  total_bytes?: number
  denied_count?: number
  sin_indice?: boolean
}

interface EntradaHistorica {
  time: string
  client_ip: string
  user: string
  method: string
  domain: string
  status: number
  bytes: number
}

const NOMBRES_MES = [
  '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
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

export default function HistoricalLogs() {
  const [meses, setMeses] = useState<MesIndice[]>([])
  const [loadingMeses, setLoadingMeses] = useState(true)
  const [seleccion, setSeleccion] = useState<{ year: number; month: number } | null>(null)

  const [entries, setEntries] = useState<EntradaHistorica[]>([])
  const [totalMatched, setTotalMatched] = useState(0)
  const [loadingEntries, setLoadingEntries] = useState(false)
  const [offset, setOffset] = useState(0)
  const [exportFormat, setExportFormat] = useState<'csv' | 'ndjson'>('csv')

  const [fUser, setFUser] = useState('')
  const [fStatus, setFStatus] = useState('')
  const [fDomain, setFDomain] = useState('')
  const [fDenied, setFDenied] = useState(false)

  const limit = 100
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    // Sin polling a propósito: un mes cerrado no cambia, no tiene sentido
    // repetir esta consulta cada pocos segundos como sí hace el visor en vivo.
    api.getHistoricalMonths()
      .then(setMeses)
      .catch(() => showToast(traducir("Error al cargar los meses históricos"), 'error'))
      .finally(() => setLoadingMeses(false))
  }, [])

  const cargarEntradas = useCallback(() => {
    if (!seleccion) return
    setLoadingEntries(true)
    api.getHistoricalEntries(seleccion.year, seleccion.month, {
      limit, offset,
      user: fUser || undefined,
      status: fStatus ? Number(fStatus) : undefined,
      domain: fDomain || undefined,
      denied: fDenied,
    }).then(data => {
      setEntries(data.entries)
      setTotalMatched(data.total_matched)
    }).catch(e => showToast(e.message, 'error')).finally(() => setLoadingEntries(false))
  }, [seleccion, offset, fUser, fStatus, fDomain, fDenied])

  useEffect(() => { cargarEntradas() }, [cargarEntradas])

  const seleccionarMes = (m: MesIndice) => {
    setSeleccion({ year: m.year, month: m.month })
    setOffset(0)
    setFUser(''); setFStatus(''); setFDomain(''); setFDenied(false)
  }

  const handleExport = () => {
    if (!seleccion) return
    const token = getToken()
    const url = api.exportHistoricalLogs(seleccion.year, seleccion.month, {
      format: exportFormat,
      user: fUser || undefined, status: fStatus ? Number(fStatus) : undefined,
      domain: fDomain || undefined, denied: fDenied,
    })
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        const u = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = u
        a.download = `squid-logs-${seleccion.year}${String(seleccion.month).padStart(2, '0')}.${exportFormat}`
        a.click()
        URL.revokeObjectURL(u)
        showToast(`Mes exportado (${exportFormat.toUpperCase()})`, 'success')
      })
      .catch(() => showToast(traducir("Error exportando el mes"), 'error'))
  }

  const mesActivo = seleccion ? meses.find(m => m.year === seleccion.year && m.month === seleccion.month) : null

  if (loadingMeses) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Histórico de logs")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Meses ya consolidados en frío. A diferencia de Registros (en vivo), esto no se actualiza solo: un mes cerrado no cambia.")}
      </p>

      {meses.length === 0 ? (
        <div className="card p-8 text-center text-ink-3">
          <IconArchive className="w-8 h-8 mx-auto mb-2 text-ink-4" />
          {traducir("Todavía no hay ningún mes consolidado. El primero aparece aquí al cerrar el mes en curso.")}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-6">
          {meses.map(m => {
            const activo = seleccion?.year === m.year && seleccion?.month === m.month
            return (
              <button
                key={`${m.year}-${m.month}`}
                onClick={() => seleccionarMes(m)}
                className={`card p-4 text-left hover:border-primary-500 transition-colors ${activo ? 'ring-2 ring-primary-500' : ''}`}
              >
                <div className="font-bold text-ink">{NOMBRES_MES[m.month]} {m.year}</div>
                {m.sin_indice ? (
                  <p className="text-xs text-ink-3 mt-1">{traducir("Sin resumen (instalación anterior al indexador)")}</p>
                ) : (
                  <>
                    <p className="text-xs text-ink-3 mt-1">{m.total_lines?.toLocaleString()} {traducir("peticiones")}</p>
                    <p className="text-xs text-ink-3">{formatBytes(m.size_bytes)} {traducir("comprimido")}</p>
                    {!!m.denied_count && (
                      <p className="text-xs text-danger mt-1">{m.denied_count.toLocaleString()} {traducir("denegadas")}</p>
                    )}
                  </>
                )}
              </button>
            )
          })}
        </div>
      )}

      {mesActivo && !mesActivo.sin_indice && (
        <div className="card p-4 mb-6">
          <h2 className="text-sm font-bold text-ink mb-3">
            {traducir("Resumen de")} {NOMBRES_MES[mesActivo.month]} {mesActivo.year}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-3">
            <div><span className="text-ink-3 block text-xs">{traducir("Usuarios únicos")}</span><span className="font-bold">{mesActivo.unique_users}</span></div>
            <div><span className="text-ink-3 block text-xs">{traducir("Dominios únicos")}</span><span className="font-bold">{mesActivo.unique_domains}</span></div>
            <div><span className="text-ink-3 block text-xs">{traducir("Tráfico total")}</span><span className="font-bold">{formatBytes(mesActivo.total_bytes || 0)}</span></div>
            <div><span className="text-ink-3 block text-xs">{traducir("Denegadas")}</span><span className="font-bold text-danger">{mesActivo.denied_count}</span></div>
          </div>
          {!!mesActivo.top_domains?.length && (
            <div className="text-xs text-ink-3">
              {traducir("Top dominios:")}{' '}
              {mesActivo.top_domains.slice(0, 5).map(d => `${d.domain} (${d.count})`).join(', ')}
            </div>
          )}
        </div>
      )}

      {seleccion && (
        <>
          <div className="card p-4 mb-4">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <div>
                <label htmlFor="hist-filter-user" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Usuario")}</label>
                <input id="hist-filter-user" type="text" value={fUser} placeholder={traducir("ej: jperez")}
                  onChange={e => { setFUser(e.target.value); setOffset(0) }}
                  className="input text-sm" />
              </div>
              <div>
                <label htmlFor="hist-filter-status" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Estado HTTP")}</label>
                <input id="hist-filter-status" type="text" value={fStatus} placeholder="403"
                  onChange={e => { setFStatus(e.target.value.replace(/\D/g, '')); setOffset(0) }}
                  className="input text-sm" />
              </div>
              <div>
                <label htmlFor="hist-filter-domain" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Dominio")}</label>
                <input id="hist-filter-domain" type="text" value={fDomain} placeholder={traducir("ej: youtube.com")}
                  onChange={e => { setFDomain(e.target.value); setOffset(0) }}
                  className="input text-sm" />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
                  <input type="checkbox" checked={fDenied} onChange={e => { setFDenied(e.target.checked); setOffset(0) }}
                    className="w-4 h-4 rounded" style={{ accentColor: '#dc2626' }} />{traducir("Solo bloqueados")}</label>
              </div>
              <div className="flex items-end gap-2">
                <select
                  value={exportFormat}
                  onChange={e => setExportFormat(e.target.value as typeof exportFormat)}
                  className="input text-sm flex-1"
                >
                  <option value="csv">CSV</option>
                  <option value="ndjson">NDJSON</option>
                </select>
                <button onClick={handleExport} className="btn btn-primary btn-sm shrink-0" title={traducir("Exporta el mes completo, no solo la página visible")}>
                  <IconDownload className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="table-panel">
                <thead className="bg-brand-50 border-b border-line-soft">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Hora")}</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">IP</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Usuario")}</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Método")}</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Dominio")}</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Estado")}</th>
                    <th className="text-right px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Bytes")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {loadingEntries ? (
                    <tr><td colSpan={7} className="px-6 py-8 text-center text-ink-3">{traducir("Cargando...")}</td></tr>
                  ) : entries.length === 0 ? (
                    <tr><td colSpan={7} className="px-6 py-8 text-center text-ink-3">{traducir("Sin resultados con estos filtros")}</td></tr>
                  ) : entries.map((e, i) => (
                    <tr key={i} className={`hover:bg-brand-50 ${e.status === 403 || e.status === 407 ? 'bg-red-50/40' : ''}`}>
                      <td className="px-4 py-2 text-xs text-ink-3 font-mono whitespace-nowrap">{e.time}</td>
                      <td className="px-4 py-2 text-xs font-mono text-ink-2">{e.client_ip}</td>
                      <td className="px-4 py-2 text-xs font-medium">{e.user}</td>
                      <td className="px-4 py-2 text-xs font-mono text-ink-2">{e.method}</td>
                      <td className="px-4 py-2 text-xs font-mono text-ink-2 max-w-xs truncate">{e.domain}</td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor(e.status)}`}>{e.status}</span>
                      </td>
                      <td className="px-4 py-2 text-right text-xs font-mono text-ink-3">{formatBytes(e.bytes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex items-center justify-between mt-4 text-sm">
            <span className="text-ink-3">{traducir("Mostrando")} {totalMatched === 0 ? 0 : offset + 1}–{Math.min(offset + limit, totalMatched)} {traducir("de")} {totalMatched}</span>
            <div className="flex gap-2">
              <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}
                className="px-3 py-1.5 border border-line rounded-lg disabled:opacity-40 hover:bg-brand-50 inline-flex items-center gap-1.5"><IconChevronLeft className="w-3.5 h-3.5" />{traducir("Anterior")}</button>
              <button onClick={() => setOffset(offset + limit)} disabled={offset + limit >= totalMatched}
                className="px-3 py-1.5 border border-line rounded-lg disabled:opacity-40 hover:bg-brand-50 inline-flex items-center gap-1.5">{traducir("Siguiente")}<IconChevronRight className="w-3.5 h-3.5" /></button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
