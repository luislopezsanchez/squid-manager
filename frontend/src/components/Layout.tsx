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
    { to: '/backup', label: 'Backup/Migrar', icon: '💾' },
    { to: '/logs', label: 'Logs', icon: '📜' },
    { to: '/notifications', label: 'Notificaciones', icon: '🔔' },
    { to: '/admins', label: 'Admins', icon: '🛡️' },
  ]

  return (
    <div className="min-h-screen flex" style={{ backgroundColor: '#f0f4f8' }}>
      {/* Sidebar con colores del logo */}
      <aside className="w-64 flex flex-col fixed h-screen overflow-y-auto" style={{ backgroundColor: '#083151' }}>
        {/* Logo + título */}
        <div className="p-6 border-b" style={{ borderColor: '#0b497c' }}>
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center">
              <svg width="40" height="40" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="32" cy="32" r="30" fill="#0b497c"/>
                <circle cx="32" cy="32" r="22" fill="none" stroke="#299ac2" strokeWidth="2"/>
                <path d="M20 32 L28 32 L28 24 L36 24 L36 40 L44 40" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                <circle cx="20" cy="32" r="3" fill="#299ac2"/>
                <circle cx="44" cy="40" r="3" fill="#299ac2"/>
              </svg>
            </div>
            <div>
              <h1 className="font-bold text-lg text-white">SquidManager</h1>
              <p className="text-xs" style={{ color: '#299ac2' }}>v0.4.0</p>
            </div>
          </div>
        </div>

        {/* Navegación */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg transition ${
                  isActive
                    ? 'text-white font-medium'
                    : 'text-slate-400 hover:text-white'
                }`
              }
              style={({ isActive }) =>
                isActive ? { backgroundColor: '#0b497c' } : {}
              }
            >
              <span className="text-lg">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Sección inferior: Aplicar Cambios separado de Cerrar Sesión */}
        <div className="p-4 border-t" style={{ borderColor: '#0b497c' }}>
          {/* Aplicar Cambios - destacado */}
          <button
            onClick={handleApply}
            disabled={applying}
            className={`w-full px-4 py-3 rounded-lg font-medium transition flex items-center justify-center gap-2 mb-3 ${
              applying ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            style={{
              backgroundColor: applying ? '#1a3a5c' : '#299ac2',
              color: '#fff',
            }}
            onMouseEnter={(e) => { if (!applying) e.currentTarget.style.backgroundColor = '#1a7a9a' }}
            onMouseLeave={(e) => { if (!applying) e.currentTarget.style.backgroundColor = '#299ac2' }}
          >
            {applying ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                </svg>
                Aplicando...
              </>
            ) : (
              <>⚡ Aplicar Cambios</>
            )}
          </button>
          <p className="text-xs text-center mb-4" style={{ color: '#4a6a8a' }}>
            Genera squid.conf y recarga Squid
          </p>

          {/* Separador */}
          <div className="border-t pt-3" style={{ borderColor: '#1a3a5c' }}>
            <button
              onClick={handleLogout}
              className="w-full text-left px-4 py-2.5 rounded-lg transition flex items-center gap-3 text-slate-400 hover:text-white"
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#5a1a1a'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <span>🚪</span> Cerrar Sesión
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto ml-64">
        <Outlet />
      </main>

      {/* Toast notification */}
      {toast && (
        <div
          className="fixed top-6 right-6 z-50 px-6 py-4 rounded-xl shadow-2xl text-white font-medium animate-slide-in"
          style={{
            backgroundColor: toast.type === 'success' ? '#0b497c' : toast.type === 'warning' ? '#d97706' : '#dc2626',
          }}
        >
          {toast.msg}
        </div>
      )}
    </div>
  )
}