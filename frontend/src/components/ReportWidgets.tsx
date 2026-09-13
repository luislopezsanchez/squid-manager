// Piezas visuales compartidas entre las paginas de Analisis (Actividad de
// red, Latencia y errores...): antes vivian duplicadas dentro de
// ActividadRed.tsx, y la segunda pagina que las necesito iba a terminar con
// su propia copia que podia desincronizarse -mismo criterio que ya aplica
// el proyecto para formatBytes/formatNumber (ver utils/format.ts).
import { Link } from 'react-router-dom'
import { traducir } from '../i18n'
import { formatBytes, formatMs } from '../utils/format'

export type FilaDetalle = {
  time: string; user: string; domain: string; method: string
  status: number; bytes: number; elapsed_ms: number; denied: boolean
}

/** Barra horizontal proporcional al máximo del conjunto -no a una escala
 * fija-, para que el ranking se lea de un vistazo aunque el primero le
 * saque una distancia enorme al resto. Clickeable cuando hay drill-down
 * disponible (onClick): abre el detalle de esa fila puntual. */
export function FilaBarra({ etiqueta, subEtiqueta, valor, valorFormateado, maximo, color, posicion, onClick }: {
  etiqueta: string; subEtiqueta?: string; valor: number; valorFormateado: string
  maximo: number; color: string; posicion: number; onClick?: () => void
}) {
  const pct = maximo > 0 ? Math.max((valor / maximo) * 100, valor > 0 ? 2 : 0) : 0
  return (
    <div
      className={`flex items-center gap-3 py-1.5 rounded-lg ${onClick ? 'cursor-pointer hover:bg-line-soft/50 -mx-2 px-2' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
    >
      <span className="w-6 flex-none text-right text-xs font-semibold text-ink-3 tabular">{posicion}</span>
      <span className="w-40 md:w-56 flex-none truncate" title={etiqueta}>
        <span className="block text-sm text-ink truncate">{etiqueta}</span>
        {subEtiqueta && <span className="block text-[11px] text-ink-3 truncate">{subEtiqueta}</span>}
      </span>
      <div className="flex-1 h-5 bg-line-soft rounded-md overflow-hidden">
        <div
          className="h-full rounded-md transition-all"
          style={{ width: `${pct}%`, background: color, minWidth: valor > 0 ? '2px' : 0 }}
        />
      </div>
      <span className="w-20 flex-none text-right text-sm font-semibold tabular" style={{ color }}>
        {valorFormateado}
      </span>
    </div>
  )
}

/** Anillo que muestra que porcion del total concentra el top 3 -el
 * "grafico" que complementa a la tabla de barras, no una repeticion del
 * mismo dato. El total absoluto va debajo -sin el, el porcentaje no se
 * puede verificar ni sirve para citar en un informe (ver el bug real que
 * esto corrigio en Actividad de Red, 2026-09-12: el "Total" sumaba solo
 * el top 10 visible, no el total real de la ventana). */
export function AnilloConcentracion({ pct, color, total, totalFormateado }: {
  pct: number; color: string; total: number; totalFormateado: string
}) {
  const size = 108
  const stroke = 10
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const arco = Math.max(0, Math.min(pct, 100))
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative flex-none" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--line-soft)" strokeWidth={stroke} />
          <circle
            cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={circumference}
            strokeDashoffset={circumference - (arco / 100) * circumference}
            style={{ transition: 'stroke-dashoffset .6s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-extrabold tabular" style={{ color: 'var(--ink)' }}>{Math.round(pct)}%</span>
        </div>
      </div>
      {total > 0 && (
        <div className="text-center">
          <p className="text-[11px] text-ink-3">{traducir("Total")}</p>
          <p className="text-sm font-semibold text-ink tabular">{totalFormateado}</p>
        </div>
      )}
    </div>
  )
}

// Mismo criterio de color que LogsViewer.tsx (statusColor): un 403 no se
// lee igual que un 500, y ambos distinto de un 200 -consistente con como ya
// se pintan los estados en Registros, no un esquema nuevo por pagina.
export function statusColor(status: number): string {
  if (status >= 200 && status < 300) return 'pill-ok'
  if (status >= 300 && status < 400) return 'pill-info'
  if (status >= 400 && status < 500) return 'pill-danger'
  if (status >= 500) return 'bg-orange-100 text-orange-700'
  return 'pill-mute'
}

/** Detalle de una fila puntual (drill-down): que peticiones concretas
 * explican ese numero agregado. Mismo patron de modal que Admins.tsx /
 * ProxyUsers.tsx -overlay + tarjeta blanca, sin componente Modal generico
 * en el proyecto todavia. */
export function ModalDetalle({ titulo, filas, cargando, onClose, tendenciaHref }: {
  titulo: string; filas: FilaDetalle[]; cargando: boolean; onClose: () => void; tendenciaHref?: string
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-4xl max-h-[80vh] flex flex-col shadow-lg overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line-soft flex-none">
          <div>
            <h2 className="text-lg font-bold text-ink">{titulo}</h2>
            <p className="text-xs text-ink-3">{traducir("Últimas {n} peticiones", { n: filas.length })}</p>
          </div>
          <div className="flex items-center gap-2">
            {tendenciaHref && (
              <Link to={tendenciaHref}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border border-line-soft text-ink-2 hover:bg-line-soft/60 transition">
                {traducir("Ver tendencia")}
              </Link>
            )}
            <button onClick={onClose} aria-label={traducir("Cerrar")}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-ink-3 hover:bg-line-soft hover:text-ink text-xl leading-none transition">×</button>
          </div>
        </div>
        {cargando ? (
          <p className="text-sm text-ink-3 text-center py-12">{traducir("Cargando...")}</p>
        ) : filas.length === 0 ? (
          <p className="text-sm text-ink-3 text-center py-12">{traducir("Sin datos todavía.")}</p>
        ) : (
          <div className="overflow-auto">
            <table className="table-panel">
              <thead className="bg-brand-50 border-b border-line-soft sticky top-0">
                <tr>
                  <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Hora")}</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Usuario")}</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Dominio")}</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Estado")}</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Tamaño")}</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-ink-3 uppercase">{traducir("Latencia")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filas.map((f, i) => (
                  <tr key={i} className={`hover:bg-brand-50 ${f.denied ? 'bg-red-50/40' : ''}`}>
                    <td className="px-4 py-2 text-xs text-ink-3 font-mono whitespace-nowrap">{f.time}</td>
                    <td className="px-4 py-2 text-xs font-medium truncate max-w-[140px]" title={f.user}>{f.user}</td>
                    <td className="px-4 py-2 text-xs font-mono text-ink-2 truncate max-w-[260px]" title={f.domain}>{f.domain}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor(f.status)}`}>{f.status}</span>
                    </td>
                    <td className="px-4 py-2 text-right text-xs font-mono text-ink-3 tabular">{formatBytes(f.bytes)}</td>
                    <td className="px-4 py-2 text-right text-xs font-mono text-ink-3 tabular">{formatMs(f.elapsed_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

/** Selector de ventana de tiempo compartido: mismas 4 opciones en cada
 * pagina de Analisis que filtra por fecha, para que el admin no tenga que
 * reaprender el control en cada pantalla. */
export type Ventana = '' | '1h' | '24h' | '7d' | '30d'

export const VENTANAS: { id: Ventana; label: string }[] = [
  { id: '', label: traducir("Recientes (últimas 1.000)") },
  { id: '1h', label: traducir("Última hora") },
  { id: '24h', label: traducir("Últimas 24 horas") },
  { id: '7d', label: traducir("Últimos 7 días") },
  { id: '30d', label: traducir("Últimos 30 días") },
]

export function SelectorVentana({ value, onChange }: { value: Ventana; onChange: (v: Ventana) => void }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as Ventana)}
      className="input text-sm bg-white py-1.5"
      aria-label={traducir("Ventana de tiempo")}
    >
      {VENTANAS.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
    </select>
  )
}
