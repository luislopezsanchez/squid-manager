import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'

type FilaUsuario = { user: string; bytes: number; requests: number }
type FilaDominio = { domain: string; requests: number; bytes: number }
type FilaBloqueado = { user: string; blocked_requests: number; account_status: 'enabled' | 'disabled' | 'unknown' }
type RespuestaBloqueados = { users: FilaBloqueado[]; anonymous_blocked: number }

type Pestana = 'usuarios' | 'dominios' | 'bloqueados-dominio' | 'bloqueados-usuario'

const COLORES = {
  usuarios: '#0B497C',
  dominios: '#2E93BC',
  'bloqueados-dominio': '#C0392B',
  'bloqueados-usuario': '#C0392B',
} as const

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

export default function Top20() {
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

  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Top 20")}</h1>
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
    </div>
  )
}
