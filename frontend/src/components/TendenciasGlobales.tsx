import { useEffect, useMemo, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'
import { LoadingState } from './AsyncState'
import { GraficoBarras, GraficoTiempo, Indicador, MapaCalor, TarjetaGrafico, ESTADO, MARCA, SERIE } from './charts'

type Ventana = '24h' | '7d' | '30d'
const VENTANAS: { id: Ventana; etiqueta: string }[] = [
  { id: '24h', etiqueta: '24 horas' }, { id: '7d', etiqueta: '7 días' }, { id: '30d', etiqueta: '30 días' },
]
const DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

type Mover = { nombre: string; actual: number; anterior: number }
type Movers = { nuevos: Mover[]; suben: Mover[]; bajan: Mover[] }

const SUBE = SERIE[1]   // naranja: consume más que antes
const BAJA = SERIE[0]   // azul: consume menos
const NUEVO = SERIE[2]  // verde: no estaba en el periodo anterior

/** Cambios frente al periodo anterior como barras divergentes: a la derecha del eje, lo que
 * subió; a la izquierda, lo que bajó. Cada fila dice cuánto era antes y cuánto es ahora. */
function CambiosDivergentes({ movers, formato, unidad }: { movers: Movers; formato: (n: number) => string; unidad: string }) {
  const filas = [
    ...movers.suben.map(m => ({ ...m, tipo: 'sube' as const })),
    ...movers.nuevos.map(m => ({ ...m, tipo: 'nuevo' as const })),
    ...movers.bajan.map(m => ({ ...m, tipo: 'baja' as const })),
  ].map(m => ({ ...m, delta: m.actual - m.anterior }))
  if (filas.length === 0) return <p className="text-[13px] text-ink-3 py-4">{traducir("Sin cambios destacables frente al periodo anterior.")}</p>
  filas.sort((x, y) => y.delta - x.delta)
  const max = Math.max(...filas.map(f => Math.abs(f.delta)), 1)
  return (
    <div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-ink-3 mb-3">
        <span className="flex items-center gap-1.5"><i className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: BAJA }} />{traducir("Menos que antes")}</span>
        <span className="flex items-center gap-1.5"><i className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: SUBE }} />{traducir("Más que antes")}</span>
        <span className="flex items-center gap-1.5"><i className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: NUEVO }} />{traducir("Nuevo en este periodo")}</span>
      </div>
      <ul className="space-y-2">
        {filas.map(f => {
          const ancho = Math.max((Math.abs(f.delta) / max) * 50, 1.5)
          const color = f.tipo === 'nuevo' ? NUEVO : f.delta >= 0 ? SUBE : BAJA
          const signo = f.delta >= 0 ? '+' : '−'
          return (
            <li key={f.nombre} className="grid grid-cols-[minmax(0,9rem)_1fr] sm:grid-cols-[minmax(0,12rem)_1fr] gap-3 items-center text-[13px]"
              title={`${f.nombre}: ${formato(f.anterior)} → ${formato(f.actual)} ${unidad}`}>
              <span className="truncate text-ink">{f.nombre}</span>
              <div>
                <div className="relative h-4">
                  <span className="absolute inset-y-0 left-1/2 w-px bg-line" aria-hidden="true" />
                  <span className="absolute top-0.5 bottom-0.5 rounded-sm"
                    style={{ background: color, width: `${ancho}%`, ...(f.delta >= 0 ? { left: '50%' } : { right: '50%' }) }} />
                </div>
                <p className="text-[11px] text-ink-3 tabular mt-0.5">
                  {f.tipo === 'nuevo' ? traducir('nuevo') : `${formato(f.anterior)} → ${formato(f.actual)}`} · <span style={{ color }}>{signo}{formato(Math.abs(f.delta))}</span>
                </p>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** Tendencias del servicio entero (no de un usuario o sitio): evolución, cambios
 * frente al periodo anterior, quién crece o decrece y las horas de más actividad. */
export function TendenciasGlobales() {
  const [ventana, setVentana] = useState<Ventana>('7d')
  const [d, setD] = useState<any>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    setCargando(true)
    api.getPanorama(ventana).then(setD).catch(() => setD(null)).finally(() => setCargando(false))
  }, [ventana])

  const insights = useMemo(() => {
    if (!d?.disponible || !d.actual.requests) return []
    const lineas: string[] = []
    const mapa: number[][] = d.mapa_calor
    let mejor = { dia: 0, hora: 0, v: -1 }
    mapa.forEach((fila, dia) => fila.forEach((v, hora) => { if (v > mejor.v) mejor = { dia, hora, v } }))
    if (mejor.v > 0) lineas.push(traducir("Momento de más actividad: {dia} a las {hora}:00.", { dia: traducir(DIAS[mejor.dia]), hora: String(mejor.hora).padStart(2, '0') }))
    const porDia = mapa.map(f => f.reduce((a, b) => a + b, 0))
    const total = porDia.reduce((a, b) => a + b, 0)
    if (total > 0) {
      const dia = porDia.indexOf(Math.max(...porDia))
      lineas.push(traducir("El {dia} concentra el {pct}% del tráfico de la ventana.", { dia: traducir(DIAS[dia]), pct: String(Math.round((porDia[dia] / total) * 100)) }))
    }
    const top = d.top_usuarios?.[0]
    const totalBytes = d.actual.bytes
    if (top && totalBytes > 0 && top.bytes / totalBytes > 0.4) {
      lineas.push(traducir("{u} genera el {pct}% de todo el tráfico: conviene revisar si es uso legítimo.", { u: top.user, pct: String(Math.round((top.bytes / totalBytes) * 100)) }))
    }
    return lineas
  }, [d])

  return (
    <section className="mb-10">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold text-ink">{traducir("Tendencias del servicio")}</h2>
          <p className="text-sm text-ink-3">{traducir("Cómo evoluciona la navegación de todos y qué cambió frente al periodo anterior.")}</p>
        </div>
        <div className="flex gap-1 bg-line-soft p-1 rounded-lg" role="tablist">
          {VENTANAS.map(v => (
            <button key={v.id} role="tab" aria-selected={ventana === v.id} onClick={() => setVentana(v.id)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${ventana === v.id ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}>
              {traducir(v.etiqueta)}
            </button>
          ))}
        </div>
      </div>

      {cargando && !d ? <LoadingState /> : !d?.disponible ? (
        <div className="card p-8 text-center text-ink-3">{traducir("Los datos del análisis se están preparando. Vuelve a intentarlo en un minuto.")}</div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <Indicador titulo={traducir("Peticiones")} valor={formatNumber(d.actual.requests)} actual={d.actual.requests} anterior={d.anterior.requests} />
            <Indicador titulo={traducir("Tráfico")} valor={formatBytes(d.actual.bytes)} actual={d.actual.bytes} anterior={d.anterior.bytes} />
            <Indicador titulo={traducir("Usuarios activos")} valor={formatNumber(d.actual.users)} actual={d.actual.users} anterior={d.anterior.users} />
            <Indicador titulo={traducir("Sitios distintos")} valor={formatNumber(d.actual.domains)} actual={d.actual.domains} anterior={d.anterior.domains} />
          </div>

          {insights.length > 0 && (
            <div className="note note-info mb-4">
              <ul className="note-text list-disc pl-4 space-y-0.5">{insights.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
            <TarjetaGrafico titulo={traducir("Evolución del tráfico")}>
              <GraficoTiempo datos={d.serie} granularidad={d.granularidad} formatoEje={formatBytes}
                series={[{ key: 'bytes', label: traducir('Tráfico'), color: MARCA, formato: formatBytes }]} />
            </TarjetaGrafico>
            <TarjetaGrafico titulo={traducir("Evolución de las peticiones")}>
              <GraficoBarras datos={d.serie.map((s: any) => ({ ...s, permitidas: Math.max(s.requests - s.denied, 0) }))}
                granularidad={d.granularidad} formatoEje={formatNumber}
                series={[
                  { key: 'permitidas', label: traducir('Permitidas'), color: SERIE[0], formato: formatNumber },
                  { key: 'denied', label: traducir('Bloqueadas'), color: SERIE[1], formato: formatNumber },
                ]} />
            </TarjetaGrafico>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
            <TarjetaGrafico titulo={traducir("Usuarios: quién consume más o menos que antes")} subtitulo={traducir("Cambio en el tráfico de cada usuario frente al periodo anterior, de los que más variaron")}>
              <CambiosDivergentes movers={d.movers_usuarios as Movers} formato={formatBytes} unidad={traducir("de tráfico")} />
            </TarjetaGrafico>
            <TarjetaGrafico titulo={traducir("Sitios: cuáles se visitan más o menos que antes")} subtitulo={traducir("Cambio en las peticiones a cada sitio frente al periodo anterior, de los que más variaron")}>
              <CambiosDivergentes movers={d.movers_dominios as Movers} formato={formatNumber} unidad={traducir("peticiones")} />
            </TarjetaGrafico>
          </div>

          <TarjetaGrafico titulo={traducir("Horas de más actividad")} subtitulo={traducir("Peticiones por día de la semana y hora")}>
            <MapaCalor matriz={d.mapa_calor} formato={n => `${formatNumber(n)} ${traducir('peticiones')}`} />
          </TarjetaGrafico>
        </>
      )}
    </section>
  )
}
