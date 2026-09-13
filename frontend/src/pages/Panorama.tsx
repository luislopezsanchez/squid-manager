import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'
import { niceCeilBytes, niceCeil } from '../utils/chart'
import { SelectorVentana, type Ventana } from '../components/ReportWidgets'
import { LineAreaChart } from '../components/LineAreaChart'

type Granularidad = 'minuto' | 'hora' | 'dia'
type Punto = { timestamp: number; bytes: number; requests: number }

/** Toggle Datos/Peticiones. */
function ToggleMetrica({ porDatos, onChange }: { porDatos: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex gap-1 bg-line-soft p-1 rounded-lg">
      <button
        onClick={() => onChange(true)}
        className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${porDatos ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}
      >
        {traducir("Datos")}
      </button>
      <button
        onClick={() => onChange(false)}
        className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${!porDatos ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}
      >
        {traducir("Peticiones")}
      </button>
    </div>
  )
}

// Formato de etiqueta según la granularidad que eligió el backend -no el
// frontend: es el backend el que decide si el balde es de 5 min, de una
// hora o de un día calendario (ver get_volumen_por_periodo), acá solo se
// traduce ese timestamp a texto legible.
function formatearEtiqueta(ts: number, granularidad: Granularidad): string {
  const d = new Date(ts * 1000)
  if (granularidad === 'dia') {
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatearFechaCompleta(ts: number, granularidad: Granularidad): string {
  const d = new Date(ts * 1000)
  const fecha = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  if (granularidad === 'dia') return fecha
  return `${fecha} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function VolumenPorPeriodo() {
  const [ventana, setVentana] = useState<Ventana>('7d')
  const [porDatos, setPorDatos] = useState(true)
  const [granularidad, setGranularidad] = useState<Granularidad>('dia')
  const [puntos, setPuntos] = useState<Punto[] | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const cargar = () => api.getVolumenPorPeriodo(ventana || undefined).then(r => {
      setGranularidad(r.granularidad)
      setPuntos(r.puntos)
    }).finally(() => setLoading(false))
    cargar()
    const interval = setInterval(cargar, 30000)
    return () => clearInterval(interval)
  }, [ventana])

  const datos = puntos || []
  const valores = datos.map(d => (porDatos ? d.bytes : d.requests))
  const techo = porDatos ? niceCeilBytes(Math.max(...valores, 1)) : niceCeil(Math.max(...valores, 1))
  const formatearValor = porDatos ? formatBytes : formatNumber
  const total = valores.reduce((a, b) => a + b, 0)
  const pico = datos.length > 0
    ? datos.reduce((max, d) => (porDatos ? d.bytes : d.requests) > (porDatos ? max.bytes : max.requests) ? d : max, datos[0])
    : null

  // Con muchos puntos (30 dias, o 288 baldes de 5 min en 1h) mostrar todas
  // las etiquetas se pisa -se muestra una de cada varias, el tooltip por
  // punto sigue teniendo la fecha/hora completa.
  const paso = Math.max(1, Math.ceil(datos.length / 10))
  const ejeXLabels = datos.map((d, i) => (i % paso === 0 ? formatearEtiqueta(d.timestamp, granularidad) : ''))

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold text-ink">{traducir("Volumen de tráfico")}</h3>
        <div className="flex items-center gap-3">
          <SelectorVentana value={ventana} onChange={setVentana} />
          <ToggleMetrica porDatos={porDatos} onChange={setPorDatos} />
        </div>
      </div>
      <p className="text-sm text-ink-2 mb-4 max-w-3xl">
        {traducir("El tamaño de cada barra se adapta a la ventana elegida: minutos u horas para ventanas cortas, un día calendario por barra para ventanas de 7 o 30 días. Sirve para ver cuándo pesa más el tráfico y si viene creciendo o hubo un pico puntual.")}
      </p>

      {loading ? (
        <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>
      ) : total === 0 ? (
        <div className="card p-8 border border-line-soft text-center text-ink-3">{traducir("Sin datos todavía.")}</div>
      ) : (
        <>
          {pico && (
            <div className="card p-4 mb-4 w-fit">
              <p className="text-xs text-ink-3 mb-1">
                {granularidad === 'dia' ? traducir("Día con más tráfico") : traducir("Momento con más tráfico")}
              </p>
              <p className="text-2xl font-bold text-ink">{formatearFechaCompleta(pico.timestamp, granularidad)}</p>
            </div>
          )}
          <div className="card p-6">
            <LineAreaChart
              valores={valores}
              techo={techo}
              formatearValor={formatearValor}
              ejeXLabels={ejeXLabels}
              tooltipFor={i => `${formatearFechaCompleta(datos[i].timestamp, granularidad)} — ${
                porDatos ? formatBytes(datos[i].bytes) : `${formatNumber(datos[i].requests)} ${traducir("req")}`
              }`}
            />
          </div>
        </>
      )}
    </div>
  )
}

export default function Panorama() {
  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Panorama")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Cómo se comporta la navegación en general -no un usuario o sitio puntual, sino el tráfico de todos.")}
      </p>

      <VolumenPorPeriodo />
    </div>
  )
}
