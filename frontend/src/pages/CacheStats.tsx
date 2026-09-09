import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { IconGauge, IconDashboard, IconArchive, IconEye } from '../components/Icons'

type InfoCache = {
  version: string | null
  uptime_segundos: number | null
  hits_peticiones_5min: number | null
  hits_peticiones_60min: number | null
  hits_bytes_5min: number | null
  hits_bytes_60min: number | null
  hits_memoria_5min: number | null
  hits_memoria_60min: number | null
  hits_disco_5min: number | null
  hits_disco_60min: number | null
  swap_size_kb: number | null
  swap_capacidad_pct: number | null
  mem_size_kb: number | null
  objeto_medio_kb: number | null
  ratio_fallos: number | null
  clientes_activos: number | null
  peticiones_recibidas: number | null
}

type StoreDir = {
  entradas: number | null
  tamano_maximo_kb: number | null
  tamano_actual_kb: number | null
  capacidad_pct: number | null
}

type Estadisticas = { info: InfoCache | null; storedir: StoreDir | null; errores: string[] }

function formatKB(kb: number | null | undefined): string {
  if (kb === null || kb === undefined) return '—'
  if (kb >= 1024 * 1024) return `${(kb / (1024 * 1024)).toFixed(2)} GB`
  if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`
  return `${kb.toFixed(0)} KB`
}

function formatPct(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : `${v.toFixed(1)}%`
}

function formatUptime(segundos: number | null | undefined): string {
  if (!segundos) return '—'
  const dias = Math.floor(segundos / 86400)
  const horas = Math.floor((segundos % 86400) / 3600)
  const minutos = Math.floor((segundos % 3600) / 60)
  if (dias > 0) return traducir("{dias}d {horas}h", { dias, horas })
  if (horas > 0) return traducir("{horas}h {minutos}m", { horas, minutos })
  return traducir("{minutos}m", { minutos })
}

function Tarjeta({ titulo, valor, Icon, color, detalle }: {
  titulo: string; valor: string; Icon: (p: { className?: string }) => JSX.Element; color: string; detalle?: string
}) {
  return (
    <div className="card p-5 border border-line-soft">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm text-ink-3">{titulo}</h3>
        <span className="stat-icon"><Icon /></span>
      </div>
      <p className="text-2xl font-bold tabular" style={{ color }}>{valor}</p>
      {detalle && <p className="text-xs text-ink-3 mt-1">{detalle}</p>}
    </div>
  )
}

export default function CacheStats() {
  const [datos, setDatos] = useState<Estadisticas | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const cargar = () => {
    api.getCacheStats()
      .then(setDatos)
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    cargar()
    // El Cache Manager de Squid cambia todo el tiempo -igual que el
    // dashboard, un refresco periodico sin que el admin tenga que recargar
    // la pagina a mano.
    const interval = setInterval(cargar, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  const info = datos?.info
  const storedir = datos?.storedir

  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Estadísticas de caché")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Lo que el propio Squid reporta sobre su caché -Cache Manager-, no una estimación calculada aparte.")}
      </p>

      {error && (
        <div className="mb-6 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>
      )}

      {datos?.errores && datos.errores.length > 0 && (
        <div className="mb-6 bg-warn-soft text-warn text-[13px] p-3 rounded-lg">
          {traducir("Squid no respondió completo: {detalle}", { detalle: datos.errores.join(' · ') })}
        </div>
      )}

      {!error && !info && !storedir && (
        <div className="card p-6 text-center text-ink-3">
          {traducir("Sin datos todavía. Squid puede estar recién iniciado, o el Cache Manager no respondió.")}
        </div>
      )}

      {(info || storedir) && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
            <Tarjeta
              titulo={traducir("Aciertos por bytes (60 min)")}
              valor={formatPct(info?.hits_bytes_60min)}
              Icon={IconGauge}
              color="#0B497C"
              detalle={traducir("5 min: {v}", { v: formatPct(info?.hits_bytes_5min) })}
            />
            <Tarjeta
              titulo={traducir("Aciertos por petición (60 min)")}
              valor={formatPct(info?.hits_peticiones_60min)}
              Icon={IconDashboard}
              color="#2E93BC"
              detalle={traducir("Memoria {m} · Disco {d}", {
                m: formatPct(info?.hits_memoria_60min), d: formatPct(info?.hits_disco_60min),
              })}
            />
            <Tarjeta
              titulo={traducir("Caché en disco")}
              valor={formatKB(storedir?.tamano_actual_kb)}
              Icon={IconArchive}
              color="#0A2C48"
              detalle={traducir("de {max} · {pct} usado", {
                max: formatKB(storedir?.tamano_maximo_kb), pct: formatPct(storedir?.capacidad_pct),
              })}
            />
            <Tarjeta
              titulo={traducir("Objetos en caché")}
              valor={storedir?.entradas != null ? String(storedir.entradas) : '—'}
              Icon={IconEye}
              color="#4E9C5B"
              detalle={traducir("Tamaño medio: {v}", { v: formatKB(info?.objeto_medio_kb) })}
            />
          </div>

          <div className="card p-6">
            <h2 className="text-base font-semibold text-ink mb-4">{traducir("Detalle")}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-3 text-sm">
              <div className="flex justify-between border-b border-line-soft pb-2">
                <span className="text-ink-3">{traducir("Versión de Squid")}</span>
                <span className="font-medium font-mono">{info?.version ?? '—'}</span>
              </div>
              <div className="flex justify-between border-b border-line-soft pb-2">
                <span className="text-ink-3">{traducir("Tiempo activo")}</span>
                <span className="font-medium tabular">{formatUptime(info?.uptime_segundos)}</span>
              </div>
              <div className="flex justify-between border-b border-line-soft pb-2">
                <span className="text-ink-3">{traducir("Clientes accediendo a la caché")}</span>
                <span className="font-medium tabular">{info?.clientes_activos ?? '—'}</span>
              </div>
              <div className="flex justify-between border-b border-line-soft pb-2">
                <span className="text-ink-3">{traducir("Peticiones HTTP recibidas")}</span>
                <span className="font-medium tabular">{info?.peticiones_recibidas ?? '—'}</span>
              </div>
              <div className="flex justify-between border-b border-line-soft pb-2">
                <span className="text-ink-3">{traducir("Ratio de fallos")}</span>
                <span className="font-medium tabular">{info?.ratio_fallos != null ? info.ratio_fallos.toFixed(2) : '—'}</span>
              </div>
              <div className="flex justify-between border-b border-line-soft pb-2">
                <span className="text-ink-3">{traducir("Caché en memoria")}</span>
                <span className="font-medium tabular">{formatKB(info?.mem_size_kb)}</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
