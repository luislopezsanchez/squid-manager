import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { clearToken, api } from '../api/client'

export default function Layout() {
  const navigate = useNavigate()
  const [applying, setApplying] = useState(false)
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'warning' } | null>(null)

  const handleLogout = () => {
    clearToken()
    navigate('/login')
  }

  const showToast = (msg: string, type: 'success' | 'error' | 'warning') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 6000)
  }

  const handleApply = async () => {
    setApplying(true)
    setToast(null)
    try {
      const result = await api.applyConfig()
      if (result.status === 'ok') {
        showToast('✅ Cambios aplicados correctamente. Squid reconfigurado.', 'success')
      } else {
        showToast(`⚠️ ${result.message}`, 'warning')
      }
    } catch (e: any) {
      showToast(`❌ Error: ${e.message}`, 'error')
    } finally {
      setApplying(false)
    }
  }

  const navItems = [
    { to: '/', label: 'Dashboard', icon: '📊' },
    { to: '/users', label: 'Usuarios', icon: '👥' },
    { to: '/acls', label: 'ACLs', icon: '🏷️' },
    { to: '/rules', label: 'Reglas de Acceso', icon: '📋' },
    { to: '/delay-pools', label: 'Ancho de Banda', icon: '🐌' },
    { to: '/ldap', label: 'LDAP', icon: '🔗' },
    { to: '/settings', label: 'Configuración', icon: '⚙️' },
    { to: '/certificate', label: 'Certificado SSL', icon: '🔐' },
    { to: '/audit', label: 'Auditoría', icon: '📝' },
  ]

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <aside className="w-64 bg-slate-900 text-white flex flex-col fixed h-screen overflow-y-auto">
        <div className="p-6 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold">S</span>
            </div>
            <div>
              <h1 className="font-bold text-lg">SquidManager</h1>
              <p className="text-xs text-slate-400">v0.3.0</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg transition ${
                  isActive ? 'bg-primary-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                }`
              }
            >
              <span className="text-lg">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-700">
          <button
            onClick={handleApply}
            disabled={applying}
            className={`w-full px-4 py-3 rounded-lg font-medium transition flex items-center justify-center gap-2 ${
              applying ? 'bg-slate-600 text-slate-300' : 'bg-green-600 text-white hover:bg-green-700'
            }`}
          >
            {applying ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
                Aplicando...
              </>
            ) : (
              <>⚡ Aplicar Cambios</>
            )}
          </button>
          <p className="text-xs text-slate-500 mt-2 text-center">Genera squid.conf y recarga Squid</p>
          <button
            onClick={handleLogout}
            className="w-full mt-3 text-left px-4 py-2.5 rounded-lg text-slate-300 hover:bg-red-900/50 transition flex items-center gap-3"
          >
            <span>🚪</span> Cerrar Sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto ml-64">
        <Outlet />
      </main>

      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-6 py-4 rounded-xl shadow-2xl text-white font-medium animate-slide-in ${
          toast.type === 'success' ? 'bg-green-600' :
          toast.type === 'warning' ? 'bg-yellow-600' : 'bg-red-600'
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}