import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../api/client'

export default function Login() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await api.login(username, password)
      setToken(data.access_token)
      // Redirección inmediata al dashboard
      window.location.href = '/'
    } catch (err: any) {
      setError(err.message || 'Error al iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #083151 0%, #0b497c 50%, #299ac2 100%)' }}>
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          {/* Logo placeholder - reemplazar con logo real */}
          <div className="inline-flex items-center justify-center mb-4">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Icono de proxy/red */}
              <circle cx="32" cy="32" r="30" fill="#0b497c"/>
              <circle cx="32" cy="32" r="22" fill="none" stroke="#299ac2" stroke-width="2"/>
              <path d="M20 32 L28 32 L28 24 L36 24 L36 40 L44 40" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
              <circle cx="20" cy="32" r="3" fill="#299ac2"/>
              <circle cx="44" cy="40" r="3" fill="#299ac2"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold" style={{ color: '#0b497c' }}>SquidManager</h1>
          <p className="text-gray-500 mt-1">Panel de Gestión de Proxy</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:border-transparent transition"
              style={{ '--tw-ring-color': '#0b497c' } as React.CSSProperties}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:border-transparent transition"
              style={{ '--tw-ring-color': '#0b497c' } as React.CSSProperties}
              required
            />
          </div>

          {error && (
            <div className="bg-red-50 text-red-600 text-sm p-3 rounded-lg">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full text-white py-2.5 rounded-lg font-medium disabled:opacity-50 transition flex items-center justify-center gap-2"
            style={{ backgroundColor: '#0b497c' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#083151'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#0b497c'}
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                </svg>
                Iniciando...
              </>
            ) : (
              'Iniciar Sesión'
            )}
          </button>
        </form>

        <p className="text-center text-xs text-gray-400 mt-6">
          SquidManager v0.4.0
        </p>
      </div>
    </div>
  )
}