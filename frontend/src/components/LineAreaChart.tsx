// Gráfico de línea + área con degradado, eje Y y tooltips por punto -mismo
// patrón visual que ya existía por separado en Dashboard.tsx (tráfico en
// tiempo real) y en Tendencias.tsx (evolución de un usuario/dominio). Con
// Panorama sumando un tercer uso, duplicarlo una vez más ya no se justificaba
// -ver utils/chart.ts, mismo criterio de extracción.
import { monotonePath } from '../utils/chart'

export function LineAreaChart({ valores, techo, formatearValor, tooltipFor, ejeXLabels, color = '#0B497C', altura = 220 }: {
  valores: number[]
  techo: number
  formatearValor: (n: number) => string
  tooltipFor: (i: number) => string
  ejeXLabels?: string[]
  color?: string
  altura?: number
}) {
  const pts: [number, number][] = valores.map((v, i) => {
    const x = valores.length > 1 ? (i / (valores.length - 1)) * 100 : 50
    const y = techo > 0 ? 100 - (v / techo) * 100 : 100
    return [x, y]
  })
  const linePath = monotonePath(pts)
  const areaPath = pts.length > 0
    ? `${linePath} L${pts[pts.length - 1][0].toFixed(2)},100 L${pts[0][0].toFixed(2)},100 Z`
    : ''
  const gradId = `lineAreaGrad-${color.replace('#', '')}`

  return (
    <div className="flex flex-col">
      <div className="flex gap-2" style={{ height: `${altura}px` }}>
        <div className="flex flex-col justify-between text-[10px] text-ink-3 font-mono text-right pr-1" style={{ width: '64px' }}>
          <span>{formatearValor(techo)}</span>
          <span>{formatearValor(techo * 0.75)}</span>
          <span>{formatearValor(techo * 0.5)}</span>
          <span>{formatearValor(techo * 0.25)}</span>
          <span>0</span>
        </div>
        <div className="relative flex-1 overflow-hidden">
          <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
            {[0, 1, 2, 3, 4].map(i => <div key={i} className="border-t border-line-soft w-full" />)}
          </div>
          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity="0.30" />
                <stop offset="100%" stopColor={color} stopOpacity="0.03" />
              </linearGradient>
            </defs>
            <path d={areaPath} fill={`url(#${gradId})`} />
            <path d={linePath} fill="none" stroke={color} strokeWidth="2"
              vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
          </svg>
          <div className="absolute inset-0">
            {valores.map((_, i) => {
              const width = 100 / valores.length
              const x = valores.length > 1 ? (i / (valores.length - 1)) * 100 : 50
              return (
                <div key={i} className="absolute top-0 h-full group"
                  style={{ left: `${Math.max(0, x - width / 2)}%`, width: `${width}%` }}>
                  <div className="absolute inset-y-0 left-1/2 w-px bg-brand-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block bg-brand-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-20 pointer-events-none">
                    {tooltipFor(i)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
      {ejeXLabels && (
        <div className="flex gap-2 mt-2 pl-[72px]">
          {ejeXLabels.map((l, i) => (
            <span key={i} className="flex-1 text-center text-[10px] text-ink-3 truncate">{l}</span>
          ))}
        </div>
      )}
    </div>
  )
}
