import { traducir } from '../i18n'
import { useState, useEffect, useRef, Component } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { formatRate, formatNumber, formatBytes } from '../utils/format'
import { IconRefresh, IconEdit, IconTrash, IconGlobe, IconUpload, IconClose, IconBan, IconLink, IconInfo, IconAlert } from '../components/Icons'
import { LoadingState, ErrorState } from '../components/AsyncState'

// "squidmanager" (otra instancia con login) o "squid_basico" (Squid puro,
// sin panel -se lee su Cache Manager directo). Ver MonitoredNode.tipo.
type TipoNodo = 'squidmanager' | 'squid_basico'

interface FormNodo {
  name: string
  tipo: TipoNodo
  url: string
  username: string
  password: string
  enabled: boolean
}

interface Node {
  id: number
  name: string
  tipo: TipoNodo
  url: string
  // null en un nodo squid_basico: no tiene cuenta que guardar.
  username: string | null
  password: string | null
  enabled: boolean
}

interface NodeStatus {
  // null solo en la raíz (este servidor): no es un MonitoredNode de la
  // tabla, no tiene fila propia que editar/borrar ni endpoint de detalle.
  id: number | null
  name: string
  tipo?: TipoNodo
  url: string | null
  instance_id?: string | null
  squid_port?: string | null
  status: 'ok' | 'error'
  message?: string
  // Árbol real (no solo un nivel): cada nodo remoto ya trae SUS propios
  // hijos, resueltos del lado de ESE servidor -ver
  // central_monitor_service.consultar_arbol. Vacío, nunca undefined: así
  // el render recursivo no necesita `?? []` en cada punto de uso.
  children: NodeStatus[]
  data?: {
    // Ausentes en un nodo squid_basico: no hay base de datos ni logs de
    // SquidManager de los que sacar tráfico en tiempo real ni usuarios
    // activos -un Squid puro no lleva esa cuenta.
    traffic?: {
      total_bytes_per_second: number
      active_ips: string[]
      active_users: string[]
      denied_requests_60s: number
    }
    system?: {
      cpu: { percent: number }
      memory: { percent: number }
    }
    // Sale del Cache Manager REAL de Squid (mgr:info), no de la API de
    // SquidManager -null si Squid no responde, sea cual sea el motivo.
    // Es la única forma de distinguir "el panel de SquidManager está
    // arriba" de "Squid, el proxy de verdad, también lo está". En un nodo
    // squid_basico es la fuente PRINCIPAL de datos, no un extra.
    squid_uptime?: number | null
    // Solo presentes en un nodo squid_basico -ver consultar_nodo_basico.
    squid_version?: string | null
    clientes_conectados?: number | null
  }
}

interface NodoDetalle {
  id: number
  name: string
  status: 'ok' | 'error'
  message?: string
  top_users: { user: string; bytes: number; requests: number }[] | null
  top_domains: { domain: string; requests: number; bytes: number }[] | null
  connections: { time: string; user: string; domain: string; status: number; bytes: number; denied: boolean }[] | null
}

/** Ícono ℹ con explicación al pasar el mouse o al hacer clic (clic para que
 *  funcione igual de bien en pantallas táctiles, donde no hay "hover"). Se
 *  cierra solo al perder el foco -clic en cualquier otro lado de la
 *  página. `anclaje` decide de qué lado del ícono cuelga el globo: "right"
 *  (default, el ícono queda a la derecha de lo que explica) o "left" (el
 *  ícono queda a la IZQUIERDA de lo que explica, como en la tarjeta de un
 *  nodo -angosta, w-60- donde colgar el globo hacia la izquierda lo
 *  sacaría del lienzo). `ancho` angosta el globo para espacios chicos,
 *  como esa misma tarjeta. */
function InfoTipCentral({ children, anclaje = 'right', ancho }: {
  children: React.ReactNode
  anclaje?: 'left' | 'right'
  ancho?: { min: number; max: number }
}) {
  const [abierto, setAbierto] = useState(false)
  const min = ancho?.min ?? 260
  const max = ancho?.max ?? 360
  return (
    <span className="relative inline-flex items-center group">
      <button
        type="button"
        // stopPropagation: este ícono puede vivir DENTRO de un <label> que
        // envuelve un checkbox (uno por interruptor, en el banner de
        // Monitoreo Centralizado) -sin esto, el clic para abrir el
        // tooltip también le llegaría al <label> y tildaría/destildaría
        // el checkbox sin querer.
        onClick={e => { e.stopPropagation(); setAbierto(a => !a) }}
        onBlur={() => setAbierto(false)}
        title={traducir("Más información")}
        className="flex items-center justify-center text-ink-3 opacity-60 hover:opacity-100 cursor-help"
      >
        <IconInfo className="w-4 h-4" />
      </button>
      <span className={`absolute ${anclaje === 'left' ? 'left-0' : 'right-0'} top-full mt-1.5 ${abierto ? 'block' : 'hidden group-hover:block'}
                       bg-brand-900 text-white text-xs px-3 py-2 rounded-lg
                       whitespace-normal shadow-lg z-30 pointer-events-none`}
            style={{ maxWidth: `${max}px`, minWidth: `${min}px` }}>
        {children}
      </span>
    </span>
  )
}

function hostPuertoDe(nodo: NodeStatus): string | null {
  if (!nodo.url) return null
  try {
    const u = new URL(nodo.url)
    // squid_port es el puerto que otro SquidManager reportó para SU Squid;
    // un nodo squid_basico no lo tiene (no hay panel que lo reporte), pero
    // su propia `url` YA es host:puerto de Squid, así que el puerto de la
    // URL alcanza.
    const puerto = nodo.squid_port || u.port
    return puerto ? `${u.hostname}:${puerto}` : u.hostname
  } catch {
    return null
  }
}

function TarjetaNodo({ nodo, esRaiz, nivel, ruta, onVerMas }: {
  nodo: NodeStatus; esRaiz: boolean
  // Nivel calculado en el momento, según la profundidad de ESTE recorrido
  // -nunca guardado en ningún lado, ver docs/project-log.md: el mismo nodo
  // puede ser "nivel 1" visto desde su propio panel y "nivel 2" visto desde
  // el de su padre, no hay un número fijo que asignarle de antemano.
  nivel: number
  // Ids desde el hijo DIRECTO de este servidor hasta este nodo (un hijo
  // directo es una ruta de un solo elemento) -lo que necesita el backend
  // para pedir el detalle de un nieto/bisnieto sin tener sus credenciales:
  // cada salto resuelve un id con las suyas y reenvía el resto. Ver
  // GET /central/nodes/detalle-por-ruta.
  ruta: number[]
  onVerMas: (n: NodeStatus, ruta: number[]) => void
}) {
  const enLinea = nodo.status === 'ok'
  // "En línea" antes solo significaba "el backend de SquidManager respondió
  // al login" -no que Squid, el proxy de verdad, estuviera corriendo ahí.
  // squid_uptime sale del Cache Manager REAL de Squid (no de la API), y da
  // null exactamente cuando Squid no responde -sin importar que el panel
  // de SquidManager siga arriba y conteste perfecto. Bug real, reportado
  // en vivo 2026-09-26: un Squid detenido a propósito seguía viéndose "En
  // línea" en el árbol.
  //
  // OJO: un nodo remoto con una versión vieja de SquidManager (de antes de
  // que existiera este campo) tampoco manda la clave "squid_uptime" -ahí
  // "in" da false. Eso NO es "Squid caído", es "no lo sabemos" -no hay que
  // confundir "no tengo el dato" con "el dato vino null". Reportado en vivo
  // 2026-09-26 contra el .116 (versión vieja, Squid corriendo de verdad).
  const dashboardSoportaSquidUptime = enLinea && !!nodo.data && 'squid_uptime' in nodo.data
  const squidActivo = enLinea && (!dashboardSoportaSquidUptime || nodo.data?.squid_uptime != null)
  const squidCaido = enLinea && dashboardSoportaSquidUptime && !squidActivo
  const hostPuerto = hostPuertoDe(nodo)
  // Un Squid puro no tiene tráfico en tiempo real ni usuarios activos que
  // mostrar -eso sale de la base de datos y los logs de SquidManager, que
  // acá no hay. Se muestra en cambio lo que SÍ sale del propio Squid: su
  // versión y cuántos clientes tiene conectados ahora mismo.
  const esBasico = nodo.tipo === 'squid_basico'
  return (
    <div className={`card p-4 text-left w-60 relative ${
      squidCaido ? 'bg-warn-soft' : enLinea ? 'bg-ok-soft' : 'bg-danger-soft'
    } ${
      esRaiz ? 'border-brand-500 border-2' : squidCaido ? 'border-warn/30' : enLinea ? '' : 'border-rose-200'
    }`}>
      {esRaiz && (
        <span className="absolute -top-2.5 left-3.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-brand-700 text-white">
          {traducir("Este servidor")}
        </span>
      )}
      <div className="flex items-center justify-between gap-2 mb-1">
        <h3 className="font-medium text-ink flex items-center gap-1.5 min-w-0">
          <IconGlobe className="w-4 h-4 text-ink-3 flex-none" />
          <span className="truncate" title={nodo.name}>{nodo.name}</span>
        </h3>
        <span className={`flex-none ${squidCaido ? 'pill-warn' : enLinea ? 'pill-ok' : 'pill-danger'}`}>
          {squidCaido ? traducir("Squid caído") : enLinea ? traducir("En línea") : traducir("Sin conexión")}
        </span>
      </div>
      <p className="text-[10px] font-bold uppercase tracking-wide text-ink-3 mb-2 flex items-center flex-wrap gap-1">
        <span>{traducir("Nivel {n}", { n: String(nivel) })}{esRaiz ? ` (${traducir("este panel")})` : ''}</span>
        {esBasico && <span className="pill-mute normal-case tracking-normal">{traducir("Squid básico")}</span>}
        {/* Ícono + tooltip en vez de un párrafo largo adentro de la tarjeta
            -el texto completo (versión/uptime no disponibles, la ACL es
            opcional) deformaba el alto de todas las tarjetas del árbol por
            igual, ancladas a la misma fila. Pedido en vivo, 2026-09-26. */}
        {esBasico && enLinea && nodo.message && (
          <InfoTipCentral anclaje="left" ancho={{ min: 220, max: 280 }}>
            <p className="normal-case tracking-normal font-normal">{nodo.message}</p>
          </InfoTipCentral>
        )}
      </p>
      {hostPuerto && <p className="text-xs text-ink-3 font-mono mb-2 truncate">{hostPuerto}</p>}
      {enLinea && nodo.data ? (
        // Mismo grid, mismas clases, en los dos casos -incluido `truncate`
        // en cada etiqueta y valor: una tarjeta de squid_basico con un
        // rótulo más largo ("Clientes conectados") NO puede terminar más
        // alta que sus vecinas por eso -todas las tarjetas del árbol están
        // ancladas a la misma fila. Bug real, reportado en vivo,
        // 2026-09-27: el texto se cortaba a dos líneas y agrandaba la
        // tarjeta entera.
        esBasico ? (
          <div className="grid grid-cols-2 gap-2 text-sm mb-1">
            <div className="min-w-0">
              <p className="text-ink-3 text-xs truncate">{traducir("Versión")}</p>
              <p className="font-medium truncate">{nodo.data.squid_version || '—'}</p>
            </div>
            <div className="min-w-0">
              <p className="text-ink-3 text-xs truncate">{traducir("Clientes")}</p>
              <p className="font-medium truncate">{nodo.data.clientes_conectados != null ? formatNumber(nodo.data.clientes_conectados) : '—'}</p>
            </div>
          </div>
        ) : (
          // OJO: nada de "!" (non-null assertion) acá -eso solo calla a
          // TypeScript, no protege en tiempo de ejecución. `data.traffic`
          // puede faltar en un nodo etiquetado "squidmanager" si ESE nodo
          // remoto corre una versión vieja/incompatible que devuelve otra
          // forma de dashboard -exactamente lo que pasó en vivo,
          // 2026-09-27, al monitorear en espejo dos SquidManager entre sí
          // (cada uno viendo al otro como nodo): uno de los dos corría un
          // build tan viejo que ni siquiera tenía Monitoreo Centralizado,
          // y el "traffic" que faltaba tumbaba TODA la página con una
          // excepción sin capturar. Un problema de UN nodo nunca debería
          // poder tumbar la vista de todos los demás -por eso ?? en vez de
          // asumir que siempre está.
          <div className="grid grid-cols-2 gap-2 text-sm mb-1">
            <div className="min-w-0">
              <p className="text-ink-3 text-xs truncate">{traducir("Tráfico actual")}</p>
              <p className="font-medium truncate">{nodo.data.traffic ? formatRate(nodo.data.traffic.total_bytes_per_second) : '—'}</p>
            </div>
            <div className="min-w-0">
              <p className="text-ink-3 text-xs truncate">{traducir("Usuarios activos")}</p>
              <p className="font-medium truncate">{nodo.data.traffic ? formatNumber(nodo.data.traffic.active_users.length) : '—'}</p>
            </div>
          </div>
        )
      ) : (
        <p className="text-xs text-rose-700 mb-1">{nodo.message}</p>
      )}
      {squidCaido && (
        <p className="text-xs text-amber-800 mb-1">
          {traducir("El panel de SquidManager responde, pero Squid (el proxy) no -su Cache Manager no contestó.")}
        </p>
      )}
      {!esRaiz && (
        <div className="mt-2 pt-2 border-t border-line-soft text-right">
          <button onClick={() => onVerMas(nodo, ruta)} className="text-xs font-medium text-brand-700 hover:underline">
            {traducir("Ver más")} →
          </button>
        </div>
      )}
    </div>
  )
}

function ArbolNodo({ nodo, esRaiz, nivel, ruta, onVerMas }: {
  nodo: NodeStatus; esRaiz: boolean; nivel: number; ruta: number[]
  onVerMas: (n: NodeStatus, ruta: number[]) => void
}) {
  return (
    <li>
      <TarjetaNodo nodo={nodo} esRaiz={esRaiz} nivel={nivel} ruta={ruta} onVerMas={onVerMas} />
      {nodo.children.length > 0 && (
        <ul>
          {nodo.children.map((hijo, i) => (
            <ArbolNodo
              key={hijo.id ?? `${hijo.name}-${i}`}
              nodo={hijo} esRaiz={false} nivel={nivel + 1}
              ruta={hijo.id !== null ? [...ruta, hijo.id] : ruta}
              onVerMas={onVerMas}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

const ZOOM_MINIMO = 0.25
const ZOOM_MAXIMO = 2
const PASO_ZOOM_RUEDA = 0.0015
const PASO_ZOOM_BOTON = 0.15

// Viewport de tamaño FIJO (nunca crece, nunca scrollea) para el árbol -antes,
// si el árbol crecía a lo ancho aparecía una barra de scroll horizontal
// dentro de la tarjeta (y una vertical si además crecía en niveles),
// molesto en una laptop de resolución estándar. En vez de eso, el árbol se
// reescala para entrar completo apenas cambia (loadEstado trae un árbol
// nuevo, o la ventana cambia de tamaño), y el usuario puede acercar con la
// rueda del mouse -centrado en el cursor, como Figma/Google Maps, no en el
// centro de la pantalla- y arrastrar para moverse mientras está acercado.
// Pedido en vivo, 2026-09-26.
/** Red de seguridad para el árbol: si CUALQUIER nodo del árbol -el propio
 *  o un remoto anidado varios niveles adentro- trae datos con una forma
 *  inesperada y algo revienta al dibujarlo, esto lo atrapa ahí mismo en
 *  vez de dejar que la excepción suba y tumbe la página ENTERA en blanco
 *  -que es justo lo que le pasó a un nodo remoto viejo/incompatible
 *  (visto en vivo, 2026-09-27, monitoreando dos SquidManager entre sí:
 *  uno de los dos corría una versión sin Monitoreo Centralizado, y su
 *  "dashboard" le faltaba un campo que el otro daba por garantizado).
 *  Un componente de clase porque los error boundaries de React todavía
 *  no tienen equivalente en hooks. */
class ArbolErrorBoundary extends Component<{ children: ReactNode; onReintentar: () => void }, { rompio: boolean }> {
  state = { rompio: false }

  static getDerivedStateFromError() {
    return { rompio: true }
  }

  componentDidCatch(error: unknown) {
    console.error('Monitoreo Centralizado: error al dibujar el árbol', error)
  }

  render() {
    if (this.state.rompio) {
      return (
        <div className="p-8 text-center">
          <p className="text-sm text-ink-3 mb-3">
            {traducir("No se pudo dibujar el árbol -probablemente un nodo remoto devolvió datos con un formato inesperado. El resto de la página (nodos configurados, configuración) sigue funcionando normalmente.")}
          </p>
          <button
            onClick={() => { this.setState({ rompio: false }); this.props.onReintentar() }}
            className="btn btn-outline"
          >
            {traducir("Reintentar")}
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function ArbolConZoom({ children, dependenciaAjuste }: { children: React.ReactNode; dependenciaAjuste: unknown }) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const contenidoRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const arrastreRef = useRef({ activo: false, x: 0, y: 0, panX: 0, panY: 0 })

  const ajustarAPantalla = () => {
    const viewport = viewportRef.current
    const contenido = contenidoRef.current
    if (!viewport || !contenido) return
    // offsetWidth/Height del contenido son su tamaño de LAYOUT, que
    // transform: scale no altera (solo cambia lo pintado) -por eso se puede
    // medir así sin importar el zoom que ya esté aplicado.
    const anchoNatural = contenido.offsetWidth
    const altoNatural = contenido.offsetHeight
    if (anchoNatural === 0 || altoNatural === 0) return
    // Nunca se agranda solo porque sobra espacio (tope en 1): un árbol
    // chico se ve a tamaño real, no estirado.
    const escala = Math.min(1, viewport.clientWidth / anchoNatural, viewport.clientHeight / altoNatural)
    setZoom(escala)
    setPan({
      x: (viewport.clientWidth - anchoNatural * escala) / 2,
      y: (viewport.clientHeight - altoNatural * escala) / 2,
    })
  }

  useEffect(() => {
    ajustarAPantalla()
    window.addEventListener('resize', ajustarAPantalla)
    return () => window.removeEventListener('resize', ajustarAPantalla)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dependenciaAjuste])

  // Se mantiene siempre al día con el zoom actual, sin depender del cierre
  // (closure) de una función vieja -hace falta porque el listener de la
  // rueda se engancha UNA sola vez (ver más abajo) y necesita leer el
  // último valor real en cada evento, no el que existía cuando se creó.
  const zoomRef = useRef(zoom)
  useEffect(() => { zoomRef.current = zoom }, [zoom])

  const zoomHacia = (nuevoZoomSinTope: number, puntoX: number, puntoY: number) => {
    const zoomActual = zoomRef.current
    const nuevoZoom = Math.min(ZOOM_MAXIMO, Math.max(ZOOM_MINIMO, nuevoZoomSinTope))
    const razon = nuevoZoom / zoomActual
    setPan(p => ({ x: puntoX - (puntoX - p.x) * razon, y: puntoY - (puntoY - p.y) * razon }))
    setZoom(nuevoZoom)
    zoomRef.current = nuevoZoom
  }

  // Enganchado a mano con addEventListener (no con la prop onWheel de
  // React): React adjunta wheel como passive por defecto, así que
  // e.preventDefault() ahí NO hace nada de verdad -el navegador igual
  // aplica su propio zoom de página con Ctrl+rueda, aunque el handler de
  // React se ejecute. Bug real, reportado en vivo 2026-09-26: acercaba el
  // navegador entero en vez de solo el lienzo (en la emulación de
  // dispositivo móvil de las herramientas de desarrollo no se nota, porque
  // ese camino de evento es distinto). Con { passive: false } acá si se
  // puede frenar el zoom nativo de verdad.
  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return
    const onWheelNativo = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      const rect = viewport.getBoundingClientRect()
      zoomHacia(zoomRef.current * (1 - e.deltaY * PASO_ZOOM_RUEDA), e.clientX - rect.left, e.clientY - rect.top)
    }
    viewport.addEventListener('wheel', onWheelNativo, { passive: false })
    return () => viewport.removeEventListener('wheel', onWheelNativo)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const zoomBoton = (delta: number) => {
    const viewport = viewportRef.current
    if (!viewport) return
    zoomHacia(zoomRef.current + delta, viewport.clientWidth / 2, viewport.clientHeight / 2)
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    arrastreRef.current = { activo: true, x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y }
  }

  // A nivel window, no del viewport: arrastrar y sacar el cursor un
  // momento del lienzo (fácil, el viewport mide apenas 440px de alto) no
  // debe cortar el movimiento -mismo criterio que Google Maps, donde
  // arrastrar sigue funcionando aunque el cursor se salga del mapa
  // mientras el botón sigue apretado. Antes se escuchaba mousemove/mouseup
  // solo sobre el viewport (con onMouseLeave cortando el arrastre apenas
  // el cursor salía), y el arrastre se sentía roto -bug real, reportado en
  // vivo 2026-09-26.
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!arrastreRef.current.activo) return
      const a = arrastreRef.current
      setPan({ x: a.panX + (e.clientX - a.x), y: a.panY + (e.clientY - a.y) })
    }
    const onUp = () => { arrastreRef.current.activo = false }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  return (
    <div className="relative">
      <div
        ref={viewportRef}
        className="relative h-[620px] overflow-hidden rounded-lg bg-ground/60 cursor-grab active:cursor-grabbing select-none"
        onMouseDown={handleMouseDown}
      >
        <div
          ref={contenidoRef}
          className="absolute top-0 left-0 inline-block"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: '0 0' }}
        >
          {children}
        </div>
      </div>
      <span className="absolute bottom-2 left-2 text-[11px] text-ink-3 bg-white/80 backdrop-blur rounded px-1.5 py-0.5">
        {traducir("Ctrl + rueda para acercar · clic y arrastrar para mover")}
      </span>
      <div className="absolute bottom-2 right-2 flex items-center gap-0.5 bg-white/95 backdrop-blur rounded-lg border border-line-soft shadow-sm px-1 py-1">
        <button type="button" onClick={() => zoomBoton(-PASO_ZOOM_BOTON)} className="btn-icon w-7 h-7 text-base" title={traducir("Alejar")}>−</button>
        <span className="text-xs text-ink-3 w-11 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => zoomBoton(PASO_ZOOM_BOTON)} className="btn-icon w-7 h-7 text-base" title={traducir("Acercar")}>+</button>
        <button type="button" onClick={ajustarAPantalla} className="btn-icon text-xs px-2 w-auto" title={traducir("Ajustar a la pantalla")}>
          {traducir("Ajustar")}
        </button>
      </div>
    </div>
  )
}

function BarraProporcion({ etiqueta, valor, maximo, color }: { etiqueta: string; valor: string; maximo: number; color: string }) {
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="truncate" title={etiqueta}>{etiqueta}</span>
        <b className="flex-none ml-2">{valor}</b>
      </div>
      <div className="h-1.5 rounded-full bg-line-soft overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${Math.max(maximo, 1)}%`, background: color }} />
      </div>
    </div>
  )
}

function ModalDetalleNodo({ nodo, ruta, onClose }: { nodo: NodeStatus; ruta: number[]; onClose: () => void }) {
  const [detalle, setDetalle] = useState<NodoDetalle | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (ruta.length === 0) return
    setCargando(true)
    setError(false)
    api.getCentralNodeDetallePorRuta(ruta)
      .then(r => {
        if (r.status !== 'ok') setError(true)
        setDetalle(r)
      })
      .catch(() => setError(true))
      .finally(() => setCargando(false))
  }, [ruta.join(',')])

  const maxBytesUsuarios = detalle?.top_users?.length ? Math.max(...detalle.top_users.map(u => u.bytes), 1) : 1
  const maxReqDominios = detalle?.top_domains?.length ? Math.max(...detalle.top_domains.map(d => d.requests), 1) : 1
  const hostPuerto = hostPuertoDe(nodo)

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-lg overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line-soft flex-none">
          <div className="flex items-center gap-2 min-w-0">
            <h2 className="text-lg font-bold text-ink truncate">{nodo.name}</h2>
            <span className={nodo.status === 'ok' ? 'pill-ok flex-none' : 'pill-danger flex-none'}>
              {nodo.status === 'ok' ? traducir("En línea") : traducir("Sin conexión")}
            </span>
          </div>
          <button onClick={onClose} aria-label={traducir("Cerrar")}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-ink-3 hover:bg-line-soft hover:text-ink transition flex-none">
            <IconClose className="w-4 h-4" />
          </button>
        </div>
        {hostPuerto && <p className="px-6 pt-3 text-xs text-ink-3 font-mono">{hostPuerto}</p>}
        {!cargando && !error && detalle?.message && (
          <p className="px-6 pt-3 text-xs text-ink-3">{detalle.message}</p>
        )}

        {cargando ? (
          <p className="text-sm text-ink-3 text-center py-12">{traducir("Cargando...")}</p>
        ) : error && !detalle?.top_users && !detalle?.top_domains && !detalle?.connections ? (
          <p className="text-sm text-rose-700 text-center py-12">
            {detalle?.message || traducir("No se pudo obtener el detalle de este nodo.")}
          </p>
        ) : (
          <div className="px-6 py-4 overflow-y-auto">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-5">
              <div>
                <h3 className="text-xs font-bold text-ink uppercase mb-2">{traducir("Top usuarios")}</h3>
                {detalle?.top_users?.length ? (
                  <div className="flex flex-col gap-2">
                    {detalle.top_users.map(u => (
                      <BarraProporcion key={u.user} etiqueta={u.user} valor={formatBytes(u.bytes)}
                        maximo={(u.bytes / maxBytesUsuarios) * 100} color="var(--brand-400)" />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-ink-3">{traducir("Sin datos todavía.")}</p>
                )}
              </div>
              <div>
                <h3 className="text-xs font-bold text-ink uppercase mb-2">{traducir("Top sitios visitados")}</h3>
                {detalle?.top_domains?.length ? (
                  <div className="flex flex-col gap-2">
                    {detalle.top_domains.map(d => (
                      <BarraProporcion key={d.domain} etiqueta={d.domain} valor={traducir("{n} peticiones", { n: formatNumber(d.requests) })}
                        maximo={(d.requests / maxReqDominios) * 100} color="var(--brand-500)" />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-ink-3">{traducir("Sin datos todavía.")}</p>
                )}
              </div>
            </div>

            <h3 className="text-xs font-bold text-ink uppercase mb-2">{traducir("Últimas conexiones")}</h3>
            {detalle?.connections?.length ? (
              <table className="table-panel">
                <thead className="bg-brand-50 border-b border-line-soft">
                  <tr>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Hora")}</th>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Usuario")}</th>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Dominio")}</th>
                    <th className="text-left px-3 py-1.5 text-xs font-medium text-ink-3 uppercase">{traducir("Estado")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {detalle.connections.map((c, i) => (
                    <tr key={i} className={c.denied ? 'bg-red-50/40' : ''}>
                      <td className="px-3 py-1.5 text-xs text-ink-3 font-mono whitespace-nowrap">{c.time}</td>
                      <td className="px-3 py-1.5 text-xs font-medium truncate max-w-[140px]" title={c.user}>{c.user}</td>
                      <td className="px-3 py-1.5 text-xs font-mono text-ink-2 truncate max-w-[220px]" title={c.domain}>{c.domain}</td>
                      <td className="px-3 py-1.5 text-xs">
                        <span className={c.denied ? 'pill-danger' : 'pill-ok'}>{c.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-xs text-ink-3">{traducir("Sin datos todavía.")}</p>
            )}

            <p className="text-xs text-ink-3 mt-4">
              {traducir("Estos datos se piden aparte, bajo demanda, con la misma cuenta guardada para este nodo -el backend hace de intermediario, la contraseña del nodo remoto nunca llega al navegador.")}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// Modal para agregar/editar un nodo -antes era un <form> siempre visible
// dentro de "Nodos configurados", que le robaba espacio a la página incluso
// cerrado (el botón "Cancelar"/"+ Agregar nodo" quedaba lejos del lienzo del
// árbol). Ahora vive en un modal, disparado desde un botón al lado de
// "Actualizar" -mismo lugar donde ya se refresca el árbol- y "Nodos
// configurados" queda solo como la lista. Pedido en vivo, 2026-09-26.
function ModalFormNodo({ form, setForm, editingId, testing, testResult, onTest, onSave, onClose }: {
  form: FormNodo
  setForm: (f: FormNodo) => void
  editingId: number | null
  testing: boolean
  testResult: { status: string; message?: string; monitoreo_centralizado_remoto?: boolean | null } | null
  onTest: () => void
  onSave: (e: React.FormEvent) => void
  onClose: () => void
}) {
  const esBasicoForm = form.tipo === 'squid_basico'
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-lg overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line-soft flex-none">
          <h2 className="text-lg font-bold text-ink">
            {editingId !== null ? traducir("Editar nodo") : traducir("Agregar nodo")}
          </h2>
          <button onClick={onClose} aria-label={traducir("Cerrar")}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-ink-3 hover:bg-line-soft hover:text-ink transition flex-none">
            <IconClose className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={onSave} className="px-6 py-4 overflow-y-auto">
          <div className="mb-4">
            <label className="field-label block mb-1.5">{traducir("Tipo de nodo")}</label>
            <div className="flex flex-col sm:flex-row gap-2">
              <label className={`flex-1 flex items-start gap-2 border rounded-lg px-3 py-2 cursor-pointer ${!esBasicoForm ? 'border-brand-500 bg-brand-50' : 'border-line-soft'}`}>
                <input type="radio" name="node-tipo" className="mt-1" checked={!esBasicoForm}
                  onChange={() => setForm({ ...form, tipo: 'squidmanager' })} />
                <span>
                  <span className="block text-sm font-medium text-ink">{traducir("SquidManager")}</span>
                  <span className="block text-xs text-ink-3">{traducir("Otra instancia de este panel, con usuario y contraseña propios.")}</span>
                </span>
              </label>
              <label className={`flex-1 flex items-start gap-2 border rounded-lg px-3 py-2 cursor-pointer ${esBasicoForm ? 'border-brand-500 bg-brand-50' : 'border-line-soft'}`}>
                <input type="radio" name="node-tipo" className="mt-1" checked={esBasicoForm}
                  onChange={() => setForm({ ...form, tipo: 'squid_basico' })} />
                <span>
                  <span className="block text-sm font-medium text-ink">{traducir("Squid básico")}</span>
                  <span className="block text-xs text-ink-3">{traducir("Un Squid sin SquidManager, sin cuenta -se lee su Cache Manager directo.")}</span>
                </span>
              </label>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="node-name" className="field-label block mb-1.5">{traducir("Nombre")}</label>
              <input id="node-name" type="text" value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                className="input" placeholder={traducir("ej: Sucursal Norte")} required />
            </div>
            <div>
              <label htmlFor="node-url" className="field-label block mb-1.5">
                {esBasicoForm ? traducir("Dirección de Squid") : traducir("URL del panel remoto")}
              </label>
              <input id="node-url" type="text" value={form.url}
                onChange={e => setForm({ ...form, url: e.target.value })}
                className="input font-mono text-sm" placeholder={esBasicoForm ? "http://10.0.0.9:3128" : "https://10.0.0.5:8443"} required />
              {esBasicoForm && <p className="field-help mt-1">{traducir("Host y puerto donde escucha Squid -no un panel.")}</p>}
            </div>
            {!esBasicoForm && (
              <>
                <div>
                  <label htmlFor="node-username" className="field-label block mb-1.5">{traducir("Usuario")}</label>
                  <input id="node-username" type="text" value={form.username}
                    onChange={e => setForm({ ...form, username: e.target.value })}
                    className="input" required={!esBasicoForm} />
                  <p className="field-help mt-1">{traducir("Recomendado: una cuenta con rol \"Solo lectura\" dedicada a esto en el nodo remoto.")}</p>
                </div>
                <div>
                  <label htmlFor="node-password" className="field-label block mb-1.5">{traducir("Contraseña")}</label>
                  <input id="node-password" type="password" value={form.password}
                    onChange={e => setForm({ ...form, password: e.target.value })}
                    className="input" placeholder={editingId !== null ? traducir("Dejar en blanco para no cambiarla") : ''}
                    required={editingId === null} />
                </div>
              </>
            )}
          </div>

          <label className="flex items-center gap-2 mt-4 cursor-pointer">
            <input type="checkbox" checked={form.enabled} onChange={e => setForm({ ...form, enabled: e.target.checked })} />
            {traducir("Habilitado")}
          </label>

          <div className="flex items-center gap-3 mt-4">
            <button type="button" onClick={onTest} disabled={testing} className="btn btn-outline">
              {testing ? traducir("Probando...") : traducir("Probar conexión")}
            </button>
            <button type="submit" className="btn btn-primary">
              {editingId !== null ? traducir("Guardar cambios") : traducir("Agregar nodo")}
            </button>
          </div>

          {testResult && (
            <div className={`mt-4 note ${
              testResult.status !== 'ok' ? 'note-danger'
                : testResult.monitoreo_centralizado_remoto === false ? 'note-warn'
                  : 'note-ok'
            }`}>
              <p className="note-text">
                {testResult.status !== 'ok'
                  ? testResult.message
                  : testResult.monitoreo_centralizado_remoto === false
                    ? traducir("Conexión exitosa, pero el monitoreo centralizado está deshabilitado en ese nodo: va a aparecer «Sin conexión» en el árbol hasta que lo actives allá (Monitoreo centralizado → Habilitar).")
                    : traducir("Conexión exitosa: el nodo respondió correctamente.")}
              </p>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}

const FORM_VACIO: FormNodo = { name: '', tipo: 'squidmanager', url: '', username: '', password: '', enabled: true }

export default function PanelCentral() {
  const [config, setConfig] = useState<{ enabled: boolean; monitorizar_hijos: boolean; instance_id: string } | null>(null)
  const [savingConfig, setSavingConfig] = useState(false)
  const [nodes, setNodes] = useState<Node[]>([])
  const [raiz, setRaiz] = useState<NodeStatus | null>(null)
  const [loadingEstado, setLoadingEstado] = useState(true)
  const [estadoError, setEstadoError] = useState(false)
  const [ultimaActualizacion, setUltimaActualizacion] = useState<Date | null>(null)
  const [nodoDetalle, setNodoDetalle] = useState<{ nodo: NodeStatus; ruta: number[] } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState(FORM_VACIO)
  const [testing, setTesting] = useState(false)
  const [syncingId, setSyncingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ status: string; message?: string; monitoreo_centralizado_remoto?: boolean | null } | null>(null)
  // Transiciones de estado ("nodo caído"/"nodo recuperado") ya notificadas
  // por email/Telegram si esos canales están configurados -ver
  // node_alert_service.py. No depende de que esta pestaña esté abierta en
  // el momento en que pasó -el chequeo lo hace un hilo de fondo en el
  // backend cada un minuto, esto solo muestra lo que ya detectó.
  const [alertas, setAlertas] = useState<{ ts: number; node_name: string; estado: string; mensaje: string }[]>([])
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { showToast, ToastContainer } = useToast()

  const loadConfig = () => {
    api.getCentralConfig().then(setConfig).catch(() => showToast(traducir("Error al cargar la configuración"), 'error'))
  }

  const handleToggleEnabled = async (checked: boolean) => {
    setSavingConfig(true)
    try {
      const nuevo = await api.updateCentralConfig(checked, config?.monitorizar_hijos ?? true)
      setConfig(nuevo)
      if (checked) { loadNodes(); loadEstado() }
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    } finally {
      setSavingConfig(false)
    }
  }

  const handleToggleMonitorizarHijos = async (checked: boolean) => {
    if (!config) return
    setSavingConfig(true)
    try {
      const nuevo = await api.updateCentralConfig(config.enabled, checked)
      setConfig(nuevo)
      loadEstado()
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    } finally {
      setSavingConfig(false)
    }
  }

  const loadNodes = () => {
    api.listCentralNodes().then(setNodes).catch(() => showToast(traducir("Error al cargar los nodos"), 'error'))
  }

  const loadEstado = () => {
    // self + children tal cual los arma el backend (ya es un árbol real,
    // cada hijo con los suyos propios) -ver central_monitor_service.
    // consultar_arbol_de_todos. Nada se aplana acá.
    api.getCentralDashboard()
      .then(r => {
        setRaiz({
          id: null,
          name: r.self.name,
          tipo: 'squidmanager',
          url: null,
          instance_id: r.self.instance_id,
          squid_port: r.self.squid_port,
          status: r.self.status,
          data: r.self.data,
          children: r.children,
        })
        setUltimaActualizacion(new Date())
        setEstadoError(false)
      })
      .catch(() => { showToast(traducir("Error al consultar el estado de los nodos"), 'error'); setEstadoError(true) })
      .finally(() => setLoadingEstado(false))
  }

  useEffect(() => {
    loadConfig()
  }, [])

  const loadAlertas = () => {
    api.getCentralAlertasRecientes(24, 5).then(setAlertas).catch(() => {})
  }

  useEffect(() => {
    if (!config?.enabled) return
    loadNodes()
    loadEstado()
    loadAlertas()
    // Cada nodo implica un login + un dashboard completo contra otra
    // instancia -no tiene sentido repetirlo cada pocos segundos como el
    // dashboard local, que solo lee de su propio proceso.
    intervalRef.current = setInterval(() => { loadEstado(); loadAlertas() }, 30000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [config?.enabled])

  // "Cerrar" el aviso de alertas de nodos no debería esconderlo para
  // siempre -solo hasta la más nueva que ya viste. Guardado en
  // localStorage (por navegador, no por servidor -ver la guía de
  // artifact-capabilities sobre no usarlo para nada que necesite
  // compartirse o sobrevivir de forma confiable, que acá no aplica: es
  // pura conveniencia de "ya lo vi"), comparado contra el timestamp de la
  // alerta más nueva: si aparece una transición nueva después de cerrarlo,
  // vuelve a mostrarse solo. Pedido en vivo, 2026-09-27.
  const CLAVE_ALERTAS_VISTAS = 'panelCentral.alertasVistasHasta'
  const [alertaCerrada, setAlertaCerrada] = useState(false)

  useEffect(() => {
    if (alertas.length === 0) return
    try {
      const vistoHasta = Number(localStorage.getItem(CLAVE_ALERTAS_VISTAS) || 0)
      setAlertaCerrada(alertas[0].ts <= vistoHasta)
    } catch {
      setAlertaCerrada(false)
    }
  }, [alertas])

  const cerrarAlertaNodos = () => {
    setAlertaCerrada(true)
    try { localStorage.setItem(CLAVE_ALERTAS_VISTAS, String(alertas[0]?.ts ?? Date.now() / 1000)) } catch { /* per-viewer only, sin problema si falla */ }
  }

  const resetForm = () => {
    setForm(FORM_VACIO)
    setEditingId(null)
    setTestResult(null)
  }

  const handleEdit = (node: Node) => {
    setForm({ name: node.name, tipo: node.tipo, url: node.url, username: node.username ?? '', password: '', enabled: node.enabled })
    setEditingId(node.id)
    setTestResult(null)
    setShowForm(true)
  }

  const esBasicoForm = form.tipo === 'squid_basico'

  const handleTest = async () => {
    if (!form.url || (!esBasicoForm && (!form.username || (!form.password && editingId === null)))) {
      showToast(traducir("Completa URL, usuario y contraseña para probar la conexión"), 'error')
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const password = form.password || '***'
      const resultado = await api.testCentralNode({
        tipo: form.tipo, url: form.url, username: esBasicoForm ? undefined : form.username, password: esBasicoForm ? undefined : password,
        // Si la contraseña no se reescribió (queda "***"), esto le permite
        // al backend resolverla contra la guardada de este nodo -sin esto,
        // probar un nodo existente sin tocar la contraseña mandaba el
        // placeholder literal y la prueba fallaba siempre.
        id: editingId ?? undefined,
      })
      setTestResult(resultado)
    } catch (e: any) {
      setTestResult({ status: 'error', message: e.message })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingId !== null) {
        const data: any = { name: form.name, tipo: form.tipo, url: form.url, enabled: form.enabled }
        if (!esBasicoForm) {
          data.username = form.username
          if (form.password) data.password = form.password
        }
        await api.updateCentralNode(editingId, data)
        showToast(traducir("Nodo actualizado"))
      } else {
        await api.createCentralNode(form)
        showToast(traducir("Nodo agregado"))
      }
      resetForm()
      setShowForm(false)
      loadNodes()
      loadEstado()
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    }
  }

  const handleDelete = async (node: Node) => {
    if (!confirm(traducir('¿Eliminar el nodo "{n}"?', { n: node.name }))) return
    try {
      await api.deleteCentralNode(node.id)
      showToast(traducir("Nodo eliminado"))
      loadNodes()
      loadEstado()
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    }
  }

  const [togglingId, setTogglingId] = useState<number | null>(null)

  const handleToggleNodeEnabled = async (node: Node) => {
    // Pausar el monitoreo de un nodo puntual sin borrarlo -antes la única
    // forma de hacerlo era abrir "Editar" y destildar "Habilitado" ahí, sin
    // ninguna acción rápida en la fila misma. El campo `enabled` ya existía
    // y el árbol ya lo respeta (consultar_arbol_de_todos filtra por él);
    // solo faltaba esta acción en la UI -encontrado en vivo, 2026-09-26.
    setTogglingId(node.id)
    try {
      const nuevoEstado = !node.enabled
      await api.updateCentralNode(node.id, { enabled: nuevoEstado })
      showToast(nuevoEstado
        ? traducir('Nodo "{n}" reconectado', { n: node.name })
        : traducir('Nodo "{n}" desconectado', { n: node.name }))
      loadNodes()
      loadEstado()
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    } finally {
      setTogglingId(null)
    }
  }

  const handleSync = async (node: Node) => {
    if (!confirm(traducir(
      'Esto SOBRESCRIBE la configuración de "{n}" con la de este servidor (ACLs, reglas, usuarios, grupos, cuotas...). ¿Continuar?',
      { n: node.name },
    ))) return
    setSyncingId(node.id)
    try {
      const resultado = await api.syncCentralNode(node.id)
      if (resultado.status === 'ok') {
        showToast(traducir('Configuración sincronizada a "{n}"', { n: node.name }))
      } else {
        showToast(resultado.message, 'error')
      }
    } catch (e: any) {
      showToast(`${traducir("Error")}: ${e.message}`, 'error')
    } finally {
      setSyncingId(null)
    }
  }

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Monitoreo centralizado")}</h1>
          <p className="page-sub">{traducir("Métricas de este servidor y de otras instancias de SquidManager, en una sola vista")}</p>
        </div>
      </div>

      {/* Apagado por defecto, mismo patrón que LDAP: el interruptor arriba de
          todo, y el resto de la página (nodos, dashboard) recién aparece una
          vez habilitado -no es solo estético, el backend también rechaza esas
          rutas (listar/crear/editar/borrar nodos propios, probarlos,
          sincronizarlos) con 403 mientras esté apagado (ver
          _requerir_habilitado en routes/central.py). Esto es solo el lado
          SALIENTE -que otro SquidManager consulte a ESTE servidor como nodo
          nunca depende de este interruptor, ver el docstring de
          _requerir_habilitado.
          Antes esto era dos tarjetas verdes con párrafos de texto siempre
          visibles -le robaban altura al lienzo del árbol, que es lo que el
          usuario más quiere ver de un vistazo. Ahora es una barra angosta con
          los dos checkboxes en línea y el texto explicativo movido a un
          tooltip (ícono ℹ, hover o clic): la explicación sigue ahí para quien
          la necesite, pero no ocupa espacio permanente. Pedido en vivo,
          2026-09-26. */}
      <div className={`flex items-center gap-x-5 gap-y-1.5 flex-wrap rounded-lg px-4 py-2 mb-4 border text-sm ${config?.enabled ? 'bg-green-50 border-green-200' : 'bg-brand-50 border-line'}`}>
        <div className="flex items-center gap-2">
          <span className={`inline-flex h-2.5 w-2.5 rounded-full flex-none ${config?.enabled ? 'bg-ok' : 'bg-ink-3'}`} />
          <span className="font-medium text-ink whitespace-nowrap">
            {traducir('Monitoreo centralizado')}
          </span>
        </div>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={config?.enabled ?? false}
            disabled={!config || savingConfig}
            onChange={e => handleToggleEnabled(e.target.checked)}
          />
          <span className="text-ink-2 whitespace-nowrap">{traducir("Habilitar")}</span>
          <InfoTipCentral>
            <p>
              {traducir("Cada nodo se consulta con una cuenta propia del panel remoto (recomendado: un usuario con rol \"solo lectura\" dedicado a esto). No requiere ningún cambio en Squid ni que los nodos se conozcan entre sí. Mientras esté desactivado, no podés configurar ni consultar nodos propios desde acá -pero si OTRO SquidManager ya te tiene agregado como nodo a vos, te sigue viendo igual: dejarse monitorear nunca depende de este interruptor, solo de que esa cuenta sea válida.")}
            </p>
          </InfoTipCentral>
        </label>
        {config?.enabled && (
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={config?.monitorizar_hijos ?? true}
              disabled={savingConfig}
              onChange={e => handleToggleMonitorizarHijos(e.target.checked)}
            />
            <span className="text-ink-2 whitespace-nowrap">{traducir("Monitorizar mis propios nodos")}</span>
            <InfoTipCentral>
              <p>
                {traducir("Independiente de arriba: este servidor siempre puede seguir siendo visto por otro SquidManager que lo tenga como nodo, esté prendido o apagado \"Habilitar\". Desactivá esto solo si querés que sea un nodo sin hijos propios, sin perder los nodos que ya tengas configurados más abajo.")}
              </p>
            </InfoTipCentral>
          </label>
        )}
      </div>

      {config?.enabled && (
      <>
      {/* Aviso de alertas de nodos: lo mismo que ya se manda por
          email/Telegram si esos canales están configurados (ver
          node_alert_service.py), para que también se note acá sin
          depender de revisar el correo -ni de tener esta pestaña abierta
          en el momento en que pasó, a diferencia del estado en vivo del
          árbol de abajo. Pedido en vivo, 2026-09-27. */}
      {alertas.length > 0 && !alertaCerrada && (
        <div className="relative card p-4 mb-4 flex items-center gap-3 border"
             style={{ borderColor: 'var(--warn)', background: 'var(--warn-soft)' }}>
          <span
            className="absolute -top-2 left-3 px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase tracking-wide text-white whitespace-nowrap z-10"
            style={{ background: 'var(--warn)', boxShadow: '0 2px 6px -2px rgba(224,160,54,.6)' }}
          >
            {traducir("Alertas de nodos")}
          </span>
          <span className="flex-none" style={{ color: 'var(--warn)' }}>
            <IconAlert className="w-5 h-5" />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold" style={{ color: 'var(--warn)' }}>
              {alertas.length === 1
                ? traducir("1 cambio de estado detectado recientemente")
                : traducir("{n} cambios de estado detectados recientemente", { n: alertas.length })}
            </p>
            <p className="text-xs text-ink-2 truncate">
              {alertas[0].mensaje}
              {alertas.length > 1 && ` ${traducir("+ {n} más", { n: alertas.length - 1 })}`}
            </p>
          </div>
          <button onClick={cerrarAlertaNodos} aria-label={traducir("Cerrar")}
            className="w-7 h-7 flex-none flex items-center justify-center rounded-lg text-ink-3 hover:bg-black/5 transition">
            <IconClose className="w-4 h-4" />
          </button>
        </div>
      )}
      {loadingEstado ? (
        <LoadingState />
      ) : estadoError && !raiz ? (
        <ErrorState onRetry={loadEstado} />
      ) : raiz ? (
        <div className="card p-5 mb-8">
          <div className="flex items-start justify-between flex-wrap gap-2 mb-4">
            <div>
              <h2 className="text-sm font-bold text-ink">{traducir("Árbol de nodos")}</h2>
              <p className="text-xs text-ink-3 mt-0.5">
                {traducir("El nivel se calcula según qué panel estés mirando -nadie lo asigna a mano")}
              </p>
              {ultimaActualizacion && (
                <p className="text-xs text-ink-3 mt-0.5">
                  {traducir("Última actualización")}: {ultimaActualizacion.toLocaleTimeString()}
                </p>
              )}
            </div>
            {/* Adentro de la propia tarjeta del árbol, no en el encabezado de
                la página: antes había que scrollear hasta arriba de todo
                para refrescar -pedido en vivo, 2026-09-26. "+ Agregar nodo"
                se suma acá mismo por el mismo motivo (antes estaba junto a
                "Nodos configurados", lejos del lienzo) -pedido en vivo,
                2026-09-26. */}
            <div className="flex items-center gap-2 flex-none">
              <button onClick={() => { resetForm(); setShowForm(true) }} className="btn btn-primary flex items-center gap-2">
                {traducir('+ Agregar nodo')}
              </button>
              <button onClick={loadEstado} className="btn btn-outline flex items-center gap-2">
                <IconRefresh className="w-4 h-4" />
                {traducir("Actualizar")}
              </button>
            </div>
          </div>
          <ArbolErrorBoundary onReintentar={loadEstado}>
            <ArbolConZoom dependenciaAjuste={raiz}>
              {/* pt-3: le da a la insignia "Este servidor" (que sobresale del
                  borde de su tarjeta con -top-2.5) un margen real, contado
                  adentro de lo que ArbolConZoom mide para encuadrar el árbol
                  -sin esto, la insignia queda justo en el borde superior y el
                  viewport (overflow: hidden) se la recorta. */}
              <div className="flex justify-center px-4 pt-3">
                <ul className="tree">
                  <ArbolNodo nodo={raiz} esRaiz nivel={1} ruta={[]}
                    onVerMas={(nodo, ruta) => setNodoDetalle({ nodo, ruta })} />
                </ul>
              </div>
            </ArbolConZoom>
          </ArbolErrorBoundary>
        </div>
      ) : null}

      {nodoDetalle && (
        <ModalDetalleNodo nodo={nodoDetalle.nodo} ruta={nodoDetalle.ruta} onClose={() => setNodoDetalle(null)} />
      )}

      {showForm && (
        <ModalFormNodo
          form={form} setForm={setForm} editingId={editingId}
          testing={testing} testResult={testResult}
          onTest={handleTest} onSave={handleSave}
          onClose={() => setShowForm(false)}
        />
      )}

      <h2 className="text-lg font-medium text-ink mb-4">{traducir("Nodos configurados")}</h2>

      {nodes.length === 0 ? (
        <p className="text-ink-3 text-sm">{traducir("No hay nodos remotos configurados todavía.")}</p>
      ) : (
        <div className="card divide-y divide-line-soft">
          {nodes.map(node => (
            <div key={node.id} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium text-ink flex items-center gap-2">
                  {node.name}
                  <span className={node.enabled ? 'pill-ok' : 'pill-mute'}>
                    {node.enabled ? traducir("Habilitado") : traducir("Deshabilitado")}
                  </span>
                  {node.tipo === 'squid_basico' && <span className="pill-mute">{traducir("Squid básico")}</span>}
                </p>
                <p className="text-xs text-ink-3 font-mono">{node.url}{node.username ? ` · ${node.username}` : ''}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleToggleNodeEnabled(node)} disabled={togglingId === node.id}
                  className={`btn-icon ${node.enabled ? 'text-rose-600' : 'text-ok'}`}
                  title={node.enabled ? traducir("Desconectar (dejar de monitorear sin borrarlo)") : traducir("Reconectar")}>
                  {node.enabled ? <IconBan className="w-4 h-4" /> : <IconLink className="w-4 h-4" />}
                </button>
                {node.tipo !== 'squid_basico' && (
                  <button onClick={() => handleSync(node)} disabled={syncingId === node.id}
                    className="btn-icon" title={traducir("Sincronizar configuración a este nodo")}>
                    <IconUpload className="w-4 h-4" />
                  </button>
                )}
                <button onClick={() => handleEdit(node)} className="btn-icon" title={traducir("Editar")}>
                  <IconEdit className="w-4 h-4" />
                </button>
                <button onClick={() => handleDelete(node)} className="btn-icon text-rose-600" title={traducir("Eliminar")}>
                  <IconTrash className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      </>
      )}
    </div>
  )
}
