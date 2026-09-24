import { IconSpinner, IconAlert } from './Icons'
import { traducir } from '../i18n'

/**
 * Estado de carga a pantalla completa, animado.
 *
 * Reemplaza el texto estático "Cargando..." que tenían todas las páginas:
 * bajo carga real (muchos admins, muchas pestañas, el backend ocupado) una
 * carga que tarda un par de segundos con solo texto se siente rota o
 * colgada; con el spinner se ve que el panel sigue vivo y está trabajando.
 */
export function LoadingState({ text }: { text?: string }) {
  return (
    <div className="p-8 flex flex-col items-center justify-center gap-3 text-ink-3">
      <span style={{ color: 'var(--brand-600)' }}><IconSpinner className="w-7 h-7 animate-spin" /></span>
      <span className="text-sm">{text ?? traducir('Cargando...')}</span>
    </div>
  )
}

/**
 * Estado de error con reintento manual.
 *
 * Antes, si la carga inicial de una página fallaba (red, backend ocupado,
 * límite de peticiones bajo carga real), la mayoría de las páginas se
 * quedaba en blanco o a mitad de cargar sin ninguna explicación -el único
 * indicio era la consola del navegador. `onRetry` vuelve a llamar a la
 * misma función de carga; no hace falta recargar la página entera.
 */
export function ErrorState({ text, onRetry }: { text?: string; onRetry: () => void }) {
  return (
    <div className="p-8 flex flex-col items-center justify-center gap-3 text-center">
      <span style={{ color: 'var(--warn)' }}><IconAlert className="w-7 h-7" /></span>
      <p className="text-sm text-ink-3 max-w-sm">
        {text ?? traducir('No se pudieron cargar los datos. Revisá la conexión o volvé a intentar.')}
      </p>
      <button
        onClick={onRetry}
        className="px-4 py-2 rounded-lg text-sm font-bold text-white transition"
        style={{ background: 'var(--brand-700)' }}
      >
        {traducir('Reintentar')}
      </button>
    </div>
  )
}
