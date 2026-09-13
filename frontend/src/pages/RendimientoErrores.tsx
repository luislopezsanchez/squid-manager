import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatNumber, formatMs } from '../utils/format'
import {
  FilaBarra, AnilloConcentracion, ModalDetalle, SelectorVentana, VENTANAS,
  type FilaDetalle, type Ventana,
} from '../components/ReportWidgets'

type Latencia = {
  latency_avg_ms: number | null
  latency_p50_ms: number | null
  latency_p95_ms: number | null
  domains: { domain: string; avg_ms: number; samples: number }[]
}
type ErroresHttp = {
  total: number
  by_code: { code: number; count: number }[]
  by_domain: { domain: string; count: number }[]
}

type Pestana = 'latencia' | 'errores'

function TarjetaKpi({ label, valor }: { label: string; valor: string }) {
  return (
    <div className="card p-4 flex-1">
      <p className="text-xs text-ink-3 mb-1">{label}</p>
      <p className="text-2xl font-bold text-ink tabular">{valor}</p>
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
  const [ventana, setVentana] = useState<Ventana>('')
  const [latencia, setLatencia] = useState<Latencia | null>(null)
  const [errores, setErrores] = useState<ErroresHttp | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [detalle, setDetalle] = useState<{ titulo: string; filas: FilaDetalle[]; cargando: boolean; tendenciaHref: string } | null>(null)

  const cargar = () => {
    const v = ventana || undefined
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

  const abrirDetalleDominio = (domain: string) => {
    const tendenciaHref = `/reportes/tendencias?tipo=domain&valor=${encodeURIComponent(domain)}`
    setDetalle({ titulo: domain, filas: [], cargando: true, tendenciaHref })
    api.getDetalle({ domain, ventana: ventana || undefined, limit: 50 })
      .then((filas: FilaDetalle[]) => setDetalle({ titulo: domain, filas, cargando: false, tendenciaHref }))
      .catch(() => setDetalle({ titulo: domain, filas: [], cargando: false, tendenciaHref }))
  }

  const PESTANAS: { id: Pestana; label: string }[] = [
    { id: 'latencia', label: traducir("Latencia") },
    { id: 'errores', label: traducir("Errores HTTP") },
  ]

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  const colorLatencia = '#B8860B'

  const filasLatencia = (latencia?.domains || []).map(d => ({
    etiqueta: d.domain, valor: d.avg_ms, valorFormateado: formatMs(d.avg_ms),
  }))
  const maxLatencia = Math.max(...filasLatencia.map(f => f.valor), 1)

  const totalErrores = errores?.total || 0

  const filasErroresCodigo = (errores?.by_code || []).map(c => ({
    etiqueta: String(c.code), valor: c.count, valorFormateado: formatNumber(c.count), color: colorCodigoError(c.code),
  }))
  const maxErroresCodigo = Math.max(...filasErroresCodigo.map(f => f.valor), 1)
  const top3Codigo = filasErroresCodigo.slice(0, 3).reduce((acc, f) => acc + f.valor, 0)
  const pctTop3Codigo = totalErrores > 0 ? (top3Codigo / totalErrores) * 100 : 0

  const filasErroresDominio = (errores?.by_domain || []).map(d => ({
    etiqueta: d.domain, valor: d.count, valorFormateado: formatNumber(d.count),
    onClick: () => abrirDetalleDominio(d.domain),
  }))
  const maxErroresDominio = Math.max(...filasErroresDominio.map(f => f.valor), 1)
  const top3Dominio = filasErroresDominio.slice(0, 3).reduce((acc, f) => acc + f.valor, 0)
  const pctTop3Dominio = totalErrores > 0 ? (top3Dominio / totalErrores) * 100 : 0

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
            <TarjetaKpi label={traducir("Promedio")} valor={latencia?.latency_avg_ms != null ? formatMs(latencia.latency_avg_ms) : '—'} />
            <TarjetaKpi label={traducir("Mediana (p50)")} valor={latencia?.latency_p50_ms != null ? formatMs(latencia.latency_p50_ms) : '—'} />
            <TarjetaKpi label={traducir("p95")} valor={latencia?.latency_p95_ms != null ? formatMs(latencia.latency_p95_ms) : '—'} />
          </div>
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-ink mb-3">{traducir("Dominios más lentos")}</h3>
            {filasLatencia.length === 0 ? (
              <p className="text-sm text-ink-3 text-center py-8">{traducir("Sin datos todavía.")}</p>
            ) : (
              <div className="flex flex-col">
                {filasLatencia.map((f, i) => (
                  <FilaBarra key={f.etiqueta} posicion={i + 1} etiqueta={f.etiqueta} valor={f.valor}
                    valorFormateado={f.valorFormateado} maximo={maxLatencia} color={colorLatencia}
                    onClick={() => abrirDetalleDominio(f.etiqueta)} />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {pestana === 'errores' && (
        <>
          <div className="mb-4">
            <TarjetaKpi label={traducir("Total de errores")} valor={formatNumber(totalErrores)} />
          </div>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4">
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
              {filasErroresCodigo.length > 0 && (
                <div className="card p-5 flex items-center justify-center w-full lg:w-64">
                  <AnilloConcentracion pct={pctTop3Codigo} color="var(--danger)" total={totalErrores} totalFormateado={formatNumber(totalErrores)} />
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4">
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
              {filasErroresDominio.length > 0 && (
                <div className="card p-5 flex items-center justify-center w-full lg:w-64">
                  <AnilloConcentracion pct={pctTop3Dominio} color="var(--danger)" total={totalErrores} totalFormateado={formatNumber(totalErrores)} />
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
        />
      )}
    </div>
  )
}
