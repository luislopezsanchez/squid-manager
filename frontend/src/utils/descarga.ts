import { useState, useCallback } from 'react'
import { getToken } from '../api/client'
import { traducir } from '../i18n'
import { formatBytes } from './format'

/**
 * Descarga de archivos con la sesión del panel, con feedback real.
 *
 * Antes cada exportación hacía `fetch(...).then(r => r.blob())` a ciegas:
 * un mes histórico grande tarda en generarse, no había ningún indicio de que
 * algo pasara (el botón parecía muerto) y una respuesta de error (404/401/
 * 500) se guardaba igual como si fuera el archivo. Acá se lee el cuerpo en
 * streaming para mostrar cuántos bytes van llegando, se valida `r.ok` y se
 * muestra el motivo del fallo.
 */
export async function descargarArchivo(
  url: string,
  nombre: string,
  onProgreso?: (bytesRecibidos: number) => void,
): Promise<boolean> {
  const r = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!r.ok) {
    let motivo = `HTTP ${r.status}`
    try {
      const j = await r.json()
      if (j?.detail) motivo = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* cuerpo no JSON */ }
    throw new Error(motivo)
  }
  const trozos: BlobPart[] = []
  let recibidos = 0
  if (r.body) {
    const lector = r.body.getReader()
    for (;;) {
      const { done, value } = await lector.read()
      if (done) break
      if (value) {
        trozos.push(value)
        recibidos += value.length
        onProgreso?.(recibidos)
      }
    }
  } else {
    trozos.push(await r.blob())
  }
  const u = URL.createObjectURL(new Blob(trozos))
  const a = document.createElement('a')
  a.href = u
  a.download = nombre
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(u), 10_000)
  // El servidor marca las exportaciones que no incluyen todo lo pedido (p. ej. más de 50 000 registros).
  return r.headers.get('X-Export-Parcial') === 'true'
}

/** Estado de una descarga en curso, para deshabilitar el botón y mostrar el avance. */
export function useDescarga(showToast: (msg: string, tipo?: 'success' | 'error' | 'warning' | 'info') => void) {
  const [descargando, setDescargando] = useState(false)
  const [bytes, setBytes] = useState(0)

  const descargar = useCallback(async (url: string, nombre: string, textoOk?: string) => {
    if (descargando) return
    setDescargando(true)
    setBytes(0)
    showToast(traducir('Preparando la descarga... los archivos grandes tardan unos segundos.'), 'info')
    try {
      const parcial = await descargarArchivo(url, nombre, setBytes)
      if (parcial) {
        showToast(traducir('El archivo es PARCIAL: hay más registros de los que caben en una exportación (máx. 50 000). Acota con filtros para obtener el resto.'), 'warning')
      } else {
        showToast(textoOk ?? traducir('Descarga lista'), 'success')
      }
    } catch (e: any) {
      showToast(`${traducir('Error en la descarga')}: ${e.message}`, 'error')
    } finally {
      setDescargando(false)
    }
  }, [descargando, showToast])

  /** Texto para el botón mientras descarga: «Descargando… 3,2 MB». */
  const etiqueta = descargando
    ? `${traducir('Descargando...')} ${bytes ? formatBytes(bytes) : ''}`.trim()
    : ''

  return { descargando, descargar, etiqueta }
}
