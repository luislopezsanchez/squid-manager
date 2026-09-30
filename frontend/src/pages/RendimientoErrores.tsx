import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatNumber, formatMs } from '../utils/format'
import {
  FilaBarra, ModalDetalle, SelectorVentana, VENTANAS,
  type FilaDetalle, type Ventana,
} from '../components/ReportWidgets'
import { LoadingState, ErrorState } from '../components/AsyncState'
import { DonaReparto, GraficoBarras, GraficoTiempo, TarjetaGrafico, ESTADO, MARCA } from '../components/charts'

type Latencia = {
  latency_avg_ms: number | null
  latency_p50_ms: number | null
  latency_p95_ms: number | null
  domains: { domain: string; avg_ms: number; samples: number }[]
  histograma?: { hasta_ms: number | null; n: number }[]
}
type ErroresHttp = {
  total: number
  peticiones?: number
  by_code: { code: number; count: number }[]
  by_domain: { domain: string; count: number }[]
}

type Pestana = 'latencia' | 'errores'

function TarjetaKpi({ label, valor, ayuda, color }: { label: string; valor: string; ayuda?: string; color?: string }) {
  return (
    <div className="card p-4 flex-1" style={color ? { borderLeft: `4px solid ${color}` } : undefined}>
      <p className="text-xs text-ink-3 mb-1">{label}</p>
      <p className="text-2xl font-bold text-ink tabular">{valor}</p>
      {ayuda && <p className="text-[11.5px] text-ink-3 mt-1">{ayuda}</p>}
    </div>
  )
}

// Verde si el sitio responde rápido, ámbar si se nota, rojo si es lento de verdad.
function colorLatenciaMs(ms: number | null | undefined): string | undefined {
  if (ms == null) return undefined
  return ms < 300 ? ESTADO.ok : ms < 1000 ? ESTADO.aviso : ESTADO.error
}

// Agrupa los baldes finos del histograma en rangos que se entienden de un vistazo.
const RANGOS: { etiqueta: string; hasta: number; color: string }[] = [
  { etiqueta: '< 25 ms', hasta: 25, color: ESTADO.ok },
  { etiqueta: '25–100 ms', hasta: 100, color: ESTADO.ok },
  { etiqueta: '100–300 ms', hasta: 300, color: ESTADO.ok },
  { etiqueta: '300 ms–1 s', hasta: 1000, color: ESTADO.aviso },
  { etiqueta: '1–3 s', hasta: 3000, color: ESTADO.error },
  { etiqueta: '> 3 s', hasta: Infinity, color: ESTADO.error },
]

function Histograma({ datos }: { datos: { hasta_ms: number | null; n: number }[] }) {
  const grupos = RANGOS.map(r => ({ ...r, n: 0 }))
  for (const b of datos) {
    const tope = b.hasta_ms ?? Infinity
    const g = grupos.find(x => tope <= x.hasta) ?? grupos[grupos.length - 1]
    g.n += b.n
  }
  const total = grupos.reduce((a, g) => a + g.n, 0)
  const max = Math.max(...grupos.map(g => g.n), 1)
  if (total === 0) return <p className="text-sm text-ink-3 py-6">{traducir("Sin datos todavía.")}</p>
  return (
    <div className="flex items-end gap-3 h-44 pt-2" role="img" aria-label={traducir("Cuántas peticiones cayeron en cada rango de latencia")}>
      {grupos.map(g => (
        <div key={g.etiqueta} className="flex-1 flex flex-col items-center justify-end h-full min-w-0"
          title={`${g.etiqueta}: ${formatNumber(g.n)} (${Math.round((g.n / total) * 100)}%)`}>
          <span className="text-[11px] text-ink-2 tabular mb-1">{Math.round((g.n / total) * 100)}%</span>
          <div className="w-full rounded-t-md" style={{ height: `${Math.max((g.n / max) * 100, g.n > 0 ? 2 : 0)}%`, background: g.color, minHeight: g.n > 0 ? 3 : 0 }} />
          <span className="text-[11px] text-ink-3 mt-1.5 text-center leading-tight">{g.etiqueta}</span>
        </div>
      ))}
    </div>
  )
}

// 4xx suele ser un recurso que no existe o un link viejo -molesto pero no
// necesariamente grave-; 5xx es el proxy o la red fallando de verdad. Mismo
// motivo por el que se separan en dos colores, no un rojo unico para "error".
function colorCodigoError(code: number): string {
  return code >= 500 ? 'var(--danger)' : 'var(--warn)'
}

const EXPLICACIONES: Record<Pestana, string> = {
  latencia: traducir(
    "Qué tan rápido responden los sitios a través del proxy. Un promedio alto en general puede ser el enlace; un promedio alto en un solo dominio suele ser ese sitio o servidor, no el proxy."
  ),
  errores: traducir(
    "Fallos reales de servidor o de red (502, 504, 500...) o recursos que no existen (404) -no incluye los bloqueos por política de acceso, esos ya están en Sitios/usuarios bloqueados."
  ),
}

export default function RendimientoErrores() {
  const [pestana, setPestana] = useState<Pestana>('latencia')
  const [ventana, setVentana] = useState<Ventana>('24h')
  const [latencia, setLatencia] = useState<Latencia | null>(null)
  const [errores, setErrores] = useState<ErroresHttp | null>(null)
  const [serie, setSerie] = useState<{ granularidad: 'hora' | 'dia'; puntos: Record<string, number>[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [detalle, setDetalle] = useState<{ titulo: string; filas: FilaDetalle[]; cargando: boolean; tendenciaHref: string; filtro?: 'errores' } | null>(null)

  const cargar = () => {
    const v = ventana || undefined
    if (v && v !== '1h') api.getRendimientoSerie(v).then(setSerie).catch(() => setSerie(null))
    else setSerie(null)
    Promise.all([api.getLatencia(15, v), api.getHttpErrors(15, v)])
      .then(([l, e]: [Latencia, ErroresHttp]) => {
        setLatencia(l)
        setErrores(e)
        setError(null)
      })
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setLoading(true)
    cargar()
    const interval = setInterval(cargar, 30000)
    return () => clearInterval(interval)
  }, [ventana])

  const abrirDetalleDominio = (domain: string, soloErrores = false) => {
    const tendenciaHref = `/reportes/tendencias?tipo=domain&valor=${encodeURIComponent(domain)}`
    const filtro = soloErrores ? 'errores' as const : undefined
    setDetalle({ titulo: domain, filas: [], cargando: true, tendenciaHref, filtro })
    // errors=soloErrores: desde "Por dominio" (pestaña Errores HTTP) tiene
    // que mostrar los errores reales de ese dominio, no sus últimas
    // peticiones sin filtrar -mismo bug que "Usuarios con más bloqueos" en
    // Actividad de red, mismo día (2026-09-25). Desde "Dominios más lentos"
    // (pestaña Latencia) no aplica: ahí sí interesa ver el tráfico general.
    api.getDetalle({ domain, ventana: ventana || undefined, limit: 50, errors: soloErrores })
      .then((filas: FilaDetalle[]) => setDetalle({ titulo: domain, filas, cargando: false, tendenciaHref, filtro }))
      .catch(() => setDetalle({ titulo: domain, filas: [], cargando: false, tendenciaHref, filtro }))
  }

  const PESTANAS: { id: Pestana; label: string }[] = [
    { id: 'latencia', label: traducir("Latencia") },
    { id: 'errores', label: traducir("Errores HTTP") },
  ]

  if (loading) return <LoadingState />
  if (error && !latencia && !errores) return <ErrorState text={error} onRetry={cargar} />

  const colorLatencia = '#B8860B'

  const filasLatencia = (latencia?.domains || []).map(d => ({
    etiqueta: d.domain, valor: d.avg_ms, valorFormateado: formatMs(d.avg_ms),
  }))
  const maxLatencia = Math.max(...filasLatencia.map(f => f.valor), 1)

  const totalErrores = errores?.total || 0
  const n5xx = (errores?.by_code || []).filter(c => c.code >= 500).reduce((a, c) => a + c.count, 0)
  const n4xx = Math.max(totalErrores - n5xx, 0)
  const tasaError = errores?.peticiones ? (totalErrores / errores.peticiones) * 100 : null

  const filasErroresCodigo = (errores?.by_code || []).map(c => ({
    etiqueta: String(c.code), valor: c.count, valorFormateado: formatNumber(c.count), color: colorCodigoError(c.code),
  }))
  const maxErroresCodigo = Math.max(...filasErroresCodigo.map(f => f.valor), 1)

  const filasErroresDominio = (errores?.by_domain || []).map(d => ({
    etiqueta: d.domain, valor: d.count, valorFormateado: formatNumber(d.count),
    onClick: () => abrirDetalleDominio(d.domain, true),
  }))
  const maxErroresDominio = Math.max(...filasErroresDominio.map(f => f.valor), 1)

  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Latencia y errores")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {ventana
          ? traducir("Filtrado por: {ventana} — se refresca solo, cada 30 s.", { ventana: VENTANAS.find(v => v.id === ventana)?.label || '' })
          : traducir("De las últimas 1.000 peticiones registradas — se refresca solo, cada 30 s.")}
      </p>

      {error && <div className="mb-6 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}

      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex gap-1 bg-line-soft p-1 rounded-lg w-fit">
          {PESTANAS.map(p => (
            <button
              key={p.id}
              onClick={() => setPestana(p.id)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                pestana === p.id ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <SelectorVentana value={ventana} onChange={setVentana} />
      </div>

      <p className="text-sm text-ink-2 mb-4 max-w-3xl">{EXPLICACIONES[pestana]}</p>

      {pestana === 'latencia' && (
        <>
          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <TarjetaKpi label={traducir("Promedio")} valor={latencia?.latency_avg_ms != null ? formatMs(latencia.latency_avg_ms) : '—'}
              color={colorLatenciaMs(latencia?.latency_avg_ms)} ayuda={traducir("Tiempo medio de respuesta de todas las peticiones")} />
            <TarjetaKpi label={traducir("Mediana (p50)")} valor={latencia?.latency_p50_ms != null ? formatMs(latencia.latency_p50_ms) : '—'}
              color={colorLatenciaMs(latencia?.latency_p50_ms)} ayuda={traducir("La mitad de las peticiones respondió más rápido que esto")} />
            <TarjetaKpi label={traducir("p95")} valor={latencia?.latency_p95_ms != null ? formatMs(latencia.latency_p95_ms) : '—'}
              color={colorLatenciaMs(latencia?.latency_p95_ms)} ayuda={traducir("El 95 % respondió más rápido que esto: muestra los casos lentos")} />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
            <TarjetaGrafico titulo={traducir("Latencia a lo largo del tiempo")} subtitulo={traducir("Tiempo medio de respuesta por periodo")}>
              {serie && serie.puntos.length > 0 ? (
                <GraficoTiempo datos={serie.puntos as any} granularidad={serie.granularidad} altura={190} formatoEje={formatMs}
                  series={[{ key: 'latencia_ms', label: traducir('Latencia media'), color: MARCA, formato: formatMs }]} />
              ) : <p className="text-sm text-ink-3 py-6">{ventana === '1h' ? traducir("Esta gráfica necesita una ventana de 24 h o más.") : traducir("Sin datos todavía.")}</p>}
            </TarjetaGrafico>
            <TarjetaGrafico titulo={traducir("¿Qué tan rápidas son las peticiones?")} subtitulo={traducir("Cuántas peticiones cayeron en cada rango de latencia")}>
              {latencia?.histograma ? <Histograma datos={latencia.histograma} /> : <p className="text-sm text-ink-3 py-6">{traducir("Elige una ventana de 24 h o más para ver la distribución.")}</p>}
            </TarjetaGrafico>
          </div>

          <div className="card p-5">
            <h3 className="text-sm font-semibold text-ink mb-1">{traducir("Dominios más lentos")}</h3>
            <p className="text-[12px] text-ink-3 mb-3">{traducir("Haz clic en un dominio para ver sus últimas peticiones.")}</p>
            {filasLatencia.length === 0 ? (
              <p className="text-sm text-ink-3 text-center py-8">{traducir("Sin datos todavía.")}</p>
            ) : (
              <div className="flex flex-col">
                {filasLatencia.map((f, i) => (
                  <FilaBarra key={f.etiqueta} posicion={i + 1} etiqueta={f.etiqueta} valor={f.valor}
                    valorFormateado={f.valorFormateado} maximo={maxLatencia} color={colorLatenciaMs(f.valor) ?? colorLatencia}
                    onClick={() => abrirDetalleDominio(f.etiqueta)} />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {pestana === 'errores' && (
        <>
          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <TarjetaKpi label={traducir("Total de errores")} valor={formatNumber(totalErrores)} color={totalErrores > 0 ? ESTADO.aviso : ESTADO.ok}
              ayuda={traducir("Fallos de servidor o de red y recursos que no existen")} />
            <TarjetaKpi label={traducir("Tasa de error")} valor={tasaError != null ? `${tasaError.toFixed(2)} %` : '—'}
              color={tasaError == null ? undefined : tasaError < 1 ? ESTADO.ok : tasaError < 5 ? ESTADO.aviso : ESTADO.error}
              ayuda={traducir("Errores sobre el total de peticiones de la ventana")} />
            <TarjetaKpi label={traducir("Errores del servidor (5xx)")} valor={formatNumber(n5xx)} color={n5xx > 0 ? ESTADO.error : ESTADO.ok}
              ayuda={traducir("El sitio o la red fallaron: lo más importante de revisar")} />
            <TarjetaKpi label={traducir("No encontrados (4xx)")} valor={formatNumber(n4xx)}
              ayuda={traducir("Enlaces rotos o recursos que ya no existen")} />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-5 gap-4 mb-4">
            <TarjetaGrafico titulo={traducir("Errores del servidor frente a no encontrados")} subtitulo={traducir("Cómo se reparten los errores")} className="xl:col-span-2">
              {totalErrores > 0 ? (
                <DonaReparto altura={170} formato={formatNumber} centro={{ titulo: traducir('errores'), valor: formatNumber(totalErrores) }}
                  items={[
                    { nombre: traducir('Servidor (5xx)'), valor: n5xx, color: ESTADO.error },
                    { nombre: traducir('No encontrado y similares (4xx)'), valor: n4xx, color: ESTADO.aviso },
                  ]} />
              ) : <p className="text-sm text-ink-3 py-6">{traducir("Sin errores en esta ventana. 🎉")}</p>}
            </TarjetaGrafico>
            <TarjetaGrafico titulo={traducir("Errores a lo largo del tiempo")} subtitulo={traducir("Cuándo fallaron más las peticiones")} className="xl:col-span-3">
              {serie && serie.puntos.length > 0 ? (
                <GraficoBarras datos={serie.puntos as any} granularidad={serie.granularidad} altura={190} formatoEje={formatNumber}
                  series={[{ key: 'errores', label: traducir('Errores'), color: ESTADO.error, formato: formatNumber }]} />
              ) : <p className="text-sm text-ink-3 py-6">{ventana === '1h' ? traducir("Esta gráfica necesita una ventana de 24 h o más.") : traducir("Sin datos todavía.")}</p>}
            </TarjetaGrafico>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-ink mb-3">{traducir("Por código de error")}</h3>
              {filasErroresCodigo.length === 0 ? (
                <p className="text-sm text-ink-3 text-center py-8">{traducir("Sin datos todavía.")}</p>
              ) : (
                <div className="flex flex-col">
                  {filasErroresCodigo.map((f, i) => (
                    <FilaBarra key={f.etiqueta} posicion={i + 1} etiqueta={f.etiqueta} valor={f.valor}
                      valorFormateado={f.valorFormateado} maximo={maxErroresCodigo} color={f.color} />
                  ))}
                </div>
              )}
            </div>
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-ink mb-3">{traducir("Por dominio")}</h3>
              {filasErroresDominio.length === 0 ? (
                <p className="text-sm text-ink-3 text-center py-8">{traducir("Sin datos todavía.")}</p>
              ) : (
                <div className="flex flex-col">
                  {filasErroresDominio.map((f, i) => (
                    <FilaBarra key={f.etiqueta} posicion={i + 1} etiqueta={f.etiqueta} valor={f.valor}
                      valorFormateado={f.valorFormateado} maximo={maxErroresDominio} color="var(--danger)" onClick={f.onClick} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {detalle && (
        <ModalDetalle
          titulo={detalle.titulo}
          filas={detalle.filas}
          cargando={detalle.cargando}
          onClose={() => setDetalle(null)}
          tendenciaHref={detalle.tendenciaHref}
          filtro={detalle.filtro}
        />
      )}
    </div>
  )
}
