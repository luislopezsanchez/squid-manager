import { useState, useCallback, useRef } from 'react'
import { IconCheck, IconAlert, IconClose, IconBolt } from './Icons'

interface Toast {
  id: number
  msg: string
  type: 'success' | 'error' | 'warning' | 'info'
}

/** Color e icono de cada tipo de aviso. */
const ESTILOS = {
  success: { clase: 'note-ok', icono: IconCheck, tono: 'stat-icon-ok' },
  error: { clase: 'note-danger', icono: IconClose, tono: 'stat-icon-danger' },
  warning: { clase: 'note-warn', icono: IconAlert, tono: 'stat-icon-warn' },
  info: { clase: 'note-info', icono: IconBolt, tono: '' },
} as const

function Avisos({ toasts, cerrar }: { toasts: Toast[]; cerrar: (id: number) => void }) {
  return (
    <div className="fixed top-6 right-6 z-50 flex flex-col gap-2.5">
      {toasts.map(t => {
        const { clase, icono: Icono, tono } = ESTILOS[t.type]
        return (
          <div
            key={t.id}
            role="status"
            className={`card ${clase} flex items-start gap-3 p-4 shadow-lg animate-slide-in
                        min-w-[300px] max-w-md`}
          >
            <span className={`stat-icon flex-none ${tono}`}>
              <Icono />
            </span>
            <p className="text-[13.5px] text-ink-2 leading-snug pt-1 flex-1">{t.msg}</p>
            <button onClick={() => cerrar(t.id)} aria-label="Cerrar" className="flex-none text-ink-3 hover:text-ink pt-1">
              <IconClose className="w-3.5 h-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const cerrar = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const showToast = useCallback(
    (msg: string, type: 'success' | 'error' | 'warning' | 'info' = 'success') => {
      const id = Date.now() + Math.random()
      setToasts(prev => [...prev, { id, msg, type }])
      // Error y warning se quedan hasta que el usuario los cierra a proposito
      // -un fallo real (ej. SMTP mal autenticado) que desaparece solo a los
      // 5s da la falsa impresion de que "no paso nada", reportado en vivo
      // por el usuario probando el envio de correo. Exito/info si se
      // autodescartan, ahi no hay nada que el usuario deba leer con calma.
      if (type === 'success' || type === 'info') {
        setTimeout(() => cerrar(id), 5000)
      }
    },
    [cerrar],
  )

  // `ToastContainer` tiene que ser el MISMO componente en cada render. Antes se
  // definía dentro del hook, así que cada vez que la página se volvía a dibujar
  // (por ejemplo, al escribir en un formulario) React lo veía como un componente
  // nuevo, lo desmontaba y lo montaba de nuevo: los avisos ya mostrados
  // reaparecían con su animación de entrada. Ahora el componente es estable y
  // lee la lista actual desde una referencia.
  const actual = useRef({ toasts, cerrar })
  actual.current = { toasts, cerrar }
  const ToastContainer = useRef(() => <Avisos toasts={actual.current.toasts} cerrar={actual.current.cerrar} />).current

  return { showToast, ToastContainer }
}
