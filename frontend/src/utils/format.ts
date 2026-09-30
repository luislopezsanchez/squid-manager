// Formateo de numeros compartido entre paginas -antes vivia duplicado
// dentro de Dashboard.tsx; se extrae aca para que ActividadRed.tsx (y lo que
// venga despues) no tenga su propia copia que pueda desincronizarse.

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export function formatRate(bytesPerSec: number): string {
  if (bytesPerSec === 0) return '0 B/s'
  return formatBytes(bytesPerSec) + '/s'
}

export function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toString()
}

export function formatMs(ms: number): string {
  if (ms >= 1000) return (ms / 1000).toFixed(1) + ' s'
  return Math.round(ms) + ' ms'
}

/** Fecha y hora cortas en la zona del navegador: "30/09 14:00". `conAnio` agrega el año. */
export function formatFechaHora(ts: number, conAnio = false): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    day: '2-digit', month: '2-digit', ...(conAnio ? { year: 'numeric' } : {}), hour: '2-digit', minute: '2-digit',
  })
}

export function formatFecha(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString(undefined, { day: '2-digit', month: '2-digit', year: 'numeric' })
}
