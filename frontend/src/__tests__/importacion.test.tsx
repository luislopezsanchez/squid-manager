// Importación masiva de usuarios: revisar -> importar en segundo plano con barra de progreso.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.hoisted(() => localStorage.setItem('idioma', 'es'))

const api = vi.hoisted(() => ({ importUsers: vi.fn(), importUsersEstado: vi.fn(), importTemplateUrl: vi.fn() }))
vi.mock('../api/client', () => ({ api, getToken: () => 't' }))

import { ImportarUsuariosModal } from '../components/UsuariosMasivo'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks() })

const informe = { simulacion: true, total_filas: 400, a_crear: 400, a_actualizar: 0, creados: 0, actualizados: 0,
  omitidos: [], errores: [], credenciales: [], segundos_estimados: 42 }

describe('importar usuarios', () => {
  it('avisa del tiempo, muestra el progreso y entrega el informe al terminar', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    api.importUsers
      .mockResolvedValueOnce(informe)                                   // revisar (simulación)
      .mockResolvedValueOnce({ ...informe, simulacion: false, tarea: 'abc' }) // confirmar -> segundo plano
    api.importUsersEstado
      .mockResolvedValueOnce({ estado: 'en_curso', fase: 'calculando', hechos: 100, total: 400, segundos: 10 })
      .mockResolvedValueOnce({ estado: 'terminada', fase: 'listo', hechos: 400, total: 400, segundos: 43,
        informe: { ...informe, simulacion: false, creados: 400, credenciales: [{ usuario: 'a', password: 'p' }] } })
    const onImportado = vi.fn()
    const onClose = vi.fn()
    const { container } = render(<ImportarUsuariosModal onClose={onClose} onImportado={onImportado} />)

    const input = container.querySelector('input[type=file]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['usuario\na'], 'u.csv', { type: 'text/csv' })] } })
    fireEvent.click(screen.getByText('Revisar archivo'))
    expect(await screen.findByText(/tardará unos 1 minutos|tardará unos/)).toBeTruthy()  // la estimación se muestra antes de confirmar

    fireEvent.click(screen.getByText(/Importar 400 usuarios/))
    await act(async () => { await vi.advanceTimersByTimeAsync(1600) })
    expect(await screen.findByText('Calculando contraseñas…')).toBeTruthy()
    expect(screen.getByText(/100 \/ 400/)).toBeTruthy()
    expect(onImportado).not.toHaveBeenCalled()

    await act(async () => { await vi.advanceTimersByTimeAsync(1600) })
    await waitFor(() => expect(onImportado).toHaveBeenCalledTimes(1))
    expect(onImportado.mock.calls[0][0].credenciales).toHaveLength(1)
    expect(onClose).toHaveBeenCalled()
  })

  it('si la tarea falla muestra el motivo y no cierra', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    api.importUsers.mockResolvedValueOnce(informe).mockResolvedValueOnce({ ...informe, tarea: 'x' })
    api.importUsersEstado.mockResolvedValueOnce({ estado: 'error', error: 'se cayó la base', hechos: 0, total: 400, fase: 'calculando', segundos: 1 })
    const onClose = vi.fn()
    const { container } = render(<ImportarUsuariosModal onClose={onClose} onImportado={vi.fn()} />)
    fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, { target: { files: [new File(['x'], 'u.csv')] } })
    fireEvent.click(screen.getByText('Revisar archivo'))
    fireEvent.click(await screen.findByText(/Importar 400 usuarios/))
    await act(async () => { await vi.advanceTimersByTimeAsync(1600) })
    expect(await screen.findByText('se cayó la base')).toBeTruthy()
    expect(onClose).not.toHaveBeenCalled()
  })
})
