import { traducir } from '../i18n'
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, clearToken } from '../api/client'
import AuthShell from '../components/AuthShell'
import { IconSpinner, IconAlert } from '../components/Icons'

const MIN_LENGTH = 10

/**
 * Cambio de contraseña de un usuario local del proxy, al que llega desde su dashboard
 * («Mi cuenta») cuando quiere, no al entrar. Al cambiarla se cierran sus sesiones (el
 * token lleva una huella de la contraseña), así que se vuelve a /login.
 */
export default function MiCuentaContrasena() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const navigate = useNavigate()
  const salir = () => {
    clearToken()
    window.location.href = '/login'
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (next.length < MIN_LENGTH) {
      setError(traducir('La contraseña nueva debe tener al menos {n} caracteres.', { n: MIN_LENGTH }))
      return
    }
    if (next !== repeat) {
      setError(traducir('Las dos contraseñas nuevas no coinciden.'))
      return
    }
    if (next === current) {
      setError(traducir('La contraseña nueva debe ser distinta de la actual.'))
      return
    }
    setLoading(true)
    try {
      await api.selfChangePassword(current, next)
      salir()
    } catch (err: any) {
      setError(err.message || 'No se pudo cambiar la contraseña')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      titulo={traducir('Cambiar contraseña')}
      subtitulo={traducir('Al cambiarla se cerrarán las sesiones abiertas y tendrás que entrar de nuevo.')}
    >

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label className="field-label" htmlFor="actual">{traducir("Contraseña actual")}</label>
          <input
            id="actual" type="password" className="input" value={current}
            onChange={e => setCurrent(e.target.value)}
            autoComplete="current-password" autoFocus required
          />
        </div>

        <div className="field">
          <label className="field-label" htmlFor="nueva">{traducir("Contraseña nueva")}</label>
          <input
            id="nueva" type="password" className="input" value={next}
            onChange={e => setNext(e.target.value)}
            autoComplete="new-password" minLength={MIN_LENGTH} required
          />
          <span className="field-help">Mínimo {MIN_LENGTH} caracteres.</span>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="repetir">{traducir("Repite la contraseña nueva")}</label>
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
              <IconSpinner className="w-5 h-5 animate-spin" />{traducir("Guardando…")}</>
          ) : (
            traducir('Cambiar contraseña')
          )}
        </button>

        <button
          type="button" onClick={() => navigate('/')}
          className="w-full py-2 mt-2 text-[13px] text-ink-3 hover:text-ink-2 transition"
        >{traducir("Volver a mi cuenta")}</button>
      </form>
    </AuthShell>
  )
}
