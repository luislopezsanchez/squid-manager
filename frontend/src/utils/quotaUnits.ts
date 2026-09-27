// Unidades y helpers compartidos por los formularios de cuota de
// navegación (por usuario en ProxyUsers.tsx, por grupo en Cuotas.tsx)
// -extraído de ProxyUsers.tsx para que ambos usen exactamente la misma
// conversión, sin dos copias que puedan desincronizarse.
import { traducir } from '../i18n'

export const TAMANO_UNITS = [
  { value: 1048576, label: traducir("MB") },
  { value: 1073741824, label: traducir("GB") },
]
export const VELOCIDAD_UNITS = [
  { value: 1024, label: traducir("KB/s") },
  { value: 1048576, label: traducir("MB/s") },
]
export const PERIODO_LABELS: Record<string, string> = {
  daily: traducir("Diario"), weekly: traducir("Semanal"), monthly: traducir("Mensual"),
}

// Elige la unidad más legible para un valor guardado en bytes (o
// bytes/s) -sin esto, reabrir una cuota guardada en MB la mostraba
// convertida a una fracción de GB casi ilegible (ej. "0,0048828125 GB"
// para lo que en realidad eran "5 MB"), porque el editor siempre asumía
// la unidad más grande de la lista en vez de la que se había usado.
export function detectarUnidad(valor: number, unidades: { value: number }[]): number {
  const ordenadas = [...unidades].sort((a, b) => b.value - a.value)
  for (const u of ordenadas) {
    if (valor >= u.value) return u.value
  }
  return ordenadas[ordenadas.length - 1]?.value ?? 1
}
