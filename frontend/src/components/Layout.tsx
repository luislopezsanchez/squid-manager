import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { clearToken, api, canWrite, isSuperadmin, getRole } from '../api/client'
import {
  IconDashboard, IconUsers, IconTag, IconRules, IconGauge, IconLink, IconGroups,
  IconSettings, IconLock, IconAudit, IconBackup, IconLogs, IconBell, IconShield, IconSend,
  IconBolt, IconKey, IconLogout, IconSpinner, IconEye,
} from './Icons'

type Item = { to: string; label: string; Icon: (p: { className?: string }) => JSX.Element }
type Grupo = { titulo: string; items: Item[] }

export default function Layout() {
  const navigate = useNavigate()
  const [applying, setApplying] = useState(false)
  const [pending, setPending] = useState(false)
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'warning' } | null>(null)

  const readOnly = !canWrite()

  const checkPending = () => {
    api.getPending().then(r => setPending(r.dirty)).catch(() => {})
  }

  useEffect(() => {
    checkPending()
    const interval = setInterval(checkPending, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleLogout = () => {
    clearToken()
    navigate('/login')
  }

  const showToast = (msg: string, type: 'success' | 'error' | 'warning') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 6000)
  }

  const handleApply = async () => {
    if (!canWrite()) {
      showToast('Tu cuenta es de solo lectura: no puede aplicar cambios.', 'warning')
      return
    }
    setApplying(true)
    setToast(null)
    try {
      const result = await api.applyConfig()
      if (result.status === 'ok') {
        showToast('Cambios aplicados. Squid está usando la configuración nueva.', 'success')
        setPending(false)
      } else {
        showToast(result.message, 'warning')
      }
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setApplying(false)
      checkPending()
    }
  }

  // El menú va agrupado por tarea, no como una lista larga de catorce entradas.
  const grupos: Grupo[] = [
    {
      titulo: 'Vigilancia',
      items: [
        { to: '/', label: 'Dashboard', Icon: IconDashboard },
        { to: '/logs', label: 'Registros', Icon: IconLogs },
        { to: '/audit', label: 'Auditoría', Icon: IconAudit },
      ],
    },
    {
      titulo: 'Políticas',
      items: [
        { to: '/users', label: 'Usuarios', Icon: IconUsers },
        { to: '/groups', label: 'Grupos', Icon: IconGroups },
        { to: '/acls', label: 'ACLs', Icon: IconTag },
        { to: '/rules', label: 'Reglas de acceso', Icon: IconRules },
        { to: '/delay-pools', label: 'Ancho de banda', Icon: IconGauge },
      ],
    },
    {
      titulo: 'Sistema',
      items: [
        { to: '/ldap', label: 'LDAP', Icon: IconLink },
        { to: '/certificate', label: 'Certificado', Icon: IconLock },
        { to: '/settings', label: 'Configuración', Icon: IconSettings },
        { to: '/notifications', label: 'Notificaciones', Icon: IconBell },
        { to: '/syslog', label: 'Syslog externo', Icon: IconSend },
        { to: '/backup', label: 'Backup y migración', Icon: IconBackup },
        ...(isSuperadmin() ? [{ to: '/admins', label: 'Administradores', Icon: IconShield }] : []),
      ],
    },
  ]

  const navClass = ({ isActive }: { isActive: boolean }) =>
    [
      'flex items-center gap-3 px-2.5 py-2 rounded-lg text-[14px] transition',
      isActive
        ? 'text-white font-semibold bg-white/[.14] ring-1 ring-inset ring-brand-300/25'
        : 'text-[#B9D2E0] font-medium hover:bg-white/[.07] hover:text-white',
    ].join(' ')

  return (
    <div className="min-h-screen flex bg-ground">
      {/* ---------- Barra lateral ---------- */}
      <aside
        className="w-[248px] fixed h-screen flex flex-col overflow-y-auto z-20"
        style={{ background: 'var(--side-gradient)' }}
      >
        {/* Trama de circuito, guiño a los del logo */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[.16]"
          style={{
            backgroundImage:
              'linear-gradient(to right, rgba(127,208,226,.5) 1px, transparent 1px),' +
              'linear-gradient(to bottom, rgba(127,208,226,.5) 1px, transparent 1px)',
            backgroundSize: '34px 34px',
            maskImage: 'radial-gradient(circle at 30% 10%, #000 0%, transparent 62%)',
            WebkitMaskImage: 'radial-gradient(circle at 30% 10%, #000 0%, transparent 62%)',
          }}
        />

        {/* Marca */}
        <div className="relative flex items-center gap-3 px-4 pt-5 pb-4">
          <img
            src="/brand/logo-128.png"
            alt=""
            width={42}
            height={40}
            className="w-[42px] h-auto"
            style={{ filter: 'drop-shadow(0 0 10px rgba(127,208,226,.28))' }}
          />
          <div className="flex flex-col leading-tight">
            <span className="text-[17px] font-extrabold text-white tracking-tight">SquidManager</span>
            <span className="text-[10.5px] font-semibold uppercase tracking-[.1em] text-brand-300">
              Proxy
            </span>
          </div>
        </div>

        {/* Navegación */}
        <nav className="relative flex-1 px-3 pb-3">
          {grupos.map(grupo => (
            <div key={grupo.titulo}>
              <p className="px-2.5 pt-4 pb-1.5 text-[10px] font-bold uppercase tracking-[.13em] text-brand-300/65">
                {grupo.titulo}
              </p>
              <div className="flex flex-col gap-0.5">
                {grupo.items.map(({ to, label, Icon }) => (
                  <NavLink key={to} to={to} end={to === '/'} className={navClass}>
                    {({ isActive }) => (
                      <>
                        <Icon className={`w-[18px] h-[18px] flex-none ${isActive ? 'text-brand-300' : 'opacity-85'}`} />
                        {label}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Pie: aplicar cambios y sesión */}
        <div className="relative px-3 pb-4 pt-3 border-t border-white/10">
          {!readOnly && (
            <>
              <button
                onClick={handleApply}
                disabled={applying}
                className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-[10px]
                            text-[14px] font-bold text-white transition
                            ${applying ? 'opacity-60 cursor-not-allowed' : 'hover:brightness-110'}`}
                style={{
                  background: pending
                    ? 'linear-gradient(135deg, #E0A036, #C77C15)'
                    : 'linear-gradient(135deg, var(--brand-400), var(--brand-500))',
                  boxShadow: pending
                    ? '0 4px 14px -4px rgba(199,124,21,.6)'
                    : '0 4px 14px -4px rgba(72,179,208,.6)',
                }}
              >
                {applying ? (
                  <>
                    <IconSpinner className="w-4 h-4 animate-spin" />
                    Aplicando…
                  </>
                ) : (
                  <>
                    <IconBolt className="w-4 h-4" />
                    Aplicar cambios
                  </>
                )}
              </button>
              <p className="text-[11px] text-center mt-2 text-[#B9D2E0]/60">
                {pending ? 'Hay cambios sin aplicar' : 'Squid está al día'}
              </p>
            </>
          )}

          <div className="mt-3 pt-3 border-t border-white/10 flex flex-col gap-0.5">
            <NavLink
              to="/cambiar-contrasena"
              className="flex items-center gap-3 px-2.5 py-2 rounded-lg text-[13.5px] font-medium
                         text-[#B9D2E0] hover:bg-white/[.07] hover:text-white transition"
            >
              <IconKey className="w-[17px] h-[17px] flex-none opacity-85" />
              Cambiar contraseña
            </NavLink>
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-2.5 py-2 rounded-lg text-[13.5px] font-medium
                         text-[#B9D2E0] hover:bg-danger/25 hover:text-white transition text-left"
            >
              <IconLogout className="w-[17px] h-[17px] flex-none opacity-85" />
              Cerrar sesión
            </button>
          </div>
        </div>
      </aside>

      {/* ---------- Contenido ---------- */}
      <main className="flex-1 ml-[248px] min-w-0">
        {readOnly && (
          <div className="flex items-center gap-2 px-6 py-2 text-[13px] font-medium bg-warn-soft text-warn border-b border-warn/20">
            <IconEye className="w-4 h-4 flex-none" />
            Cuenta de solo lectura ({getRole()}): puedes consultarlo todo, pero no guardar cambios.
          </div>
        )}
        <Outlet />
      </main>

      {/* ---------- Aviso emergente ---------- */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 animate-slide-in max-w-md">
          <div
            className={`card flex items-start gap-3 p-4 shadow-lg
              ${toast.type === 'success' ? 'note-ok' : toast.type === 'warning' ? 'note-warn' : 'note-danger'}`}
          >
            <span
              className={`stat-icon flex-none ${
                toast.type === 'success' ? 'stat-icon-ok' : toast.type === 'warning' ? 'stat-icon-warn' : ''
              }`}
              style={toast.type === 'error' ? { background: 'var(--danger-soft)', color: 'var(--danger)' } : undefined}
            >
              {toast.type === 'success' ? <IconShield /> : <IconBolt />}
            </span>
            <p className="text-[13.5px] text-ink-2 leading-snug">{toast.msg}</p>
          </div>
        </div>
      )}
    </div>
  )
}
