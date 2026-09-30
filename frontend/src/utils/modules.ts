import { useEffect, useState } from 'react'
import { api } from '../api/client'

/** Módulos opcionales del panel (ver backend/app/services/modules_service.py).
 * Un solo estado compartido para menú y rutas: se pide una vez al entrar y se
 * refresca cuando el superadmin enciende o apaga alguno. */
export type ModuloClave = 'analisis' | 'panel_central' | 'asistente'
export type EstadoModulos = Record<ModuloClave, boolean>

// Valores por defecto mientras llega la respuesta: los mismos que el servidor
// (Análisis y Asistente sí, Panel central no), para que el menú no parpadee.
const POR_DEFECTO: EstadoModulos = { analisis: true, panel_central: false, asistente: true }

let estado: EstadoModulos = POR_DEFECTO
let cargado = false
const oyentes = new Set<(e: EstadoModulos) => void>()

function publicar(nuevo: EstadoModulos) {
  estado = nuevo
  cargado = true
  oyentes.forEach(f => f(nuevo))
}

export async function refrescarModulos(): Promise<void> {
  try {
    const lista: { key: ModuloClave; enabled: boolean }[] = await api.listModules()
    publicar({ ...POR_DEFECTO, ...Object.fromEntries(lista.map(m => [m.key, m.enabled])) } as EstadoModulos)
  } catch {
    /* sin red o sin sesión: se queda lo último conocido */
  }
}

export function useModulos(): { modulos: EstadoModulos; cargado: boolean } {
  const [m, setM] = useState<EstadoModulos>(estado)
  useEffect(() => {
    oyentes.add(setM)
    if (!cargado) refrescarModulos()
    return () => { oyentes.delete(setM) }
  }, [])
  return { modulos: m, cargado }
}
