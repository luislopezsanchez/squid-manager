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
