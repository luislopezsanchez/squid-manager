import { traducir, cambiarIdioma, idiomaActual, IDIOMAS, type Idioma } from '../i18n'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import { clearToken, api, canWrite, isSuperadmin, getRole } from '../api/client'
import {
  IconDashboard, IconUsers, IconTag, IconRules, IconGauge, IconLink, IconGroups,
  IconSettings, IconLock, IconAudit, IconBackup, IconLogs, IconBell, IconShield, IconSend,
  IconBolt, IconKey, IconLogout, IconSpinner, IconEye, IconGlobe, IconAssistant, IconArchive,
  IconChevronDown,
} from './Icons'

type Item = { to: string; label: string; Icon: (p: { className?: string }) => JSX.Element }
// id estable, independiente del titulo traducido: el titulo cambia segun
// el idioma, pero la clave que se guarda en localStorage (que grupo quedo
// abierto/cerrado) no puede depender de eso.
type Grupo = { id: string; titulo: string; items: Item[] }

// Que grupo queda abierto entre sesiones, por admin -en el navegador de
// cada uno, no en el backend: es una preferencia de pantalla, no un dato
// que valga la pena sincronizar entre dispositivos. Acordeon exclusivo -a
// pedido del usuario tras probarlo en vivo: con varios grupos abiertos a
// la vez el menu seguia siendo largo. Se guarda como "cual esta abierto"
// (o null si estan todos cerrados), no un set de colapsados: abrir uno
// cierra los demas por diseño, no por accidente.
const CLAVE_ABIERTO = 'squidmanager:menu-abierto'

function leerAbierto(): string | null {
  try {
    return localStorage.getItem(CLAVE_ABIERTO)
  } catch {
    return null
  }
}

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [grupoManual, setGrupoManual] = useState<string | null>(leerAbierto)
  const [applying, setApplying] = useState(false)
  const [pending, setPending] = useState(false)
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'warning' } | null>(null)
  const [version, setVersion] = useState<{ version: string; update_available: boolean } | null>(null)
  // Detecta, desde CUALQUIER página (no solo /actualizaciones), que una
  // actualización que estaba aprobada/programada ya terminó -por si el
  // admin navegó a otro lado mientras esperaba la hora programada-. Mismo
  // diseño de dos efectos que Actualizaciones.tsx: nada de lógica de
  // timing manual, solo comparar valores en cada render.
  const [commitVigilado, setCommitVigilado] = useState<string | null>(null)
  const [actualizado, setActualizado] = useState(false)
  const fastPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const readOnly = !canWrite()

  const checkPending = () => {
    api.getPending().then(r => setPending(r.dirty)).catch(() => {})
  }

  const checkVersion = () => {
    api.getUpdateStatus()
      .then(r => {
        setVersion({ version: r.version_actual, update_available: !!r.check?.update_available })
        const enCurso = r.apply?.status === 'running' || r.apply?.status === 'verificando'
        const yaVencida = !!(r.request?.approved && r.request?.scheduled_at
          && new Date(r.request.scheduled_at).getTime() <= Date.now())
        const vigilando = enCurso || yaVencida
        if (vigilando) {
          setCommitVigilado(prev => prev ?? (r.check?.local_commit ?? null))
          if (!fastPollRef.current) {
            fastPollRef.current = setInterval(checkVersion, 4000)
          }
        } else if (fastPollRef.current) {
          clearInterval(fastPollRef.current)
          fastPollRef.current = null
        }
        setCommitVigilado(prev => {
          if (prev && r.check?.local_commit && r.check.local_commit !== prev) {
            setActualizado(true)
            return null
          }
          return prev
        })
      })
      .catch(() => {})
  }

  useEffect(() => {
    checkPending()
    checkVersion()
    const interval = setInterval(checkPending, 5000)
    // La comprobación real contra GitHub la hace el backend cada 6 h; acá
    // solo se relee el estado ya calculado, así que alcanza con sondear
    // bastante menos seguido -salvo mientras haya un ciclo activo, ver
    // checkVersion(), que ahí pasa a cada 4s por su cuenta-.
    const intervalVersion = setInterval(checkVersion, 5 * 60 * 1000)
    // Refresco inmediato cuando una pantalla guarda un cambio que requiere
    // Aplicar, en vez de esperar hasta 5s a que llegue el próximo sondeo.
    window.addEventListener('squidmanager:cambio-pendiente', checkPending)
    return () => {
      clearInterval(interval)
      clearInterval(intervalVersion)
      if (fastPollRef.current) clearInterval(fastPollRef.current)
      window.removeEventListener('squidmanager:cambio-pendiente', checkPending)
    }
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
      showToast(traducir("Tu cuenta es de solo lectura: no puede aplicar cambios."), 'warning')
      return
    }
    setApplying(true)
    setToast(null)
    try {
      const result = await api.applyConfig()
      if (result.status === 'ok') {
        showToast(traducir("Cambios aplicados. Squid está usando la configuración nueva."), 'success')
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

  // Asistente vive fuera de los grupos colapsables: es de uso frecuente y
  // conceptualmente distinto (ayuda, no monitoreo/politica/sistema) -antes
  // estaba enterrado dentro de "Vigilancia", lo cual no tenia sentido.
  const asistente: Item = { to: '/asistente', label: traducir("Asistente"), Icon: IconAssistant }

  // Reorganizado en 5 grupos en vez de 3 (2026-09-09): "Sistema" habia
  // crecido a 9 items, dificil de escanear, y no habia ningun lugar para
  // reportes/estadisticas (Top 20, cache, cuotas) ni para una futura
  // seccion de cluster/monitoreo centralizado -esta ultima se agrega el
  // dia que exista, no antes: un grupo vacio no aporta nada al menu.
  // Los grupos sin items no se renderizan (ver el filter() de abajo), asi
  // que agregar "Reportes y estadisticas" como grupo ya armado, aunque
  // estos items no existen todavia.
  const grupos: Grupo[] = [
    {
      id: 'vigilancia',
      titulo: traducir("Vigilancia"),
      items: [
        { to: '/', label: traducir("Dashboard"), Icon: IconDashboard },
        { to: '/logs', label: traducir("Registros"), Icon: IconLogs },
        { to: '/logs-historico', label: traducir("Histórico"), Icon: IconArchive },
        { to: '/audit', label: traducir("Auditoría"), Icon: IconAudit },
      ],
    },
    {
      id: 'reportes',
      titulo: traducir("Reportes y estadísticas"),
      items: [
        { to: '/reportes/cache', label: traducir("Estadísticas de caché"), Icon: IconArchive },
        // Top 20 con graficos y cuotas por usuario/grupo se suman aca
        // cuando existan.
      ],
    },
    {
      id: 'politicas',
      titulo: traducir("Políticas"),
      items: [
        { to: '/users', label: traducir("Usuarios"), Icon: IconUsers },
        { to: '/groups', label: traducir("Grupos"), Icon: IconGroups },
        { to: '/acls', label: traducir("ACLs"), Icon: IconTag },
        { to: '/rules', label: traducir("Reglas de acceso"), Icon: IconRules },
        { to: '/delay-pools', label: traducir("Ancho de banda"), Icon: IconGauge },
      ],
    },
    {
      id: 'integraciones',
      titulo: traducir("Integraciones"),
      items: [
        { to: '/ldap', label: 'LDAP', Icon: IconLink },
        { to: '/kerberos', label: 'Kerberos', Icon: IconKey },
        { to: '/syslog', label: traducir("Syslog externo"), Icon: IconSend },
        { to: '/parent-proxy', label: traducir("Proxy padre"), Icon: IconLink },
        { to: '/notifications', label: traducir("Notificaciones"), Icon: IconBell },
      ],
    },
    {
      id: 'sistema',
      titulo: traducir("Sistema"),
      items: [
        { to: '/certificate', label: traducir("Certificado"), Icon: IconLock },
        { to: '/settings', label: traducir("Configuración"), Icon: IconSettings },
        { to: '/backup', label: traducir("Backup y migración"), Icon: IconBackup },
        ...(isSuperadmin() ? [{ to: '/admins', label: traducir("Administradores"), Icon: IconShield }] : []),
      ],
    },
  ].filter(g => g.items.length > 0)

  const grupoActivoId = grupos.find(g => g.items.some(it => it.to === '/'
    ? location.pathname === '/'
    : location.pathname.startsWith(it.to)))?.id

  // Acordeon exclusivo: como mucho un grupo abierto a la vez, para que el
  // menu no vuelva a crecer aunque haya 5 secciones. Mientras el admin no
  // haya tocado nada (grupoManual === null, primera carga sin preferencia
  // guardada) se abre solo el grupo de la pagina en la que esta parado.
  // En cuanto hace clic en un encabezado, esa eleccion manda del todo -
  // incluso pudiendo dejar TODO cerrado ('' guardado a proposito, no
  // null-, que el usuario pidio explicitamente poder hacer- y ya no se
  // fuerza a abrir el grupo activo solo por estar navegando ahi: es el
  // comportamiento esperado de un acordeon normal, no una excepcion.
  const grupoAbierto = (id: string) =>
    grupoManual === null ? id === grupoActivoId : grupoManual === id

  const toggleGrupo = (id: string) => {
    const nuevo = grupoAbierto(id) ? '' : id
    setGrupoManual(nuevo)
    try {
      localStorage.setItem(CLAVE_ABIERTO, nuevo)
    } catch {
      // localStorage puede fallar (modo privado, cuota) -no es critico,
      // la preferencia simplemente no sobrevive al reload.
    }
  }

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
            <span className="text-[17px] font-extrabold text-white tracking-tight">{traducir("SquidManager")}</span>
            <span className="text-[10.5px] font-semibold uppercase tracking-[.1em] text-brand-300">{traducir("Proxy")}</span>
          </div>
        </div>

        {/* Versión + aviso de actualización disponible */}
        {version && (
          <NavLink
            to="/actualizaciones"
            className="relative mx-4 mb-3 flex items-center justify-between px-2.5 py-1.5 rounded-lg
                       text-[11px] font-medium text-[#B9D2E0]/75 hover:bg-white/[.07] hover:text-white transition"
            title={traducir("Ver actualizaciones")}
          >
            <span className="font-mono">v{version.version}</span>
            <span className="relative">
              <IconBell className={`w-[15px] h-[15px] ${version.update_available ? 'text-brand-300' : 'opacity-50'}`} />
              {version.update_available && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-warn ring-2 ring-[#0f2f4a]" />
              )}
            </span>
          </NavLink>
        )}

        {/* Navegación */}
        <nav className="relative flex-1 px-3 pb-3">
          {/* Asistente: fijo, fuera de los grupos colapsables -uso frecuente,
              no encaja en ningun grupo de tarea. */}
          <NavLink to={asistente.to} className={(p) => `${navClass(p)} mb-2`}>
            {({ isActive }) => (
              <>
                <asistente.Icon className={`w-[18px] h-[18px] flex-none ${isActive ? 'text-brand-300' : 'opacity-85'}`} />
                {asistente.label}
              </>
            )}
          </NavLink>

          {grupos.map(grupo => {
            const abierto = grupoAbierto(grupo.id)
            return (
              <div key={grupo.id}>
                <button
                  type="button"
                  onClick={() => toggleGrupo(grupo.id)}
                  aria-expanded={abierto}
                  className={[
                    'w-full flex items-center justify-between px-2.5 py-2 mt-1 rounded-lg',
                    'text-[11px] font-bold uppercase tracking-[.12em] transition',
                    // Mismos tokens de color que los items de navegacion (navClass),
                    // no un tono aparte mas tenue: ahi ya esta probado que se lee
                    // bien sobre este fondo -el 10px/brand-300/65 anterior se veia
                    // deslavado, reportado en vivo por el usuario con captura.
                    abierto
                      ? 'text-white bg-white/[.10]'
                      : 'text-[#B9D2E0] hover:bg-white/[.07] hover:text-white',
                  ].join(' ')}
                >
                  {grupo.titulo}
                  <IconChevronDown
                    className={`w-3.5 h-3.5 flex-none transition-transform ${abierto ? 'text-brand-300' : 'opacity-70 -rotate-90'}`}
                  />
                </button>
                {abierto && (
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
                )}
              </div>
            )
          })}
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
                    <IconSpinner className="w-4 h-4 animate-spin" />{traducir("Aplicando…")}</>
                ) : (
                  <>
                    <IconBolt className="w-4 h-4" />{traducir("Aplicar cambios")}</>
                )}
              </button>
              <p className="text-[11px] text-center mt-2 text-[#B9D2E0]/60">
                {pending
                  ? traducir("Hay cambios sin aplicar")
                  : traducir("Squid está al día")}
              </p>
            </>
          )}

          <div className="mt-3 pt-3 border-t border-white/10 flex flex-col gap-0.5">
            {/* Selector de idioma. Cambiarlo recarga la pagina: los textos se
                resuelven al cargar el modulo, asi que es la unica forma de que
                toda la interfaz quede coherente de una vez. */}
            <label className="flex items-center gap-3 px-2.5 py-2 rounded-lg text-[13.5px] font-medium
                              text-[#B9D2E0] hover:bg-white/[.07] hover:text-white transition cursor-pointer">
              <IconGlobe className="w-[17px] h-[17px] flex-none opacity-85" />
              <select
                aria-label={traducir("Idioma")}
                value={idiomaActual()}
                onChange={e => cambiarIdioma(e.target.value as Idioma)}
                className="bg-transparent border-0 outline-none cursor-pointer w-full text-[13.5px]"
              >
                {IDIOMAS.map(i => (
                  <option key={i.codigo} value={i.codigo} className="text-ink">
                    {i.nombre}
                  </option>
                ))}
              </select>
            </label>
            <NavLink
              to="/cambiar-contrasena"
              className="flex items-center gap-3 px-2.5 py-2 rounded-lg text-[13.5px] font-medium
                         text-[#B9D2E0] hover:bg-white/[.07] hover:text-white transition"
            >
              <IconKey className="w-[17px] h-[17px] flex-none opacity-85" />{traducir("Cambiar contraseña")}</NavLink>
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-2.5 py-2 rounded-lg text-[13.5px] font-medium
                         text-[#B9D2E0] hover:bg-danger/25 hover:text-white transition text-left"
            >
              <IconLogout className="w-[17px] h-[17px] flex-none opacity-85" />{traducir("Cerrar sesión")}</button>
          </div>
        </div>
      </aside>

      {/* ---------- Contenido ---------- */}
      <main className="flex-1 ml-[248px] min-w-0">
        {actualizado && (
          <div className="flex items-center gap-3 px-6 py-2 text-[13px] font-medium border-b"
               style={{ background: 'var(--ok-soft)', color: 'var(--ok)', borderColor: 'var(--ok)' }}>
            <IconBell className="w-4 h-4 flex-none" />
            <span className="flex-1">
              {traducir("Se aplicó una actualización de SquidManager. Recargá la página para ver la versión nueva.")}
            </span>
            <button
              onClick={() => window.location.reload()}
              className="flex-none px-3 py-1 rounded-md text-xs font-bold text-white transition"
              style={{ background: 'var(--ok)' }}
            >
              {traducir("Recargar")}
            </button>
          </div>
        )}
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
