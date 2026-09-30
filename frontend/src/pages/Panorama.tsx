import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatBytes, formatNumber, formatMs } from '../utils/format'
import { LoadingState, ErrorState } from '../components/AsyncState'
import {
  DonaReparto, GraficoBarras, GraficoTiempo, Indicador, MapaCalor, Ranking, TarjetaGrafico,
  ESTADO, MARCA, SERIE,
} from '../components/charts'
import { IconAlert, IconCheck } from '../components/Icons'

type Ventana = '24h' | '7d' | '30d'
const VENTANAS: { id: Ventana; etiqueta: string }[] = [
  { id: '24h', etiqueta: '24 horas' }, { id: '7d', etiqueta: '7 días' }, { id: '30d', etiqueta: '30 días' },
]

interface Kpis {
  requests: number; bytes: number; denied: number; errors: number
  cache_hit_ratio: number | null; cache_bytes_saved: number; latency_avg_ms: number | null
  users: number; domains: number
}
interface Datos {
  disponible: boolean
  granularidad: 'hora' | 'dia'
  actual: Kpis; anterior: Kpis
  serie: { timestamp: number; requests: number; bytes: number; denied: number; errors: number; hits: number; misses: number }[]
  clases_http: Record<string, number>
  mapa_calor: number[][]
  top_usuarios: { user: string; bytes: number; requests: number }[]
  top_dominios: { domain: string; requests: number; bytes: number }[]
  top_bloqueados_dominio: { domain: string; requests: number }[]
  top_bloqueados_usuario: { user: string; blocked_requests: number }[]
  cuotas: { en_riesgo: number; excedidas: { tipo: string; nombre: string; quota_bytes: number; quota_bytes_used: number; quota_action: string }[] }
  anomalias: { timestamp?: number; tipo?: string; mensaje?: string; detalle?: string; entidad?: string; [k: string]: any }[]
}

export default function Panorama() {
  const [ventana, setVentana] = useState<Ventana>('24h')
  const [datos, setDatos] = useState<Datos | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    setCargando(true)
    const cargar = () => api.getPanorama(ventana)
      .then((d: Datos) => { setDatos(d); setError(false) })
      .catch(() => setError(true))
      .finally(() => setCargando(false))
    cargar()
    const id = setInterval(cargar, 60000)
    return () => clearInterval(id)
  }, [ventana])

  const Selector = (
    <div className="flex gap-1 bg-line-soft p-1 rounded-lg" role="tablist" aria-label={traducir("Ventana de tiempo")}>
      {VENTANAS.map(v => (
        <button key={v.id} role="tab" aria-selected={ventana === v.id} onClick={() => setVentana(v.id)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${ventana === v.id ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}>
          {traducir(v.etiqueta)}
        </button>
      ))}
    </div>
  )

  const cabecera = (
    <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
      <div>
        <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Panorama")}</h1>
        <p className="text-sm text-ink-3 max-w-2xl">
          {traducir("El estado general del servicio de un vistazo: cuánto se navega, qué se bloquea, cómo responde el proxy y qué requiere tu atención.")}
        </p>
      </div>
      {Selector}
    </div>
  )

  if (cargando && !datos) return <div className="p-6 md:p-8">{cabecera}<LoadingState /></div>
  if (error && !datos) return <div className="p-6 md:p-8">{cabecera}<ErrorState onRetry={() => setVentana(v => v)} /></div>
  if (!datos || !datos.disponible) {
    return (
      <div className="p-6 md:p-8">{cabecera}
        <div className="card p-8 text-center text-ink-3">
          {traducir("Los datos del análisis se están preparando (se calculan en segundo plano al arrancar). Vuelve a intentarlo en un minuto.")}
        </div>
      </div>
    )
  }

  const { actual, anterior } = datos
  const serie = datos.serie.map(s => ({ ...s, permitidas: Math.max(s.requests - s.denied, 0) }))
  const serieCache = datos.serie.map(s => ({
    timestamp: s.timestamp,
    // Sin tráfico cacheable en esa hora no hay porcentaje (null = hueco): un 0% inventado parecería una caída de la caché.
    acierto: s.hits + s.misses > 0 ? Math.round((s.hits / (s.hits + s.misses)) * 1000) / 10 : (null as any),
  }))
  const c = datos.clases_http
  const reparto = [
    { nombre: traducir('Correctas (2xx)'), valor: c['2xx'], color: SERIE[2] },
    { nombre: traducir('Redirecciones (3xx)'), valor: c['3xx'], color: SERIE[0] },
    { nombre: traducir('Bloqueadas por política'), valor: c.politica, color: SERIE[3] },
    { nombre: traducir('Errores del cliente (4xx)'), valor: c['4xx'], color: SERIE[1] },
    { nombre: traducir('Errores del servidor (5xx)'), valor: c['5xx'], color: ESTADO.error },
  ]
  const sinActividad = actual.requests === 0
  const hayAlertas = datos.cuotas.excedidas.length > 0 || datos.cuotas.en_riesgo > 0 || datos.anomalias.length > 0

  return (
    <div className="p-6 md:p-8">
      {cabecera}

      {sinActividad && (
        <div className="note note-info mb-6"><p className="note-text">{traducir("No hay actividad registrada en esta ventana todavía.")}</p></div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">
        <Indicador titulo={traducir("Peticiones")} valor={formatNumber(actual.requests)} actual={actual.requests} anterior={anterior.requests} />
        <Indicador titulo={traducir("Tráfico")} valor={formatBytes(actual.bytes)} actual={actual.bytes} anterior={anterior.bytes} />
        <Indicador titulo={traducir("Bloqueos")} valor={formatNumber(actual.denied)} actual={actual.denied} anterior={anterior.denied} masEsMejor={false}
          ayuda={traducir("Peticiones denegadas por la política de acceso (401/403/407).")} />
        <Indicador titulo={traducir("Errores")} valor={formatNumber(actual.errors)} actual={actual.errors} anterior={anterior.errors} masEsMejor={false}
          ayuda={traducir("Fallos reales de red o de servidores (404, 500, 502...), sin contar bloqueos.")} />
        <Indicador titulo={traducir("Acierto de caché")} valor={actual.cache_hit_ratio == null ? '—' : `${actual.cache_hit_ratio}%`}
          actual={actual.cache_hit_ratio} anterior={anterior.cache_hit_ratio} />
        <Indicador titulo={traducir("Latencia media")} valor={actual.latency_avg_ms == null ? '—' : formatMs(actual.latency_avg_ms)}
          actual={actual.latency_avg_ms} anterior={anterior.latency_avg_ms} masEsMejor={false}
          ayuda={traducir("Tiempo medio de respuesta, sin contar túneles HTTPS.")} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
        <TarjetaGrafico titulo={traducir("Tráfico transferido")} subtitulo={traducir("Datos descargados a través del proxy")}>
          <GraficoTiempo datos={serie} granularidad={datos.granularidad} formatoEje={formatBytes}
            series={[{ key: 'bytes', label: traducir('Tráfico'), color: MARCA, formato: formatBytes }]} />
        </TarjetaGrafico>
        <TarjetaGrafico titulo={traducir("Peticiones: permitidas y bloqueadas")} subtitulo={traducir("Las bloqueadas se apilan sobre las permitidas")}>
          <GraficoBarras datos={serie} granularidad={datos.granularidad} formatoEje={formatNumber}
            series={[
              { key: 'permitidas', label: traducir('Permitidas'), color: SERIE[0], formato: formatNumber },
              { key: 'denied', label: traducir('Bloqueadas'), color: SERIE[1], formato: formatNumber },
            ]} />
        </TarjetaGrafico>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
        <TarjetaGrafico titulo={traducir("Cómo responde el servicio")} subtitulo={traducir("Reparto de las respuestas por tipo")} className="xl:col-span-1">
          <DonaReparto items={reparto} formato={formatNumber} centro={{ titulo: traducir('peticiones'), valor: formatNumber(actual.requests) }} />
        </TarjetaGrafico>
        <TarjetaGrafico titulo={traducir("Acierto de caché")} subtitulo={traducir("Porcentaje de peticiones servidas desde la caché")} className="xl:col-span-2">
          <GraficoTiempo datos={serieCache} granularidad={datos.granularidad} altura={190} formatoEje={(n: number) => `${n}%`}
            series={[{ key: 'acierto', label: traducir('Acierto'), color: SERIE[2], formato: (n: number) => `${n}%` }]} />
          <p className="text-[12px] text-ink-3 mt-2">
            {traducir("Ahorro estimado en el periodo")}: <strong className="text-ink">{formatBytes(actual.cache_bytes_saved)}</strong>
          </p>
        </TarjetaGrafico>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <TarjetaGrafico titulo={traducir("Usuarios que más consumen")}>
          <Ranking filas={datos.top_usuarios.map(u => ({ nombre: u.user, valor: u.bytes, sub: `${formatNumber(u.requests)} ${traducir('peticiones')}` }))}
            formato={formatBytes} onClick={u => navigate(`/reportes/tendencias?tipo=user&valor=${encodeURIComponent(u)}`)} />
        </TarjetaGrafico>
        <TarjetaGrafico titulo={traducir("Sitios más visitados")}>
          <Ranking color={SERIE[1]} filas={datos.top_dominios.map(d => ({ nombre: d.domain, valor: d.requests, sub: formatBytes(d.bytes) }))}
            formato={formatNumber} onClick={d => navigate(`/reportes/tendencias?tipo=domain&valor=${encodeURIComponent(d)}`)} />
        </TarjetaGrafico>
        <TarjetaGrafico titulo={traducir("Sitios más bloqueados")}>
          <Ranking color={ESTADO.error} filas={datos.top_bloqueados_dominio.map(d => ({ nombre: d.domain, valor: d.requests }))}
            formato={formatNumber} vacio={traducir("No se bloqueó ningún sitio.")} />
        </TarjetaGrafico>
        <TarjetaGrafico titulo={traducir("Usuarios con más bloqueos")}>
          <Ranking color={ESTADO.aviso} filas={datos.top_bloqueados_usuario.map(u => ({ nombre: u.user, valor: u.blocked_requests }))}
            formato={formatNumber} vacio={traducir("Ningún usuario chocó con la política.")} />
        </TarjetaGrafico>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
        <TarjetaGrafico titulo={traducir("Requiere tu atención")} className="xl:col-span-1"
          subtitulo={traducir("Cuotas y avisos de seguridad recientes")}>
          {!hayAlertas ? (
            <p className="flex items-center gap-2 text-sm text-ok"><IconCheck className="w-4 h-4" />{traducir("Todo en orden: sin cuotas agotadas ni alertas.")}</p>
          ) : (
            <ul className="space-y-2.5 text-[13px]">
              {datos.cuotas.excedidas.slice(0, 5).map(q => (
                <li key={`${q.tipo}-${q.nombre}`} className="flex items-start gap-2">
                  <IconAlert className="w-4 h-4 flex-none mt-0.5 text-danger" />
                  <span><strong className="text-ink">{q.nombre}</strong> {traducir("agotó su cuota")} ({formatBytes(q.quota_bytes_used)} / {formatBytes(q.quota_bytes)})</span>
                </li>
              ))}
              {datos.cuotas.en_riesgo > 0 && (
                <li className="flex items-start gap-2">
                  <IconAlert className="w-4 h-4 flex-none mt-0.5" />
                  <span>{traducir("{n} cuotas están por encima del 80%", { n: datos.cuotas.en_riesgo })}</span>
                </li>
              )}
              {datos.anomalias.slice(0, 5).map((a, i) => (
                <li key={i} className="flex items-start gap-2">
                  <IconAlert className="w-4 h-4 flex-none mt-0.5" />
                  <span className="text-ink-2">{a.asunto ? `${a.asunto}: ` : ''}{a.mensaje || traducir('Anomalía detectada')}</span>
                </li>
              ))}
            </ul>
          )}
          <Link to="/cuotas" className="inline-block text-[12px] font-semibold mt-4" style={{ color: 'var(--brand-700)' }}>{traducir("Ver cuotas →")}</Link>
        </TarjetaGrafico>
        <TarjetaGrafico titulo={traducir("Cuándo se navega")} className="xl:col-span-2"
          subtitulo={traducir("Peticiones por día de la semana y hora: sirve para dimensionar y para detectar actividad fuera de horario.")}>
          <MapaCalor matriz={datos.mapa_calor} formato={n => `${formatNumber(n)} ${traducir('peticiones')}`} />
        </TarjetaGrafico>
      </div>

      <p className="text-[12px] text-ink-3">
        {traducir("Los datos se calculan por hora en segundo plano: la ventana empieza al inicio de la hora correspondiente y se actualiza cada minuto.")}
      </p>
    </div>
  )
}
