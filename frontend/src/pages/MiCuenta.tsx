import { traducir } from '../i18n'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, clearToken } from '../api/client'
import { GraficoBarras, MARCA, ESTADO } from '../components/charts'
import { formatBytes, formatNumber, formatFecha, formatFechaHora } from '../utils/format'
import { PERIODO_LABELS } from '../utils/quotaUnits'
import { IconSpinner, IconAlert } from '../components/Icons'

type Cuenta = { username: string; display_name: string | null; email: string | null; expires_at: string | null }
type Punto = { timestamp: number; bytes: number; requests: number; bloqueadas: number }
type Resumen = {
  ventana: '7d' | '30d'
  puntos: Punto[]
  totales: { bytes: number; requests: number; bloqueadas: number; dias_activos: number }
  cuota: null | { periodo: string; limite_bytes: number; usado_bytes: number; accion: string; agotada: boolean; proximo_reinicio: number | null }
  grupos: string[]
}

/**
 * Dashboard de un usuario local del proxy: es lo primero que ve al entrar. Muestra su propia
 * navegación (consumo, peticiones, bloqueos, cuota) y deja cambiar la contraseña cuando quiera.
 * Solo recibe datos suyos: el servidor los filtra por el usuario del token.
 */
export default function MiCuenta() {
  const navigate = useNavigate()
  const [cuenta, setCuenta] = useState<Cuenta | null>(null)
  const [ventana, setVentana] = useState<'7d' | '30d'>('7d')
  const [datos, setDatos] = useState<Resumen | null>(null)
  const [error, setError] = useState('')

  useEffect(() => { api.selfMe().then(setCuenta).catch(() => {}) }, [])
  useEffect(() => {
    setDatos(null)
    setError('')
    api.selfDashboard(ventana).then(setDatos).catch((e: any) => setError(e.message || 'No se pudo cargar tu actividad'))
  }, [ventana])

  const salir = () => {
    clearToken()
    window.location.href = '/login'
  }

  const cuota = datos?.cuota
  const pct = cuota && cuota.limite_bytes > 0 ? Math.min(100, (cuota.usado_bytes / cuota.limite_bytes) * 100) : 0
  const colorCuota = !cuota ? MARCA : cuota.agotada ? ESTADO.error : pct >= 80 ? ESTADO.aviso : ESTADO.ok
  const sinActividad = datos && datos.totales.requests === 0

  return (
    <div className="min-h-screen">
      <header style={{ background: 'linear-gradient(90deg, #0A2C48, #12507C)' }} className="text-white">
        <div className="max-w-[980px] mx-auto px-4 py-3 flex items-center gap-3 flex-wrap">
          <img src="/brand/logo-256.png" alt="" width={34} height={32} className="h-8 w-auto" />
          <div className="mr-auto leading-tight">
            <div className="font-bold text-[15px]">{cuenta?.display_name || cuenta?.username || ' '}</div>
            <div className="text-[12px] text-white/70">
              {cuenta?.display_name ? cuenta.username : traducir('Mi cuenta')}
            </div>
          </div>
          <button className="btn btn-ghost !text-white !border-white/30 hover:!bg-white/10" onClick={() => navigate('/cambiar-contrasena')}>
            {traducir('Cambiar contraseña')}
          </button>
          <button className="btn btn-ghost !text-white !border-white/30 hover:!bg-white/10" onClick={salir}>
            {traducir('Cerrar sesión')}
          </button>
        </div>
      </header>

      <main className="max-w-[980px] mx-auto px-4 py-6 flex flex-col gap-5">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="page-title mr-auto">{traducir('Mi navegación')}</h1>
          <div className="inline-flex rounded-lg border border-line overflow-hidden" role="group" aria-label={traducir('Periodo')}>
            {(['7d', '30d'] as const).map(v => (
              <button key={v} onClick={() => setVentana(v)} aria-pressed={ventana === v}
                className={`px-3.5 py-1.5 text-[13px] font-semibold transition ${ventana === v ? 'bg-brand-600 text-white' : 'bg-surface text-ink-2 hover:bg-brand-50'}`}>
                {v === '7d' ? traducir('Última semana') : traducir('Último mes')}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="flex items-start gap-2.5 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">
            <IconAlert className="w-4 h-4 flex-none mt-0.5" /><span>{error}</span>
          </div>
        )}

        {!datos && !error && (
          <div className="grid place-items-center py-16 text-ink-3"><IconSpinner className="w-6 h-6 animate-spin" /></div>
        )}

        {datos && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: traducir('Datos descargados'), valor: formatBytes(datos.totales.bytes) },
                { label: traducir('Peticiones'), valor: formatNumber(datos.totales.requests) },
                { label: traducir('Días con actividad'), valor: `${datos.totales.dias_activos}`, nota: `/ ${datos.puntos.length}` },
                { label: traducir('Bloqueadas'), valor: formatNumber(datos.totales.bloqueadas) },
              ].map(k => (
                <div key={k.label} className="card card-body">
                  <div className="stat-label mb-2">{k.label}</div>
                  <div className="stat-value">{k.valor}{k.nota && <small> {k.nota}</small>}</div>
                </div>
              ))}
            </div>

            <div className="card">
              <div className="card-head"><h2 className="card-title">{traducir('Consumo por día')}</h2></div>
              <div className="card-body">
                {sinActividad ? (
                  <p className="text-[13.5px] text-ink-3 py-8 text-center">{traducir('Todavía no hay actividad registrada en este periodo.')}</p>
                ) : (
                  <GraficoBarras
                    datos={datos.puntos as any}
                    series={[{ key: 'bytes', label: traducir('Datos descargados'), color: MARCA, formato: formatBytes }]}
                    granularidad="dia" formatoEje={formatBytes}
                  />
                )}
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-5">
              <div className="card">
                <div className="card-head"><h2 className="card-title">{traducir('Mi cuota de navegación')}</h2></div>
                <div className="card-body">
                  {cuota ? (
                    <>
                      <div className="flex items-baseline justify-between mb-2">
                        <span className="stat-value">{formatBytes(cuota.usado_bytes)}<small> / {formatBytes(cuota.limite_bytes)}</small></span>
                        <span className="text-[13px] font-semibold" style={{ color: colorCuota }}>{Math.round(pct)}%</span>
                      </div>
                      <div className="h-2.5 rounded-full bg-line-soft overflow-hidden" role="progressbar"
                        aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: colorCuota }} />
                      </div>
                      <p className="text-[12.5px] text-ink-3 mt-3">
                        {PERIODO_LABELS[cuota.periodo] ?? cuota.periodo}
                        {cuota.proximo_reinicio ? ` · ${traducir('se restablece el')} ${formatFechaHora(cuota.proximo_reinicio)}` : ''}
                      </p>
                      {cuota.agotada && (
                        <p className="text-[13px] font-semibold mt-2" style={{ color: ESTADO.error }}>
                          {cuota.accion === 'cut' ? traducir('Agotaste tu cuota: la navegación está cortada hasta el próximo reinicio.') : traducir('Agotaste tu cuota: tu velocidad está limitada hasta el próximo reinicio.')}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="text-[13.5px] text-ink-3">{traducir('No tienes una cuota de navegación asignada.')}</p>
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-head"><h2 className="card-title">{traducir('Mi cuenta')}</h2></div>
                <div className="card-body text-[13.5px] text-ink-2 flex flex-col gap-1.5">
                  <div><span className="text-ink-3">{traducir('Usuario')}:</span> <span className="font-semibold text-ink">{cuenta?.username}</span></div>
                  {cuenta?.email && <div><span className="text-ink-3">{traducir('Correo')}:</span> {cuenta.email}</div>}
                  {cuenta?.expires_at && (
                    <div>
                      <span className="text-ink-3">{traducir('Caducidad')}:</span>{' '}
                      {formatFecha(new Date(cuenta.expires_at + 'Z').getTime() / 1000)}
                    </div>
                  )}
                  <div>
                    <span className="text-ink-3">{traducir('Grupos')}:</span>{' '}
                    {datos.grupos.length ? datos.grupos.join(', ') : traducir('Ninguno')}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
