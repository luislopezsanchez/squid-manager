// Kit de gráficos de las pantallas de análisis (Panorama, Tendencias, Actividad
// de red...), sobre Recharts. Una sola definición de colores, ejes y tooltips
// para que todos los gráficos se vean y se comporten igual.
//
// Reglas de diseño (método dataviz): una sola escala por gráfico (nunca doble
// eje: dos magnitudes distintas son dos gráficos), cuadrícula y ejes discretos,
// marcas finas, series categóricas en orden fijo, el estado (ok/aviso/error)
// con los colores reservados de la plataforma y siempre con texto, y un
// tooltip con guía vertical en todo gráfico de serie temporal.
import { useMemo } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { traducir } from '../i18n'

/** Series categóricas en orden fijo (paleta de referencia validada: azul, naranja, aqua, amarillo). */
export const SERIE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'] as const
/** Color de marca para la magnitud principal (una sola serie). */
export const MARCA = '#0B497C'
/** Estados: siempre acompañados de texto o icono, nunca solo color. */
export const ESTADO = { ok: '#2f9e75', aviso: '#b26a12', error: '#c0392f' } as const
const EJE = '#7a93a5'
const REJILLA = '#ebf2f6'

const pad = (n: number) => String(n).padStart(2, '0')

export type Granularidad = 'minuto' | 'hora' | 'dia'

export function etiquetaFecha(ts: number, granularidad: Granularidad): string {
  const d = new Date(ts * 1000)
  if (granularidad === 'minuto') return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (granularidad === 'dia') return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`
  return d.getHours() === 0 ? `${pad(d.getDate())}/${pad(d.getMonth() + 1)}` : `${pad(d.getHours())}:00`
}

export function fechaCompleta(ts: number, granularidad: Granularidad): string {
  const d = new Date(ts * 1000)
  if (granularidad === 'minuto') return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  const dia = d.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short' })
  return granularidad === 'dia' ? dia : `${dia} ${pad(d.getHours())}:00`
}

interface DefSerie { key: string; label: string; color?: string; formato?: (n: number) => string; apilar?: boolean }

function TooltipSerie({ active, payload, label, series, granularidad }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 shadow-lg text-[12.5px] border border-line-soft">
      <div className="font-semibold text-ink mb-1">{fechaCompleta(label, granularidad)}</div>
      {payload.map((p: any) => {
        const def: DefSerie | undefined = series.find((s: DefSerie) => s.key === p.dataKey)
        return (
          <div key={p.dataKey} className="flex items-center gap-2 text-ink-2">
            <span className="w-2.5 h-2.5 rounded-sm flex-none" style={{ background: p.color }} />
            <span>{def?.label ?? p.dataKey}</span>
            <span className="ml-auto pl-4 font-semibold text-ink tabular">{def?.formato ? def.formato(p.value) : p.value}</span>
          </div>
        )
      })}
    </div>
  )
}

/** Serie temporal en área, con guía vertical al pasar el ratón. Varias series
 * de la MISMA magnitud (p. ej. permitidas y bloqueadas) pueden apilarse. */
export function GraficoTiempo({ datos, series, granularidad, altura = 240, formatoEje }: {
  datos: Record<string, number>[]
  series: DefSerie[]
  granularidad: Granularidad
  altura?: number
  formatoEje?: (n: number) => string
}) {
  const marcas = useMemo(() => {
    const paso = Math.max(1, Math.ceil(datos.length / 8))
    return datos.filter((_, i) => i % paso === 0).map(d => d.timestamp)
  }, [datos])
  return (
    <div role="img" aria-label={series.map(s => s.label).join(', ')} style={{ height: altura }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {series.map((s, i) => (
              <linearGradient key={s.key} id={`g-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color ?? SERIE[i]} stopOpacity={0.28} />
                <stop offset="100%" stopColor={s.color ?? SERIE[i]} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke={REJILLA} vertical={false} />
          <XAxis dataKey="timestamp" ticks={marcas} tickFormatter={(t: number) => etiquetaFecha(t, granularidad)}
            tick={{ fontSize: 11, fill: EJE }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: EJE }} axisLine={false} tickLine={false} width={68}
            tickFormatter={formatoEje ?? ((n: number) => String(n))} />
          <Tooltip content={<TooltipSerie series={series} granularidad={granularidad} />}
            cursor={{ stroke: EJE, strokeDasharray: '3 3' }} />
          {series.map((s, i) => (
            <Area key={s.key} type="monotone" connectNulls={false} dataKey={s.key} stackId={s.apilar ? 'a' : undefined}
              stroke={s.color ?? SERIE[i]} strokeWidth={2} fill={`url(#g-${s.key})`} dot={false}
              activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Barras verticales por periodo, con permitidas/bloqueadas apiladas. */
export function GraficoBarras({ datos, series, granularidad, altura = 240, formatoEje }: {
  datos: Record<string, number>[]
  series: DefSerie[]
  granularidad: Granularidad
  altura?: number
  formatoEje?: (n: number) => string
}) {
  const marcas = useMemo(() => {
    const paso = Math.max(1, Math.ceil(datos.length / 8))
    return datos.filter((_, i) => i % paso === 0).map(d => d.timestamp)
  }, [datos])
  return (
    <div role="img" aria-label={series.map(s => s.label).join(', ')} style={{ height: altura }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={REJILLA} vertical={false} />
          <XAxis dataKey="timestamp" ticks={marcas} tickFormatter={(t: number) => etiquetaFecha(t, granularidad)}
            tick={{ fontSize: 11, fill: EJE }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: EJE }} axisLine={false} tickLine={false} width={68}
            tickFormatter={formatoEje ?? ((n: number) => String(n))} />
          <Tooltip content={<TooltipSerie series={series} granularidad={granularidad} />} cursor={{ fill: 'rgba(11,73,124,.06)' }} />
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} stackId="b" fill={s.color ?? SERIE[i]} isAnimationActive={false}
              radius={i === series.length - 1 ? [3, 3, 0, 0] : 0} maxBarSize={28} stroke="#fff" strokeWidth={1} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export interface ItemReparto { nombre: string; valor: number; color: string }

/** Dona de reparto con el total al centro y leyenda con valores (nunca solo color). */
export function DonaReparto({ items, formato, centro, altura = 190 }: {
  items: ItemReparto[]
  formato: (n: number) => string
  centro?: { titulo: string; valor: string }
  altura?: number
}) {
  const total = items.reduce((a, b) => a + b.valor, 0)
  const datos = items.filter(i => i.valor > 0)
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative flex-none" style={{ width: altura, height: altura }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={datos.length ? datos : [{ nombre: '-', valor: 1, color: REJILLA }]} dataKey="valor" nameKey="nombre"
              innerRadius="62%" outerRadius="94%" paddingAngle={datos.length > 1 ? 2 : 0} stroke="none" isAnimationActive={false}>
              {(datos.length ? datos : [{ color: REJILLA }]).map((d: any, i: number) => <Cell key={i} fill={d.color} />)}
            </Pie>
            {datos.length > 0 && (
              <Tooltip formatter={(v: any, n: any) => [formato(Number(v)), n]} contentStyle={{ borderRadius: 10, fontSize: 12.5 }} />
            )}
          </PieChart>
        </ResponsiveContainer>
        {centro && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-lg font-extrabold text-ink tabular leading-none">{centro.valor}</span>
            <span className="text-[10.5px] text-ink-3 mt-1">{centro.titulo}</span>
          </div>
        )}
      </div>
      <ul className="flex-1 min-w-0 w-full space-y-1.5 text-[13px]">
        {items.map(i => (
          <li key={i.nombre} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-sm flex-none" style={{ background: i.color }} />
            <span className="text-ink-2 truncate">{i.nombre}</span>
            <span className="ml-auto font-semibold text-ink tabular">{formato(i.valor)}</span>
            <span className="w-11 text-right text-ink-3 tabular text-[12px]">{total ? `${Math.round((i.valor / total) * 100)}%` : '—'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Ranking en barras horizontales, con el valor al final de cada barra. */
export function Ranking({ filas, formato, color = MARCA, vacio, onClick }: {
  filas: { nombre: string; valor: number; sub?: string }[]
  formato: (n: number) => string
  color?: string
  vacio?: string
  onClick?: (nombre: string) => void
}) {
  const max = Math.max(...filas.map(f => f.valor), 1)
  if (filas.length === 0) return <p className="text-sm text-ink-3 py-4">{vacio ?? traducir('Sin datos todavía.')}</p>
  return (
    <ul className="space-y-2">
      {filas.map((f, i) => (
        <li key={f.nombre}>
          <button type="button" disabled={!onClick} onClick={() => onClick?.(f.nombre)}
            className={`w-full text-left group ${onClick ? 'cursor-pointer' : 'cursor-default'}`}>
            <div className="flex items-baseline justify-between gap-3 text-[13px] mb-1">
              <span className="truncate text-ink group-hover:text-brand-700" title={f.nombre}>
                <span className="text-ink-3 tabular mr-1.5">{i + 1}</span>{f.nombre}
              </span>
              <span className="font-semibold tabular text-ink-2 flex-none">{formato(f.valor)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-line-soft overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${Math.max((f.valor / max) * 100, f.valor > 0 ? 2 : 0)}%`, background: color }} />
            </div>
            {f.sub && <div className="text-[11px] text-ink-3 mt-0.5 truncate">{f.sub}</div>}
          </button>
        </li>
      ))}
    </ul>
  )
}

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

/** Mapa de calor día de la semana × hora, en una sola escala de color (magnitud). */
export function MapaCalor({ matriz, formato }: { matriz: number[][]; formato: (n: number) => string }) {
  const max = Math.max(...matriz.flat(), 1)
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[560px]">
        <div className="grid gap-[3px]" style={{ gridTemplateColumns: '36px repeat(24, minmax(0, 1fr))' }}>
          <span />
          {Array.from({ length: 24 }, (_, h) => (
            <span key={h} className="text-[10px] text-ink-3 text-center tabular">{h % 3 === 0 ? pad(h) : ''}</span>
          ))}
          {matriz.map((fila, d) => (
            <div key={d} className="contents">
              <span className="text-[11px] text-ink-3 self-center">{traducir(DIAS[d])}</span>
              {fila.map((v, h) => {
                const t = v / max
                return (
                  <span key={h} className="h-5 rounded-[3px]" tabIndex={0}
                    title={`${traducir(DIAS[d])} ${pad(h)}:00 — ${formato(v)}`}
                    style={{ background: v === 0 ? '#eef3f6' : `rgba(11,73,124,${(0.12 + t * 0.88).toFixed(2)})` }} />
                )
              })}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 justify-end mt-2 text-[11px] text-ink-3">
          {traducir('Menos')}
          {[0.12, 0.35, 0.6, 0.85, 1].map(o => <span key={o} className="w-4 h-3 rounded-[2px]" style={{ background: `rgba(11,73,124,${o})` }} />)}
          {traducir('Más')}
        </div>
      </div>
    </div>
  )
}

/** Tarjeta de indicador con variación contra el periodo anterior.
 * `masEsMejor=false` invierte el color (más errores o más bloqueos no es «bueno»);
 * el sentido siempre se dice con flecha y texto. */
export function Indicador({ titulo, valor, actual, anterior, masEsMejor = true, formatoDelta, ayuda }: {
  titulo: string
  valor: string
  actual: number | null
  anterior: number | null
  masEsMejor?: boolean
  formatoDelta?: (n: number) => string
  ayuda?: string
}) {
  let delta: { texto: string; tono: string; flecha: string } | null = null
  if (actual != null && anterior != null && anterior > 0) {
    const pct = ((actual - anterior) / anterior) * 100
    if (Math.abs(pct) < 0.5) delta = { texto: traducir('sin cambios'), tono: 'text-ink-3', flecha: '→' }
    else {
      const sube = pct > 0
      const bueno = sube === masEsMejor
      delta = {
        texto: `${sube ? '+' : ''}${Math.abs(pct) >= 100 ? Math.round(pct) : pct.toFixed(1)}%`,
        tono: bueno ? 'text-ok' : 'text-danger', flecha: sube ? '▲' : '▼',
      }
    }
  }
  return (
    <div className="card p-4" title={ayuda}>
      <p className="text-[12px] text-ink-3">{titulo}</p>
      <p className="text-2xl font-bold text-ink tabular mt-1 leading-tight">{valor}</p>
      <p className={`text-[12px] mt-1 tabular ${delta?.tono ?? 'text-ink-3'}`}>
        {delta ? <>{delta.flecha} {delta.texto} <span className="text-ink-3">{traducir('vs. periodo anterior')}</span></> : <span>&nbsp;</span>}
      </p>
    </div>
  )
}

/** Cabecera de tarjeta de gráfico. */
export function TarjetaGrafico({ titulo, subtitulo, children, className = '' }: {
  titulo: string; subtitulo?: string; children: React.ReactNode; className?: string
}) {
  return (
    <section className={`card p-5 ${className}`}>
      <h3 className="text-sm font-semibold text-ink">{titulo}</h3>
      {subtitulo && <p className="text-[12px] text-ink-3 mt-0.5 mb-3">{subtitulo}</p>}
      {!subtitulo && <div className="mb-3" />}
      {children}
    </section>
  )
}
