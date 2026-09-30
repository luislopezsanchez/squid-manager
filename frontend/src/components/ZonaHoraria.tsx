import { useEffect, useMemo, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { useToast } from './Toast'

interface Estado {
  zona: string | null; zona_sistema: string; zona_efectiva: string
  hora_actual: string; desfase: string; zonas: string[]
}

/** Zona horaria de la instalación: decide cuándo es «medianoche» para reiniciar cuotas,
 * cómo se agrupan los gráficos por día y a qué hora sale el reporte diario. */
export function ZonaHoraria() {
  const { showToast, ToastContainer } = useToast()
  const [estado, setEstado] = useState<Estado | null>(null)
  const [zona, setZona] = useState('')   // '' = la del sistema
  const [filtro, setFiltro] = useState('')
  const [guardando, setGuardando] = useState(false)

  const cargar = () => api.getTimezone().then((e: Estado) => { setEstado(e); setZona(e.zona || '') }).catch(() => {})
  useEffect(() => { cargar() }, [])

  const opciones = useMemo(() => {
    const f = filtro.trim().toLowerCase()
    const lista = estado ? estado.zonas.filter(z => !f || z.toLowerCase().includes(f)) : []
    return zona && !lista.includes(zona) ? [zona, ...lista] : lista
  }, [estado, filtro, zona])

  if (!estado) return null
  const cambio = (estado.zona || '') !== zona

  const guardar = async () => {
    setGuardando(true)
    try {
      const e = await api.setTimezone(zona || null)
      setEstado(e)
      showToast(traducir("Zona horaria guardada. Las cuotas y los gráficos por día ya la usan."), 'success')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="card p-5 mb-6">
      <ToastContainer />
      <h2 className="text-lg font-bold text-ink mb-1">{traducir("Zona horaria")}</h2>
      <p className="text-[13px] text-ink-3 mb-4">
        {traducir("Define cuándo empieza y termina el día para SquidManager: la medianoche en la que se restablecen las cuotas diarias (y el lunes o el día 1 en las semanales y mensuales), el corte de los gráficos por día y la hora del reporte diario. Elige la zona donde está tu oficina; por defecto se usa la del servidor.")}
      </p>
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-[220px]">
          <label htmlFor="tz-buscar" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Buscar zona")}</label>
          <input id="tz-buscar" value={filtro} onChange={e => setFiltro(e.target.value)} placeholder="America/Havana" className="input text-sm mb-2" />
          <select aria-label={traducir("Zona horaria")} value={zona} onChange={e => setZona(e.target.value)} className="input text-sm bg-white">
            <option value="">{traducir("La del servidor")} ({estado.zona_sistema})</option>
            {opciones.map(z => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
        <div className="text-sm">
          <p className="text-ink-3 text-xs">{traducir("Hora actual con la zona guardada")}</p>
          <p className="font-mono text-ink">{estado.hora_actual} <span className="text-ink-3">(UTC{estado.desfase})</span></p>
        </div>
        <button onClick={guardar} disabled={!cambio || guardando} className="btn btn-primary disabled:opacity-50">
          {guardando ? traducir('Guardando…') : traducir('Guardar zona horaria')}
        </button>
      </div>
      {cambio && (
        <p className="text-xs text-ink-3 mt-3">{traducir("Al cambiarla, las cuotas se vuelven a evaluar con la nueva medianoche: si un periodo ya terminó según la nueva hora, se restablecen en el siguiente ciclo (menos de un minuto).")}</p>
      )}
    </div>
  )
}
