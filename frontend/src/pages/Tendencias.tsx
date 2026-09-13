import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'
import { niceCeilBytes, niceCeil } from '../utils/chart'
import { SelectorVentana, type Ventana } from '../components/ReportWidgets'
import { LineAreaChart } from '../components/LineAreaChart'
import { IconActivity } from '../components/Icons'

type Punto = { timestamp: number; bytes: number; requests: number }
type Tendencia = { points: Punto[]; user: string | null; domain: string | null }
type Tipo = 'user' | 'domain'

export default function Tendencias() {
  const [params, setParams] = useSearchParams()
  const [tipo, setTipo] = useState<Tipo>((params.get('tipo') as Tipo) || 'user')
  const [valorInput, setValorInput] = useState(params.get('valor') || '')
  const [valorActivo, setValorActivo] = useState(params.get('valor') || '')
  const [ventana, setVentana] = useState<Ventana>('')
  const [porDatos, setPorDatos] = useState(true)
  const [tendencia, setTendencia] = useState<Tendencia | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const cargar = () => {
    if (!valorActivo) return
    setLoading(true)
    api.getTendenciaTrafico({ [tipo]: valorActivo, ventana: ventana || undefined, buckets: 20 })
      .then((t: Tendencia) => { setTendencia(t); setError(null) })
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    cargar()
    if (!valorActivo) return
    const interval = setInterval(cargar, 30000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valorActivo, tipo, ventana])

  const buscar = () => {
    const v = valorInput.trim()
    setValorActivo(v)
    setParams(v ? { tipo, valor: v } : {})
  }

  const puntos = tendencia?.points || []
  const valores = puntos.map(p => (porDatos ? p.bytes : p.requests))
  const total = valores.reduce((a, b) => a + b, 0)
  const promedio = puntos.length > 0 ? total / puntos.length : 0
  const pico = Math.max(...valores, 0)

  const techo = porDatos ? niceCeilBytes(pico) : niceCeil(pico)
  const formatearValor = porDatos ? formatBytes : formatNumber

  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Tendencias")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Cómo evolucionó un usuario o sitio a lo largo del tiempo.")}
      </p>

      <div className="card p-4 mb-4 flex flex-wrap items-end gap-3">
        <div className="flex gap-1 bg-line-soft p-1 rounded-lg">
          <button
            onClick={() => setTipo('user')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${tipo === 'user' ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}
          >
            {traducir("Usuario")}
          </button>
          <button
            onClick={() => setTipo('domain')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${tipo === 'domain' ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}
          >
            {traducir("Dominio")}
          </button>
        </div>
        <div className="flex-1 min-w-[180px]">
          <label htmlFor="tendencia-valor" className="block text-xs font-medium text-ink-3 mb-1">
            {tipo === 'user' ? traducir("Nombre de usuario") : traducir("Dominio")}
          </label>
          <input
            id="tendencia-valor"
            type="text"
            value={valorInput}
            onChange={e => setValorInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && buscar()}
            placeholder={tipo === 'user' ? 'mgomez' : 'github.com'}
            className="input text-sm"
          />
        </div>
        <button onClick={buscar}
          className="px-4 py-2 text-white rounded-lg text-sm font-medium" style={{ backgroundColor: '#0B497C' }}>
          {traducir("Ver tendencia")}
        </button>
        <SelectorVentana value={ventana} onChange={setVentana} />
      </div>

      {error && <div className="mb-6 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}

      {!valorActivo ? (
        <div className="card p-8 border border-line-soft flex flex-col items-center text-center gap-3">
          <span className="stat-icon"><IconActivity /></span>
          <p className="text-ink-2">{traducir("Elige un usuario o dominio para ver su evolución en el tiempo.")}</p>
        </div>
      ) : loading ? (
        <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>
      ) : puntos.length === 0 ? (
        <div className="card p-8 border border-line-soft text-center text-ink-3">
          {traducir("Sin datos todavía.")}
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink">{valorActivo}</h2>
            <div className="flex gap-1 bg-line-soft p-1 rounded-lg">
              <button
                onClick={() => setPorDatos(true)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${porDatos ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}
              >
                {traducir("Datos")}
              </button>
              <button
                onClick={() => setPorDatos(false)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${!porDatos ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}
              >
                {traducir("Peticiones")}
              </button>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <div className="card p-4 flex-1">
              <p className="text-xs text-ink-3 mb-1">{traducir("Total del período")}</p>
              <p className="text-2xl font-bold text-ink tabular">{formatearValor(total)}</p>
            </div>
            <div className="card p-4 flex-1">
              <p className="text-xs text-ink-3 mb-1">{traducir("Promedio por intervalo")}</p>
              <p className="text-2xl font-bold text-ink tabular">{formatearValor(promedio)}</p>
            </div>
            <div className="card p-4 flex-1">
              <p className="text-xs text-ink-3 mb-1">{traducir("Pico")}</p>
              <p className="text-2xl font-bold text-ink tabular">{formatearValor(pico)}</p>
            </div>
          </div>

          <div className="card p-6">
            <LineAreaChart
              valores={valores}
              techo={techo}
              formatearValor={formatearValor}
              tooltipFor={i => `${new Date(puntos[i].timestamp * 1000).toLocaleString()} — ${
                porDatos ? formatBytes(puntos[i].bytes) : `${formatNumber(puntos[i].requests)} ${traducir("req")}`
              }`}
            />
          </div>
        </>
      )}
    </div>
  )
}
