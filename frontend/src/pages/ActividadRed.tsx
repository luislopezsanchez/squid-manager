import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'

type FilaUsuario = { user: string; bytes: number; requests: number }
type FilaDominio = { domain: string; requests: number; bytes: number }
type FilaBloqueado = { user: string; blocked_requests: number; account_status: 'enabled' | 'disabled' | 'unknown' }
type RespuestaBloqueados = { users: FilaBloqueado[]; anonymous_blocked: number }

type Pestana = 'usuarios' | 'dominios' | 'bloqueados-dominio' | 'bloqueados-usuario'

const COLORES: Record<Pestana, string> = {
  usuarios: '#0B497C',
  dominios: '#2E93BC',
  'bloqueados-dominio': '#C0392B',
  'bloqueados-usuario': '#C0392B',
}

// Por que importa cada vista -no es solo "una tabla mas": cada una responde
// una pregunta concreta que un admin de red se hace de verdad.
const EXPLICACIONES: Record<Pestana, string> = {
  usuarios: traducir(
    "Quién consume más ancho de banda o hace más peticiones. Un consumo alto no es necesariamente un problema -puede ser trabajo legítimo-, pero es el primer lugar donde mirar si el enlace va lento o si conviene revisar una cuota."
  ),
  dominios: traducir(
    "Qué se visita más, permitido o no. Sirve para decidir con datos reales si vale la pena sumar una ACL nueva -si algo no productivo aparece seguido acá, es candidato a bloquear- en vez de adivinar."
  ),
  'bloqueados-dominio': traducir(
    "Contra qué está chocando la política de acceso ahora mismo. Si un dominio se repite mucho, la regla que lo bloquea está funcionando de verdad -no es solo teoría en la configuración."
  ),
  'bloqueados-usuario': traducir(
    "Quién insiste más contra la política. Unos pocos bloqueos son ruido normal (un enlace viejo, una redirección); una cifra alta y sostenida de la misma persona sí amerita una conversación."
  ),
}

/** Barra horizontal proporcional al máximo del conjunto -no a una escala

 * fija-, para que el ranking se lea de un vistazo aunque el primero le
 * saque una distancia enorme al resto (caso real y frecuente: un usuario
 * o dominio muy por encima de todos los demás). */
function FilaBarra({ etiqueta, valor, valorFormateado, maximo, color, posicion }: {
  etiqueta: string; valor: number; valorFormateado: string; maximo: number; color: string; posicion: number
}) {
  const pct = maximo > 0 ? Math.max((valor / maximo) * 100, valor > 0 ? 2 : 0) : 0
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="w-6 flex-none text-right text-xs font-semibold text-ink-3 tabular">{posicion}</span>
      <span className="w-40 md:w-56 flex-none truncate text-sm text-ink" title={etiqueta}>{etiqueta}</span>
      <div className="flex-1 h-5 bg-line-soft rounded-md overflow-hidden">
        <div
          className="h-full rounded-md transition-all"
          style={{ width: `${pct}%`, background: color, minWidth: valor > 0 ? '2px' : 0 }}
        />
      </div>
      <span className="w-20 flex-none text-right text-sm font-semibold tabular" style={{ color }}>
        {valorFormateado}
      </span>
    </div>
  )
}

/** Anillo que muestra que porcion del total concentra el top 3 -el

 * "grafico" que complementa a la tabla de barras, no una repeticion del
 * mismo dato: responde "¿esto esta repartido parejo, o son cuatro
 * personas/sitios los que explican casi todo?", que la tabla sola no
 * contesta de un vistazo. */
function AnilloConcentracion({ pct, color }: { pct: number; color: string }) {
  const size = 108
  const stroke = 10
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const arco = Math.max(0, Math.min(pct, 100))
  return (
    <div className="relative flex-none" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--line-soft)" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={circumference}
          strokeDashoffset={circumference - (arco / 100) * circumference}
          style={{ transition: 'stroke-dashoffset .6s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-extrabold tabular" style={{ color: 'var(--ink)' }}>{Math.round(pct)}%</span>
      </div>
    </div>
  )
}

export default function ActividadRed() {
  const [pestana, setPestana] = useState<Pestana>('usuarios')
  const [porDatos, setPorDatos] = useState(true) // solo aplica a la pestana "usuarios"
  const [usuarios, setUsuarios] = useState<FilaUsuario[] | null>(null)
  const [dominios, setDominios] = useState<FilaDominio[] | null>(null)
  const [bloqueadosDominio, setBloqueadosDominio] = useState<FilaDominio[] | null>(null)
  const [bloqueadosUsuario, setBloqueadosUsuario] = useState<FilaBloqueado[] | null>(null)
  const [anonimosBloqueados, setAnonimosBloqueados] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const cargar = () => {
    Promise.all([
      api.getTopUsers(20),
      api.getTopDomains(20, false),
      api.getTopDomains(20, true),
      api.getTopBlockedUsers(20),
    ])
      .then(([u, d, bd, bu]: [FilaUsuario[], FilaDominio[], FilaDominio[], RespuestaBloqueados]) => {
        setUsuarios(u)
        setDominios(d)
        setBloqueadosDominio(bd)
        setBloqueadosUsuario(bu.users)
        setAnonimosBloqueados(bu.anonymous_blocked)
        setError(null)
      })
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    cargar()
    const interval = setInterval(cargar, 30000)
    return () => clearInterval(interval)
  }, [])

  const PESTANAS: { id: Pestana; label: string }[] = [
    { id: 'usuarios', label: traducir("Usuarios") },
    { id: 'dominios', label: traducir("Sitios visitados") },
    { id: 'bloqueados-dominio', label: traducir("Sitios bloqueados") },
    { id: 'bloqueados-usuario', label: traducir("Usuarios con más bloqueos") },
  ]

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  const color = COLORES[pestana]

  let filas: { etiqueta: string; valor: number; valorFormateado: string }[] = []
  if (pestana === 'usuarios' && usuarios) {
    filas = usuarios.map(u => ({
      etiqueta: u.user,
      valor: porDatos ? u.bytes : u.requests,
      valorFormateado: porDatos ? formatBytes(u.bytes) : `${formatNumber(u.requests)} ${traducir("req")}`,
    }))
  } else if (pestana === 'dominios' && dominios) {
    filas = dominios.map(d => ({ etiqueta: d.domain, valor: d.requests, valorFormateado: formatNumber(d.requests) }))
  } else if (pestana === 'bloqueados-dominio' && bloqueadosDominio) {
    filas = bloqueadosDominio.map(d => ({ etiqueta: d.domain, valor: d.requests, valorFormateado: formatNumber(d.requests) }))
  } else if (pestana === 'bloqueados-usuario' && bloqueadosUsuario) {
    filas = bloqueadosUsuario.map(b => ({
      // account_status distingue "la cuenta esta deshabilitada de verdad" de
      // "denegado por otra razon" (credenciales viejas, politica de grupo)
      // -no es lo mismo, ver la nota en metrics_service.get_top_blocked_users.
      etiqueta: b.account_status === 'disabled' ? `${b.user} (${traducir("deshabilitado")})` : b.user,
      valor: b.blocked_requests,
      valorFormateado: formatNumber(b.blocked_requests),
    }))
  }

  const maximo = Math.max(...filas.map(f => f.valor), 1)
  const total = filas.reduce((acc, f) => acc + f.valor, 0)
  const top3 = filas.slice(0, 3).reduce((acc, f) => acc + f.valor, 0)
  const pctTop3 = total > 0 ? (top3 / total) * 100 : 0

  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Actividad de red")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("De las últimas 1.000 peticiones registradas — se refresca solo, cada 30 s.")}
      </p>

      {error && <div className="mb-6 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}

      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex gap-1 bg-line-soft p-1 rounded-lg">
          {PESTANAS.map(p => (
            <button
              key={p.id}
              onClick={() => setPestana(p.id)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                pestana === p.id ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {pestana === 'usuarios' && (
          <div className="flex gap-1 bg-line-soft p-1 rounded-lg">
            <button
              onClick={() => setPorDatos(true)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                porDatos ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'
              }`}
            >
              {traducir("Datos")}
            </button>
            <button
              onClick={() => setPorDatos(false)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                !porDatos ? 'bg-white text-ink shadow-sm' : 'text-ink-3 hover:text-ink'
              }`}
            >
              {traducir("Peticiones")}
            </button>
          </div>
        )}
      </div>

      <p className="text-sm text-ink-2 mb-4 max-w-3xl">{EXPLICACIONES[pestana]}</p>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4">
        <div className="card p-5">
          {filas.length === 0 ? (
            <p className="text-sm text-ink-3 text-center py-8">{traducir("Sin datos todavía.")}</p>
          ) : (
            <div className="flex flex-col">
              {filas.map((f, i) => (
                <FilaBarra
                  key={f.etiqueta}
                  posicion={i + 1}
                  etiqueta={f.etiqueta}
                  valor={f.valor}
                  valorFormateado={f.valorFormateado}
                  maximo={maximo}
                  color={color}
                />
              ))}
            </div>
          )}
          {pestana === 'bloqueados-usuario' && anonimosBloqueados > 0 && (
            <p className="text-[11px] text-ink-3 mt-3 pt-3 border-t border-line-soft">
              {traducir(
                "+ {n} bloqueos sin usuario identificado (tráfico de fondo del navegador, sin credenciales)",
                { n: anonimosBloqueados },
              )}
            </p>
          )}
        </div>

        {filas.length > 0 && (
          <div className="card p-5 flex flex-col items-center justify-center gap-2 w-full lg:w-48">
            <AnilloConcentracion pct={pctTop3} color={color} />
            <p className="text-xs text-ink-3 text-center leading-snug">
              {traducir("concentran los primeros {n}", { n: Math.min(3, filas.length) })}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
