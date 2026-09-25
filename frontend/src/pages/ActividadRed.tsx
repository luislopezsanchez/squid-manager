import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api, getToken, type RangoFechas } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'
import { useToast } from '../components/Toast'
import { IconDownload } from '../components/Icons'
import { LoadingState, ErrorState } from '../components/AsyncState'
import {
  FilaBarra, AnilloConcentracion, ModalDetalle, SelectorVentana, VENTANAS,
  type FilaDetalle, type Ventana, type RangoFechasInput,
} from '../components/ReportWidgets'

type FilaUsuario = { user: string; bytes: number; requests: number }
type FilaDominio = { domain: string; requests: number; bytes: number }
type FilaBloqueado = { user: string; blocked_requests: number; account_status: 'enabled' | 'disabled' | 'unknown' }
type RespuestaBloqueados = { users: FilaBloqueado[]; anonymous_blocked: number }
type FilaIpCompartida = { ip: string; usuarios: string[]; requests: number }
type Totales = {
  usuarios: { count: number; bytes: number; requests: number }
  dominios: { count: number; requests: number; bytes: number }
  dominios_bloqueados: { count: number; requests: number }
  usuarios_bloqueados_requests: number
}

type Pestana = 'usuarios' | 'dominios' | 'bloqueados-dominio' | 'bloqueados-usuario' | 'ips-compartidas'

const COLORES: Record<Pestana, string> = {
  usuarios: '#0B497C',
  dominios: '#2E93BC',
  'bloqueados-dominio': '#C0392B',
  'bloqueados-usuario': '#C0392B',
  'ips-compartidas': '#E0A036',
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
  'ips-compartidas': traducir(
    "Direcciones IP desde las que navegó más de un usuario autenticado distinto. No es un veredicto -puede ser un equipo compartido de verdad (una sala, un kiosco)-, pero es una señal que vale la pena revisar: credenciales que circulan entre personas se ven así."
  ),
}

export default function ActividadRed() {
  const [pestana, setPestana] = useState<Pestana>('usuarios')
  const [ventana, setVentana] = useState<Ventana>('')
  const [rangoInput, setRangoInput] = useState<RangoFechasInput>({ desde: '', hasta: '' })
  const [porDatos, setPorDatos] = useState(true) // aplica a "usuarios" y "dominios"
  const [usuarios, setUsuarios] = useState<FilaUsuario[] | null>(null)
  const [dominios, setDominios] = useState<FilaDominio[] | null>(null)
  const [bloqueadosDominio, setBloqueadosDominio] = useState<FilaDominio[] | null>(null)
  const [bloqueadosUsuario, setBloqueadosUsuario] = useState<FilaBloqueado[] | null>(null)
  const [anonimosBloqueados, setAnonimosBloqueados] = useState(0)
  const [ipsCompartidas, setIpsCompartidas] = useState<FilaIpCompartida[] | null>(null)
  const [totales, setTotales] = useState<Totales | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [detalle, setDetalle] = useState<{ titulo: string; filas: FilaDetalle[]; cargando: boolean; tendenciaHref: string; filtro?: 'bloqueadas' } | null>(null)
  const [exportando, setExportando] = useState(false)
  const { showToast, ToastContainer } = useToast()

  // Rango libre: solo se arma (y solo reemplaza a la ventana relativa) una
  // vez que las DOS fechas están cargadas -mientras falte una, se sigue
  // viendo el comportamiento por defecto (últimas 1.000) en vez de mandar un
  // pedido con un extremo vacío. "hasta" toma el final del día elegido
  // (23:59:59), no su comienzo, para incluir ese día completo.
  const rango: RangoFechas | undefined = ventana === 'custom' && rangoInput.desde && rangoInput.hasta
    ? {
        desde: Math.floor(new Date(`${rangoInput.desde}T00:00:00`).getTime() / 1000),
        hasta: Math.floor(new Date(`${rangoInput.hasta}T23:59:59`).getTime() / 1000),
      }
    : undefined

  const cargar = () => {
    // "custom" es un valor interno del selector, no una ventana real del
    // backend (ver VENTANAS_SEGUNDOS): si todavía no hay rango válido, cae
    // al comportamiento de siempre (últimas 1.000) en vez de mandar
    // "ventana=custom", que el backend no reconoce.
    const v = ventana !== 'custom' ? (ventana || undefined) : undefined
    Promise.all([
      api.getTopUsers(10, v, porDatos ? 'bytes' : 'requests', rango),
      api.getTopDomains(10, false, v, porDatos ? 'bytes' : 'requests', rango),
      api.getTopDomains(10, true, v, undefined, rango),
      api.getTopBlockedUsers(10, v, rango),
      api.getTotalesActividad(v, rango),
      api.getIpsCompartidas(10, v, rango),
    ])
      .then(([u, d, bd, bu, t, ips]: [FilaUsuario[], FilaDominio[], FilaDominio[], RespuestaBloqueados, Totales, FilaIpCompartida[]]) => {
        setUsuarios(u)
        setDominios(d)
        setBloqueadosDominio(bd)
        setBloqueadosUsuario(bu.users)
        setAnonimosBloqueados(bu.anonymous_blocked)
        setTotales(t)
        setIpsCompartidas(ips)
        setError(null)
      })
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setLoading(true)
    cargar()
    const interval = setInterval(cargar, 30000)
    return () => clearInterval(interval)
    // porDatos entra a proposito: cambia que metrica ordena el top de
    // usuarios (bytes o peticiones), no solo que numero se muestra -ver
    // get_top_users en el backend. Sin refetch, el toggle mostraba el
    // mismo ranking (por bytes) con otro numero al lado, no un ranking
    // distinto de verdad -reportado en vivo por el usuario, 2026-09-12.
    // rangoInput.desde/hasta entran por lo mismo: cambiar el rango libre
    // debe refetchear, no solo re-renderizar con datos viejos.
  }, [ventana, porDatos, rangoInput.desde, rangoInput.hasta])

  const abrirDetalle = (opts: { user?: string; domain?: string }, titulo: string, soloBloqueadas = false) => {
    const tendenciaHref = opts.user
      ? `/reportes/tendencias?tipo=user&valor=${encodeURIComponent(opts.user)}`
      : `/reportes/tendencias?tipo=domain&valor=${encodeURIComponent(opts.domain || '')}`
    const filtro = soloBloqueadas ? 'bloqueadas' as const : undefined
    setDetalle({ titulo, filas: [], cargando: true, tendenciaHref, filtro })
    // El drill-down y el PDF no soportan todavía el rango libre (fuera de
    // alcance de esta pasada): con "custom" caen a "últimas 1.000" en vez de
    // mandar un "ventana=custom" que el backend no reconoce.
    api.getDetalle({
      ...opts, ventana: ventana !== 'custom' ? (ventana || undefined) : undefined,
      limit: 50, denied: soloBloqueadas,
    })
      .then((filas: FilaDetalle[]) => setDetalle({ titulo, filas, cargando: false, tendenciaHref, filtro }))
      .catch(() => setDetalle({ titulo, filas: [], cargando: false, tendenciaHref, filtro }))
  }

  const exportarPdf = () => {
    setExportando(true)
    const token = getToken()
    fetch(api.actividadExportPdfUrl(ventana !== 'custom' ? (ventana || undefined) : undefined), { headers: { Authorization: `Bearer ${token}` } })
      .then(r => {
        if (!r.ok) throw new Error('export failed')
        return r.blob()
      })
      .then(blob => {
        const u = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = u
        a.download = `actividad-red-${new Date().toISOString().slice(0, 19).replace(/:/g, '')}.pdf`
        a.click()
        URL.revokeObjectURL(u)
        showToast(traducir("PDF exportado"), 'success')
      })
      .catch(() => showToast(traducir("Error exportando el PDF"), 'error'))
      .finally(() => setExportando(false))
  }

  const PESTANAS: { id: Pestana; label: string }[] = [
    { id: 'usuarios', label: traducir("Usuarios") },
    { id: 'dominios', label: traducir("Sitios visitados") },
    { id: 'bloqueados-dominio', label: traducir("Sitios bloqueados") },
    { id: 'bloqueados-usuario', label: traducir("Usuarios con más bloqueos") },
    { id: 'ips-compartidas', label: traducir("IPs compartidas") },
  ]

  if (loading) return <LoadingState />
  // Si la primera carga falla del todo (nunca hubo `totales`), mostrar
  // tablas vacías + el banner rojo de abajo se leía como "no hay actividad",
  // no como "falló la carga". Si ya había datos de un ciclo anterior (esta
  // página se refresca sola cada 30s), el banner inline alcanza y no hace
  // falta tapar todo -ver más abajo.
  if (error && !totales) return <ErrorState text={error} onRetry={cargar} />

  const color = COLORES[pestana]

  let filas: { etiqueta: string; subEtiqueta?: string; valor: number; valorFormateado: string; onClick?: () => void }[] = []
  if (pestana === 'usuarios' && usuarios) {
    filas = usuarios.map(u => ({
      etiqueta: u.user,
      subEtiqueta: porDatos ? `${formatNumber(u.requests)} ${traducir("req")}` : formatBytes(u.bytes),
      valor: porDatos ? u.bytes : u.requests,
      valorFormateado: porDatos ? formatBytes(u.bytes) : `${formatNumber(u.requests)} ${traducir("req")}`,
      onClick: () => abrirDetalle({ user: u.user }, u.user),
    }))
  } else if (pestana === 'dominios' && dominios) {
    filas = dominios.map(d => ({
      etiqueta: d.domain,
      subEtiqueta: porDatos ? `${formatNumber(d.requests)} ${traducir("req")}` : formatBytes(d.bytes),
      valor: porDatos ? d.bytes : d.requests,
      valorFormateado: porDatos ? formatBytes(d.bytes) : formatNumber(d.requests),
      onClick: () => abrirDetalle({ domain: d.domain }, d.domain),
    }))
  } else if (pestana === 'bloqueados-dominio' && bloqueadosDominio) {
    filas = bloqueadosDominio.map(d => ({
      etiqueta: d.domain,
      valor: d.requests,
      valorFormateado: formatNumber(d.requests),
      // soloBloqueadas=true: este ranking es de bloqueos, así que el
      // detalle debe mostrar las peticiones bloqueadas a este dominio, no
      // las últimas N sin filtrar (que para un dominio con algo de tráfico
      // permitido mezclado eran casi todas 200 -reportado en vivo, 2026-09-25).
      onClick: () => abrirDetalle({ domain: d.domain }, d.domain, true),
    }))
  } else if (pestana === 'bloqueados-usuario' && bloqueadosUsuario) {
    filas = bloqueadosUsuario.map(b => ({
      // account_status distingue "la cuenta esta deshabilitada de verdad" de
      // "denegado por otra razon" (credenciales viejas, politica de grupo)
      // -no es lo mismo, ver la nota en metrics_service.get_top_blocked_users.
      etiqueta: b.account_status === 'disabled' ? `${b.user} (${traducir("deshabilitado")})` : b.user,
      valor: b.blocked_requests,
      valorFormateado: formatNumber(b.blocked_requests),
      onClick: () => abrirDetalle({ user: b.user }, b.user, true),
    }))
  }

  const maximo = Math.max(...filas.map(f => f.valor), 1)

  // Total REAL (todos los usuarios/dominios de la ventana, no solo el top
  // 10 visible) -antes se sumaban las filas mostradas, que subestimaba el
  // total apenas hubiera mas de 10 usuarios/dominios reales. Cada pestana
  // usa el total de la MISMA metrica que esta rankeando (ver
  // get_totales_actividad en el backend), para que el % del anillo sea
  // "cuanto de ese total concentran los primeros 3", no una comparacion
  // entre metricas distintas.
  let total = 0
  if (pestana === 'usuarios' && totales) {
    total = porDatos ? totales.usuarios.bytes : totales.usuarios.requests
  } else if (pestana === 'dominios' && totales) {
    total = porDatos ? totales.dominios.bytes : totales.dominios.requests
  } else if (pestana === 'bloqueados-dominio' && totales) {
    total = totales.dominios_bloqueados.requests
  } else if (pestana === 'bloqueados-usuario' && totales) {
    total = totales.usuarios_bloqueados_requests
  }

  const top3 = filas.slice(0, 3).reduce((acc, f) => acc + f.valor, 0)
  const pctTop3 = total > 0 ? (top3 / total) * 100 : 0
  const totalFormateado = (pestana === 'usuarios' || pestana === 'dominios') && porDatos ? formatBytes(total) : formatNumber(total)

  return (
    <div className="p-6 md:p-8">
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1 className="text-2xl font-bold text-ink">{traducir("Actividad de red")}</h1>
        <button onClick={exportarPdf} disabled={exportando}
          className="flex-none flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border border-line-soft text-ink-2 hover:bg-line-soft/60 disabled:opacity-50 transition">
          <IconDownload className="w-4 h-4" />
          {exportando ? traducir('Exportando…') : traducir('Exportar PDF')}
        </button>
      </div>
      <p className="text-sm text-ink-3 mb-6">
        {rango
          ? traducir("Filtrado del {desde} al {hasta} — se refresca solo, cada 30 s.", { desde: rangoInput.desde, hasta: rangoInput.hasta })
          : ventana && ventana !== 'custom'
          ? traducir("Filtrado por: {ventana} — se refresca solo, cada 30 s.", { ventana: VENTANAS.find(v => v.id === ventana)?.label || '' })
          : traducir("De las últimas 1.000 peticiones registradas — se refresca solo, cada 30 s.")}
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

        <div className="flex items-center gap-3">
          <SelectorVentana value={ventana} onChange={setVentana} rango={rangoInput} onRangoChange={setRangoInput} />

          {(pestana === 'usuarios' || pestana === 'dominios') && (
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
      </div>

      <p className="text-sm text-ink-2 mb-4 max-w-3xl">{EXPLICACIONES[pestana]}</p>

      {pestana === 'ips-compartidas' ? (
        // No entra en el modelo de "ranking con un solo número" que usan las
        // demás pestañas (FilaBarra + anillo de concentración): acá cada fila
        // es una IP con VARIOS usuarios, no un valor que se pueda comparar
        // contra un máximo. Lista propia, sin el anillo al costado.
        <div className="card p-5">
          {!ipsCompartidas || ipsCompartidas.length === 0 ? (
            <p className="text-sm text-ink-3 text-center py-8">{traducir("No se detectaron IPs con más de un usuario en esta ventana.")}</p>
          ) : (
            <div className="divide-y divide-line-soft">
              {ipsCompartidas.map((row, i) => (
                <div key={row.ip} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex items-start gap-3 min-w-0">
                    <span className="w-6 h-6 rounded-full text-xs flex items-center justify-center text-white flex-none mt-0.5" style={{ backgroundColor: color }}>{i + 1}</span>
                    <div className="min-w-0">
                      <p className="font-mono text-sm text-ink">{row.ip}</p>
                      <p className="text-xs text-ink-3 mt-0.5 truncate">{row.usuarios.join(', ')}</p>
                    </div>
                  </div>
                  <div className="text-right flex-none">
                    <p className="text-sm font-semibold tabular text-ink">
                      {traducir("{n} usuarios", { n: row.usuarios.length })}
                    </p>
                    <p className="text-xs text-ink-3 tabular">{formatNumber(row.requests)} {traducir("req")}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
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
                    subEtiqueta={f.subEtiqueta}
                    valor={f.valor}
                    valorFormateado={f.valorFormateado}
                    maximo={maximo}
                    color={color}
                    onClick={f.onClick}
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
            <div className="card p-5 flex flex-col items-center justify-center gap-3 w-full lg:w-64">
              <AnilloConcentracion pct={pctTop3} color={color} total={total} totalFormateado={totalFormateado} />
            </div>
          )}
        </div>
      )}

      {detalle && (
        <ModalDetalle
          titulo={detalle.titulo}
          filas={detalle.filas}
          cargando={detalle.cargando}
          onClose={() => setDetalle(null)}
          tendenciaHref={detalle.tendenciaHref}
          filtro={detalle.filtro}
        />
      )}

      <ToastContainer />
    </div>
  )
}
