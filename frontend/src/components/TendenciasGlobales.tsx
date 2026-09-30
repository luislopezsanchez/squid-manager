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

function ListaMovers({ titulo, items, formato, tono }: { titulo: string; items: Mover[]; formato: (n: number) => string; tono: string }) {
  return (
    <div>
      <h4 className="text-[12px] font-semibold uppercase tracking-wide text-ink-3 mb-2">{titulo}</h4>
      {items.length === 0 ? <p className="text-[13px] text-ink-3">{traducir("Nada destacable.")}</p> : (
        <ul className="space-y-1.5">
          {items.map(m => {
            const pct = m.anterior > 0 ? Math.round(((m.actual - m.anterior) / m.anterior) * 100) : null
            return (
              <li key={m.nombre} className="flex items-baseline gap-2 text-[13px]">
                <span className="truncate text-ink" title={m.nombre}>{m.nombre}</span>
                <span className="ml-auto flex-none tabular text-ink-2">{formato(m.actual)}</span>
                <span className={`flex-none w-14 text-right tabular text-[12px] ${tono}`}>{pct == null ? traducir('nuevo') : pct > 999 ? '>999%' : `${pct > 0 ? '+' : ''}${pct}%`}</span>
              </li>
            )
          })}
        </ul>
      )}
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
            <TarjetaGrafico titulo={traducir("Usuarios: quién cambió")} subtitulo={traducir("Tráfico de este periodo frente al anterior")}>
              <div className="grid grid-cols-1 gap-5">
                <ListaMovers titulo={traducir("Suben")} items={(d.movers_usuarios as Movers).suben} formato={formatBytes} tono="text-danger" />
                <ListaMovers titulo={traducir("Bajan")} items={(d.movers_usuarios as Movers).bajan} formato={formatBytes} tono="text-ok" />
                <ListaMovers titulo={traducir("Nuevos")} items={(d.movers_usuarios as Movers).nuevos} formato={formatBytes} tono="text-ink-3" />
              </div>
            </TarjetaGrafico>
            <TarjetaGrafico titulo={traducir("Sitios: qué cambió")} subtitulo={traducir("Peticiones de este periodo frente al anterior")}>
              <div className="grid grid-cols-1 gap-5">
                <ListaMovers titulo={traducir("Suben")} items={(d.movers_dominios as Movers).suben} formato={formatNumber} tono="text-danger" />
                <ListaMovers titulo={traducir("Bajan")} items={(d.movers_dominios as Movers).bajan} formato={formatNumber} tono="text-ok" />
                <ListaMovers titulo={traducir("Nuevos")} items={(d.movers_dominios as Movers).nuevos} formato={formatNumber} tono="text-ink-3" />
              </div>
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
