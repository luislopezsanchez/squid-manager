import { useEffect } from 'react'
import { IconClose } from './Icons'
import { traducir } from '../i18n'

/**
 * Overlay de modal reutilizable: mismo patrón visual que ya usaban a mano
 * ProxyUsers.tsx (PasswordModal, QuotaModal) y PanelCentral.tsx, ahora
 * compartido para no repetirlo en cada página nueva que pasa su
 * formulario a un modal (ACLs, Categorías, Grupos, Reglas de acceso...).
 * Cierra con click afuera, con Escape, o con el botón -las tres formas
 * esperadas de un modal, que un formulario suelto no necesitaba.
 */
export default function Modal({ title, onClose, children, maxWidth = 'max-w-md' }: {
  title: string
  onClose: () => void
  children: React.ReactNode
  maxWidth?: string
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className={`bg-white rounded-xl p-6 w-full ${maxWidth} max-h-[90vh] overflow-y-auto`}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-ink">{title}</h2>
          <button
            onClick={onClose}
            aria-label={traducir('Cerrar')}
            className="w-8 h-8 flex-none flex items-center justify-center rounded-lg text-ink-3 hover:bg-black/5 hover:text-ink-2 transition"
          >
            <IconClose className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
