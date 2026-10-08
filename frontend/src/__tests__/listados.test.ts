// Regresiones de esta etapa: los listados de usuarios deben pedir TODAS las páginas (antes sólo se veían 1000)
// y una exportación parcial debe avisarse.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { descargarArchivo } from '../utils/descarga'

afterEach(() => vi.unstubAllGlobals())

const respuesta = (cuerpo: unknown, cabeceras: Record<string, string> = {}) =>
  new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json', ...cabeceras } })

describe('listados de usuarios', () => {
  it('pide todas las páginas hasta que una viene incompleta (11 000 usuarios)', async () => {
    const pedidos: string[] = []
    const usuarios = (n: number, desde: number) => Array.from({ length: n }, (_, i) => ({ username: `u${desde + i}` }))
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      pedidos.push(url)
      const offset = Number(new URL(url, 'http://x').searchParams.get('offset'))
      return respuesta(usuarios(offset < 10000 ? 5000 : 1000, offset))
    }))
    localStorage.setItem('token', 't')
    const todos = await api.listLdapUsers()
    expect(todos).toHaveLength(11000)
    expect(pedidos).toHaveLength(3)
    expect(pedidos.map(u => new URL(u, 'http://x').searchParams.get('offset'))).toEqual(['0', '5000', '10000'])
  })

  it('con menos de una página hace una sola petición', async () => {
    const f = vi.fn(async () => respuesta([{ username: 'ana' }]))
    vi.stubGlobal('fetch', f)
    localStorage.setItem('token', 't')
    expect(await api.listUsers()).toHaveLength(1)
    expect(f).toHaveBeenCalledTimes(1)
  })
})

describe('descarga de exportaciones', () => {
  const descargar = async (cabeceras: Record<string, string>) => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('a,b\n1,2\n', { status: 200, headers: cabeceras })))
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    HTMLAnchorElement.prototype.click = vi.fn()
    return descargarArchivo('/api/logs/export', 'logs.csv')
  }

  it('avisa cuando el servidor marca el archivo como parcial', async () => {
    expect(await descargar({ 'X-Export-Parcial': 'true' })).toBe(true)
  })

  it('no avisa cuando está completo', async () => {
    expect(await descargar({})).toBe(false)
  })
})
