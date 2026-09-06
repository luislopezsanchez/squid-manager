import { traducir } from '../i18n'

/**
 * Aviso reutilizable para toda pantalla cuyo "Guardar" solo escribe en la
 * BD: el cambio no llega a Squid hasta pulsar «Aplicar cambios» en la barra
 * superior. Antes la única señal era ese botón poniéndose rojo, y tarda
 * hasta 5s en reflejar un guardado reciente (ver `notificarCambioPendiente`
 * en api/client.ts) — quien guardaba y miraba de inmediato no veía nada
 * distinto y no sabía si hacía falta un paso más.
 */
export default function RequiereAplicar() {
  return (
    <p className="text-xs text-ink-3 flex items-center gap-1.5">
      <span className="text-warn font-bold" aria-hidden="true">*</span>
      {traducir("Guardar aquí no lo aplica todavía: hace falta pulsar «Aplicar cambios» arriba para que Squid lo use.")}
    </p>
  )
}
