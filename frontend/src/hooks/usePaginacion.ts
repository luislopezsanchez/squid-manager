import { useEffect, useState } from 'react'

/**
 * Mantiene `pagina` siempre dentro de rango cuando `totalFilas` cambia
 * (se borra/crea algo, o se filtra) -mismo bug ya encontrado y corregido
 * una vez en Usuarios (ver el historial de ProxyUsers.tsx): guardar
 * `pagina` cruda y un `paginaSegura` derivado por separado podía
 * divergir, porque los botones Anterior/Siguiente tocaban la cruda. Acá
 * `pagina` en sí misma nunca queda inválida.
 *
 * El reset a 0 cuando cambia una búsqueda/filtro sigue siendo cosa de
 * cada página (las dependencias son distintas en cada una): un
 * `useEffect(() => setPagina(0), [busqueda, ...filtros])` de siempre.
 */
export function usePaginacion(totalFilas: number, porPagina: number) {
  const [pagina, setPagina] = useState(0)
  const totalPaginas = Math.max(1, Math.ceil(totalFilas / porPagina))

  useEffect(() => {
    setPagina(p => Math.min(p, totalPaginas - 1))
  }, [totalPaginas])

  return { pagina, setPagina, totalPaginas }
}
