import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, clearToken } from '../api/client'
import AuthShell from '../components/AuthShell'
import { IconSpinner, IconAlert } from '../components/Icons'

const MIN_LENGTH = 10

/**
 * Cambio de contraseña. Es también la pantalla obligatoria del primer acceso:
 * las cuentas nuevas se crean con una contraseña que ya conoce otra persona,
 * así que no vale como secreto hasta que su dueño la cambia.
 */
export default function ChangePassword() {
  const forced = localStorage.getItem('mustChangePassword') === '1'
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (next.length < MIN_LENGTH) {
      setError(`La contraseña nueva debe tener al menos ${MIN_LENGTH} caracteres.`)
      return
    }
    if (next !== repeat) {
      setError('Las dos contraseñas nuevas no coinciden.')
      return
    }
    if (next === current) {
      setError('La contraseña nueva debe ser distinta de la actual.')
      return
    }

    setLoading(true)
    try {
      await api.changePassword(current, next)
      // El cambio invalida el token actual: hay que volver a entrar.
      // window.location (no navigate): en el primer acceso App() monta un
      // router restringido sin ruta /login, asi que una navegacion SPA
      // rebota al *; hace falta una recarga dura para que App() reevalue
      // mustChangePassword desde localStorage.
      clearToken()
      window.location.href = '/login'
    } catch (err: any) {
      setError(err.message || 'No se pudo cambiar la contraseña')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      titulo={forced ? 'Elige tu contraseña' : 'Cambiar contraseña'}
      subtitulo={
        forced
          ? 'Es tu primer acceso. Define una contraseña que solo conozcas tú.'
          : 'Al cambiarla se cerrarán las sesiones abiertas en otros navegadores.'
      }
    >
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label className="field-label" htmlFor="actual">Contraseña actual</label>
          <input
            id="actual" type="password" className="input" value={current}
            onChange={e => setCurrent(e.target.value)}
            autoComplete="current-password" autoFocus required
          />
        </div>

        <div className="field">
          <label className="field-label" htmlFor="nueva">Contraseña nueva</label>
          <input
            id="nueva" type="password" className="input" value={next}
            onChange={e => setNext(e.target.value)}
            autoComplete="new-password" minLength={MIN_LENGTH} required
          />
          <span className="field-help">Mínimo {MIN_LENGTH} caracteres.</span>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="repetir">Repite la contraseña nueva</label>
          <input
            id="repetir" type="password" className="input" value={repeat}
            onChange={e => setRepeat(e.target.value)}
            autoComplete="new-password" required
          />
        </div>

        {error && (
          <div className="flex items-start gap-2.5 bg-danger-soft text-danger text-[13px] p-3 rounded-lg mb-4">
            <IconAlert className="w-4 h-4 flex-none mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <button type="submit" disabled={loading} className="btn btn-primary w-full py-2.5 text-[14.5px]">
          {loading ? (
            <>
              <IconSpinner className="w-5 h-5 animate-spin" />
              Guardando…
            </>
          ) : (
            'Cambiar contraseña'
          )}
        </button>

        {!forced && (
          <button
            type="button"
            onClick={() => navigate('/')}
            className="w-full py-2 mt-2 text-[13px] text-ink-3 hover:text-ink-2 transition"
          >
            Volver al panel
          </button>
        )}
      </form>
    </AuthShell>
  )
}
