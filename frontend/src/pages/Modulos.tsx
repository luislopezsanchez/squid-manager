import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api, isSuperadmin } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import { refrescarModulos } from '../utils/modules'

interface Modulo { key: string; enabled: boolean; default: boolean; titulo: string; descripcion: string }

// Qué incluye cada módulo y qué pasa al apagarlo, en palabras del admin.
const DETALLE: Record<string, { incluye: string; alApagar: string }> = {
  analisis: {
    incluye: 'Actividad de red, Estado del caché, Latencia y errores, Tendencias y Panorama.',
    alApagar: 'Desaparecen del menú. Los datos se siguen calculando en segundo plano, así que al volver a encenderlo no falta historia.',
  },
  panel_central: {
    incluye: 'Panel central: estado de varios proxies (SquidManager o Squid básico) en un solo lugar, con alertas de nodo caído.',
    alApagar: 'Desaparece del menú y deja de consultar y avisar de los nodos. Este servidor puede seguir siendo monitorizado por otro: eso no depende de este interruptor.',
  },
  asistente: {
    incluye: 'Asistente de IA en el menú Ayuda.',
    alApagar: 'Desaparece del menú. Su configuración (proveedor y claves) se conserva.',
  },
}

export default function Modulos() {
  const [modulos, setModulos] = useState<Modulo[] | null>(null)
  const [error, setError] = useState(false)
  const [guardando, setGuardando] = useState<string | null>(null)
  const { showToast, ToastContainer } = useToast()
  const puedeEditar = isSuperadmin()

  const cargar = () => api.listModules().then(m => { setModulos(m); setError(false) }).catch(() => setError(true))
  useEffect(() => { cargar() }, [])

  const cambiar = async (m: Modulo) => {
    setGuardando(m.key)
    try {
      await api.setModule(m.key, !m.enabled)
      await refrescarModulos()
      await cargar()
      showToast(!m.enabled ? traducir("Módulo activado") : traducir("Módulo desactivado"))
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') } finally { setGuardando(null) }
  }

  return (
    <div className="p-6 md:p-7 max-w-4xl">
      <ToastContainer />
      <h1 className="page-title">{traducir("Módulos")}</h1>
      <p className="page-sub mb-6">{traducir("Activa solo lo que necesitas: lo que apagues desaparece del menú y deja de ocupar espacio.")}</p>
      {!puedeEditar && <div className="note note-info mb-4"><p className="note-text">{traducir("Solo un superadministrador puede activar o desactivar módulos.")}</p></div>}

      {error ? <ErrorState onRetry={cargar} /> : !modulos ? <LoadingState /> : (
        <div className="space-y-3">
          {modulos.map(m => (
            <div key={m.key} className="card p-5 flex items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-semibold text-ink">{traducir(m.titulo)}</h2>
                  <span className={`pill ${m.enabled ? 'pill-ok' : 'pill-mute'}`}>{m.enabled ? traducir('Activo') : traducir('Apagado')}</span>
                  <span className="text-[11px] text-ink-3">{m.default ? traducir("activo por defecto") : traducir("apagado por defecto")}</span>
                </div>
                <p className="text-[13px] text-ink-2 mt-1">{traducir(m.descripcion)}</p>
                {DETALLE[m.key] && (
                  <dl className="mt-3 text-[12.5px] text-ink-3 space-y-1">
                    <div><dt className="inline font-semibold text-ink-2">{traducir("Incluye")}: </dt><dd className="inline">{traducir(DETALLE[m.key].incluye)}</dd></div>
                    <div><dt className="inline font-semibold text-ink-2">{traducir("Si lo apagas")}: </dt><dd className="inline">{traducir(DETALLE[m.key].alApagar)}</dd></div>
                  </dl>
                )}
              </div>
              <button role="switch" aria-checked={m.enabled} aria-label={m.titulo} disabled={!puedeEditar || guardando === m.key}
                onClick={() => cambiar(m)}
                className={`relative flex-none w-12 h-7 rounded-full transition disabled:opacity-50 ${m.enabled ? 'bg-brand-600' : 'bg-line'}`}>
                <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-all ${m.enabled ? 'left-[22px]' : 'left-0.5'}`} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
