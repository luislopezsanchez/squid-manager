import { useEffect, useState } from 'react'
import { api } from '../api/client'

/**
 * Nombres de usuario (locales + LDAP) que coinciden con lo que se está escribiendo, buscados en el servidor.
 *
 * Los selectores de Grupos, Cuotas y Delay pools descargaban TODOS los usuarios para autocompletar; con miles eso era lento.
 * Ahora se pide un puñado (máx. 50) tras una pausa de 250 ms al escribir.
 */
export function useSugerenciasUsuarios(texto: string, activo = true): { nombres: string[]; hayMas: boolean } {
  const [res, setRes] = useState<{ nombres: string[]; hayMas: boolean }>({ nombres: [], hayMas: false })
  useEffect(() => {
    if (!activo) return
    let vigente = true
    const t = setTimeout(() => {
      api.buscarUsuarios(texto.trim())
        .then(r => { if (vigente) setRes({ nombres: r.usuarios.map(u => u.username), hayMas: r.hay_mas }) })
        .catch(() => { if (vigente) setRes({ nombres: [], hayMas: false }) })
    }, 250)
    return () => { vigente = false; clearTimeout(t) }
  }, [texto, activo])
  return res
}

/** <datalist> de autocompletado cuyo contenido se busca en el servidor según `texto`. */
export function DatalistUsuarios({ id, texto }: { id: string; texto: string }) {
  const { nombres } = useSugerenciasUsuarios(texto)
  return (
    <datalist id={id}>
      {nombres.map(u => <option key={u} value={u} />)}
    </datalist>
  )
}
