import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api, isSuperadmin } from '../api/client'
import { useToast } from '../components/Toast'
import { IconBell, IconSpinner } from '../components/Icons'

// La página vive incluso para quien no es superadmin (puede consultar el
// estado, igual que cualquier otra pantalla de solo lectura), pero las
// acciones que pueden terminar reiniciando servicios quedan reservadas —
// ver la nota de diseño en backend/app/routes/update.py.

function formatearFecha(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function Actualizaciones() {
  const [estado, setEstado] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [comprobando, setComprobando] = useState(false)
  const [aprobando, setAprobando] = useState(false)
  const [fechaProgramada, setFechaProgramada] = useState('')
  const { showToast, ToastContainer } = useToast()
  const puedeEscribir = isSuperadmin()
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const cargar = () => api.getUpdateStatus().then(setEstado).catch(() => showToast(traducir("Error al cargar el estado de actualizaciones"), 'error'))

  useEffect(() => {
    cargar().finally(() => setLoading(false))
  }, [])

  // Mientras haya una actualización en curso, se sondea seguido para que la
  // pantalla se actualice sola sin que haya que recargar a mano.
  useEffect(() => {
    const enCurso = estado?.apply?.status === 'running' || estado?.apply?.status === 'verificando'
    if (enCurso && !pollRef.current) {
      pollRef.current = setInterval(cargar, 5000)
    } else if (!enCurso && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [estado?.apply?.status])

  const handleComprobar = async () => {
    setComprobando(true)
    try {
      const r = await api.checkUpdateNow()
      setEstado((prev: any) => ({ ...prev, ...r }))
      showToast(
        r.check.update_available
          ? traducir("Hay una actualización disponible")
          : traducir("Ya tenés la última versión"),
        'success',
      )
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setComprobando(false)
    }
  }

  const handleAprobar = async (paraAhora: boolean) => {
    setAprobando(true)
    try {
      const iso = paraAhora ? null : (fechaProgramada ? new Date(fechaProgramada).toISOString() : null)
      if (!paraAhora && !iso) {
        showToast(traducir("Elegí una fecha y hora para programarla"), 'warning')
        setAprobando(false)
        return
      }
      const r = await api.approveUpdate(iso)
      setEstado((prev: any) => ({ ...prev, ...r }))
      showToast(
        paraAhora
          ? traducir("Actualización aprobada — aplicándose en los próximos segundos")
          : traducir("Actualización programada"),
        'success',
      )
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setAprobando(false)
    }
  }

  const handleCancelar = async () => {
    try {
      const r = await api.cancelUpdate()
      setEstado((prev: any) => ({ ...prev, ...r }))
      showToast(traducir("Actualización programada cancelada"), 'success')
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    }
  }

  const handleToggleCheck = async (activar: boolean) => {
    try {
      await api.updateCheckConfig(activar)
      setEstado((prev: any) => ({ ...prev, check_enabled: activar }))
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    }
  }

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>
  if (!estado) return <div className="p-8 text-center text-ink-3">{traducir("No se pudo cargar el estado")}</div>

  const { check, request, apply } = estado
  const hayPendiente = request?.approved
  const enCurso = apply?.status === 'running' || apply?.status === 'verificando'

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Actualizaciones")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Comprueba si hay una versión nueva de SquidManager publicada en GitHub y permite aprobarla — para aplicar de inmediato o programada — sin salir del panel.")}
      </p>

      {!estado.es_nativo && (
        <div className="card p-4 mb-6 note-warn">
          <p className="text-sm text-ink-2">
            {traducir("Esta instalación corre en modo Docker: la comprobación y aplicación automática de actualizaciones solo está disponible en instalación nativa por ahora. Usa upgrade-docker.sh manualmente.")}
          </p>
        </div>
      )}

      {/* Estado actual */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-medium text-ink">{traducir("Versión")}</h2>
          {puedeEscribir && (
            <label className="flex items-center gap-2 cursor-pointer text-sm text-ink-2">
              <input
                type="checkbox"
                checked={estado.check_enabled}
                onChange={e => handleToggleCheck(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              {traducir("Comprobar automáticamente")}
            </label>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="field-label mb-1">{traducir("Instalada")}</p>
            <p className="font-mono text-ink">v{estado.version_actual} · {check.local_commit || '—'}</p>
          </div>
          <div>
            <p className="field-label mb-1">{traducir("Última en GitHub")}</p>
            <p className="font-mono text-ink">{check.remote_commit || '—'}</p>
          </div>
        </div>

        <p className="text-xs text-ink-3 mt-3">
          {traducir("Última comprobación")}: {formatearFecha(check.last_checked_at)}
          {check.last_check_error && (
            <span className="text-danger"> — {traducir("error")}: {check.last_check_error}</span>
          )}
        </p>

        {estado.es_nativo && (
          <button onClick={handleComprobar} disabled={comprobando} className="btn btn-ghost mt-4 disabled:opacity-50">
            {comprobando ? traducir('Comprobando…') : traducir('Comprobar ahora')}
          </button>
        )}
      </div>

      {/* Actualización disponible */}
      {check.update_available && estado.es_nativo && (
        <div className="card p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <IconBell className="w-5 h-5 text-brand-600" />
            <h2 className="font-medium text-ink">{traducir("Hay una actualización disponible")}</h2>
          </div>

          {check.commits?.length > 0 && (
            <div className="mb-4">
              <p className="field-label mb-2">{traducir("Novedades")} ({check.commits.length})</p>
              <ul className="space-y-1 max-h-56 overflow-y-auto text-sm border border-line rounded-lg p-3 bg-brand-50">
                {check.commits.map((c: any, i: number) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-mono text-ink-3 flex-none">{c.sha}</span>
                    <span className="text-ink-2">{c.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!puedeEscribir ? (
            <p className="text-sm text-ink-3">{traducir("Solo un superadministrador puede aprobar una actualización.")}</p>
          ) : enCurso ? (
            <p className="text-sm text-ink-2 flex items-center gap-2">
              <IconSpinner className="w-4 h-4 animate-spin" />
              {traducir("Actualización en curso… el panel puede reiniciarse en cualquier momento.")}
            </p>
          ) : hayPendiente ? (
            <div className="flex items-center gap-3 flex-wrap">
              <p className="text-sm text-ink-2">
                {traducir("Programada para")}: <strong>{formatearFecha(request.scheduled_at)}</strong>
                {' '}({traducir("aprobada por")} {request.requested_by})
              </p>
              <button onClick={handleCancelar} className="btn btn-ghost text-sm">{traducir("Cancelar")}</button>
            </div>
          ) : (
            <div className="flex items-center gap-3 flex-wrap">
              <button onClick={() => handleAprobar(true)} disabled={aprobando} className="btn btn-primary disabled:opacity-50">
                {aprobando ? traducir('Aprobando…') : traducir('Actualizar ahora')}
              </button>
              <span className="text-sm text-ink-3">{traducir("o")}</span>
              <input
                type="datetime-local"
                value={fechaProgramada}
                onChange={e => setFechaProgramada(e.target.value)}
                className="input w-auto"
              />
              <button onClick={() => handleAprobar(false)} disabled={aprobando} className="btn btn-ghost disabled:opacity-50">
                {traducir('Programar')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Resultado de la última actualización aplicada */}
      {apply?.status === 'ok' || apply?.status === 'error' ? (
        <div className="card p-6">
          <h2 className="font-medium text-ink mb-3">{traducir("Última actualización aplicada")}</h2>
          <p className="text-sm mb-2">
            <span className={apply.status === 'ok' ? 'text-ok font-medium' : 'text-danger font-medium'}>
              {apply.status === 'ok' ? `✓ ${traducir('Correcta')}` : `✗ ${traducir('Falló')}`}
            </span>
            {' '}— {formatearFecha(apply.finished_at)}
            {apply.commit && <> · <span className="font-mono text-ink-3">{apply.commit}</span></>}
          </p>
          {apply.log_tail && (
            <pre className="text-xs bg-black/[.06] rounded-md p-3 overflow-x-auto max-h-56 whitespace-pre-wrap">
              {apply.log_tail}
            </pre>
          )}
        </div>
      ) : null}
    </div>
  )
}
