// Página de ACLs: filtros por uso/estado, selección múltiple y acciones en bloque.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const acls = [
  { id: 1, name: 'redes', type: 'dstdomain', value: '.redes.com', enabled: true, source: 'inline', is_category: false, description: null },
  { id: 2, name: 'huerfana', type: 'src', value: '10.0.0.0/8', enabled: true, source: 'inline', is_category: false, description: null },
  { id: 3, name: 'apagada', type: 'src', value: '10.1.0.0/16', enabled: false, source: 'inline', is_category: false, description: null },
]

// El idioma se fija al importar el módulo de i18n: se fuerza español antes de cargar la página.
vi.hoisted(() => localStorage.setItem('idioma', 'es'))

const api = vi.hoisted(() => ({
  listAcls: vi.fn(),
  getAclUsage: vi.fn(),
  bulkAcls: vi.fn(),
}))
vi.mock('../api/client', () => ({ api, notificarCambioPendiente: vi.fn() }))
vi.mock('../components/ConfirmDialog', () => ({ confirmar: vi.fn(async () => true) }))
vi.mock('../components/RequiereAplicar', () => ({ default: () => null }))

import ACLs from '../pages/ACLs'

const montar = () => render(<MemoryRouter><ACLs /></MemoryRouter>)
const filas = () => screen.getAllByRole('row').slice(1)

beforeEach(() => {
  api.listAcls.mockResolvedValue(acls)
  api.getAclUsage.mockResolvedValue({ redes: ['Regla de acceso #1'] })
  api.bulkAcls.mockResolvedValue({ hechas: ['huerfana', 'apagada'], omitidas: [] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ACLs: filtros y acciones en bloque', () => {
  it('«Sin uso» deja sólo las ACLs que ninguna regla usa', async () => {
    montar()
    await screen.findByText('redes')
    expect(filas()).toHaveLength(3)
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'sinuso' } })
    await waitFor(() => expect(filas()).toHaveLength(2))
    expect(screen.queryByText('redes')).toBeNull()
    expect(screen.getByText('huerfana')).toBeTruthy()
  })

  it('«Inactivas» filtra por estado', async () => {
    montar()
    await screen.findByText('redes')
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'inactiva' } })
    await waitFor(() => expect(filas()).toHaveLength(1))
    expect(screen.getByText('apagada')).toBeTruthy()
  })

  it('marcar todas las del filtro y eliminar manda sólo esos ids', async () => {
    montar()
    await screen.findByText('redes')
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'sinuso' } })
    await waitFor(() => expect(filas()).toHaveLength(2))
    fireEvent.click(screen.getByLabelText('Seleccionar todas'))
    const barra = await screen.findByText(/2 seleccionadas/)
    expect(barra).toBeTruthy()
    fireEvent.click(within(barra.parentElement as HTMLElement).getByText('Eliminar'))
    await waitFor(() => expect(api.bulkAcls).toHaveBeenCalledTimes(1))
    expect(api.bulkAcls.mock.calls[0][0].sort()).toEqual([2, 3])
    expect(api.bulkAcls.mock.calls[0][1]).toBe('delete')
  })

  it('sin nada marcado no hay barra de acciones', async () => {
    montar()
    await screen.findByText('redes')
    expect(screen.queryByText(/seleccionadas/)).toBeNull()
  })
})
