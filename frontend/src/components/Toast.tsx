import { useState, useCallback } from 'react'
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

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const showToast = useCallback(
    (msg: string, type: 'success' | 'error' | 'warning' | 'info' = 'success') => {
      const id = Date.now() + Math.random()
      setToasts(prev => [...prev, { id, msg, type }])
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, 5000)
    },
    [],
  )

  const ToastContainer = () => (
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
            <p className="text-[13.5px] text-ink-2 leading-snug pt-1">{t.msg}</p>
          </div>
        )
      })}
    </div>
  )

  return { showToast, ToastContainer }
}
