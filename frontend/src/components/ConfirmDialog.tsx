import { useEffect, useRef, useState } from 'react'
import { IconAlert, IconInfo } from './Icons'
import { traducir } from '../i18n'

/**
 * Confirmación propia de la plataforma, en lugar del `confirm()` del
 * navegador (que no se puede estilizar, rompe el diseño y no sigue el idioma
 * del panel).
 *
 * Uso, igual de corto que el confirm() nativo pero con `await`:
 *
 *   if (!(await confirmar('¿Eliminar esta ACL?'))) return
 *   if (!(await confirmar('Mensaje', { titulo: 'Sobrescribir', confirmar: 'Sobrescribir', tono: 'peligro' }))) return
 *
 * `<ConfirmHost />` se monta una sola vez (en Layout) y dibuja el diálogo.
 * `tono` se deduce del texto si no se indica: un mensaje que empieza por
 * «¿Eliminar» o habla de borrar/sobrescribir sale en rojo.
 */

export interface OpcionesConfirmar {
  titulo?: string
  /** Texto del botón de confirmar. */
  confirmar?: string
  cancelar?: string
  tono?: 'peligro' | 'normal'
}

interface Pendiente extends OpcionesConfirmar {
  mensaje: string
  resolver: (ok: boolean) => void
}

let abrirDialogo: ((p: Pendiente) => void) | null = null

const RE_PELIGRO = /^¿?\s*(eliminar|borrar|quitar|desactivar|deshabilitar|terminar|sobrescribir)|sobrescrib|no se puede deshacer|irreversible/i

export function confirmar(mensaje: string, opciones: OpcionesConfirmar = {}): Promise<boolean> {
  return new Promise(resolver => {
    if (!abrirDialogo) {
      // Sin host montado (no debería pasar): mejor el nativo que perder la pregunta.
      resolver(window.confirm(mensaje))
      return
    }
    abrirDialogo({ mensaje, resolver, ...opciones })
  })
}

export function ConfirmHost() {
  const [cola, setCola] = useState<Pendiente[]>([])
  const botonCancelar = useRef<HTMLButtonElement>(null)
  const actual = cola[0]

  useEffect(() => {
    abrirDialogo = p => setCola(c => [...c, p])
    return () => { abrirDialogo = null }
  }, [])

  const cerrar = (ok: boolean) => {
    actual?.resolver(ok)
    setCola(c => c.slice(1))
  }

  useEffect(() => {
    if (!actual) return
    botonCancelar.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') cerrar(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actual])

  if (!actual) return null
  const peligro = (actual.tono ?? (RE_PELIGRO.test(actual.mensaje) ? 'peligro' : 'normal')) === 'peligro'
  const Icono = peligro ? IconAlert : IconInfo
  const titulo = actual.titulo ?? (peligro ? traducir('Confirmar acción') : traducir('Confirmar'))
  const etiqueta = actual.confirmar ?? (peligro ? traducir('Sí, continuar') : traducir('Aceptar'))

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[70] p-4"
         onClick={() => cerrar(false)}>
      <div className="card w-full max-w-md p-6 shadow-2xl animate-slide-in"
           role="alertdialog" aria-modal="true" aria-label={titulo}
           onClick={e => e.stopPropagation()}>
        <div className="flex items-start gap-4">
          <span className={`stat-icon flex-none ${peligro ? 'stat-icon-danger' : ''}`}><Icono /></span>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-bold text-ink">{titulo}</h2>
            <p className="text-[14px] text-ink-2 leading-snug mt-1.5 whitespace-pre-line break-words">{actual.mensaje}</p>
          </div>
        </div>
        <div className="flex justify-end gap-2.5 mt-6">
          <button ref={botonCancelar} className="btn btn-outline" onClick={() => cerrar(false)}>
            {actual.cancelar ?? traducir('Cancelar')}
          </button>
          <button className={`btn ${peligro ? 'btn-danger' : 'btn-primary'}`} onClick={() => cerrar(true)}>
            {etiqueta}
          </button>
        </div>
      </div>
    </div>
  )
}
