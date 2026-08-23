import React, { useState } from 'react'
import { api, setToken } from '../api/client'
import AuthShell from '../components/AuthShell'
import { IconSpinner, IconAlert } from '../components/Icons'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await api.login(username, password)
      setToken(data.access_token)
      if (data.role) localStorage.setItem('role', data.role)
      // Una contraseña que conoce quien creó la cuenta no sirve como secreto:
      // se cambia antes de entrar al panel.
      if (data.must_change_password) {
        localStorage.setItem('mustChangePassword', '1')
        window.location.href = '/cambiar-contrasena'
        return
      }
      localStorage.removeItem('mustChangePassword')
      window.location.href = '/'
    } catch (err: any) {
      setError(err.message || 'No se pudo iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      titulo="SquidManager"
      subtitulo="Panel de gestión del proxy"
      pie="SquidManager v0.6"
    >
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label className="field-label" htmlFor="usuario">Usuario</label>
          <input
            id="usuario"
            type="text"
            className="input"
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </div>

        <div className="field">
          <label className="field-label" htmlFor="clave">Contraseña</label>
          <input
            id="clave"
            type="password"
            className="input"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete="current-password"
            required
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
              Entrando…
            </>
          ) : (
            'Entrar'
          )}
        </button>
      </form>
    </AuthShell>
  )
}
