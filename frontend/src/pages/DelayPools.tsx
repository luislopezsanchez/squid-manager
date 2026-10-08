import { traducir } from '../i18n'
import { useState, useEffect, useMemo } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useSugerenciasUsuarios } from '../hooks/useSugerenciasUsuarios'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import RequiereAplicar from '../components/RequiereAplicar'
import Modal from '../components/Modal'
import { confirmar } from '../components/ConfirmDialog'
import {
  IconTag, IconActivity, IconUsers, IconGroups, IconGlobe, IconEdit, IconTrash, IconClose, IconGauge,
} from '../components/Icons'

interface Objetivo { kind: 'acl' | 'user' | 'group' | 'tipo' | 'all'; value: string; acl?: string }

interface DelayPool {
  id: number
  pool_class: number
  parameters: string
  acl_name: string | null
  description: string | null
  enabled: boolean
  targets: Objetivo[] | null
  download_bps: number | null
  shared: boolean
  gestionado: boolean
}

interface Acl { id: number; name: string; type: string; value: string | null; is_category: boolean; display_name: string | null }
interface Preset { clave: string; etiqueta: string; descripcion: string }

// Unidades de velocidad: se guarda siempre en bytes por segundo.
const UNIDADES = [
  { value: 1024, label: 'KB/s' },
  { value: 1048576, label: 'MB/s' },
  { value: 125000, label: 'Mbit/s' },
]

function formatVelocidad(bps: number): string {
  if (bps >= 1048576) { const v = bps / 1048576; return `${Number.isInteger(v) ? v : v.toFixed(1)} MB/s` }
  if (bps >= 1024) { const v = bps / 1024; return `${Number.isInteger(v) ? v : v.toFixed(1)} KB/s` }
  return `${bps} B/s`
}

// El número que importa de una regla antigua: el último par «restauración/límite».
function limiteAntiguo(pool: DelayPool): number {
  const partes = pool.parameters.trim().split(/\s+/)
  const [, limite] = (partes[partes.length - 1] || '0/0').split('/')
  return parseInt(limite) || 0
}

const CATEGORIAS: { id: Objetivo['kind']; etiqueta: string; ayuda: string; Icon: (p: { className?: string }) => JSX.Element }[] = [
  { id: 'acl', etiqueta: 'ACLs y categorías', ayuda: 'Dominios, redes, categorías (redes sociales, streaming…) y cualquier ACL que hayas creado.', Icon: IconTag },
  { id: 'tipo', etiqueta: 'Tipo de tráfico', ayuda: 'Vídeo, audio, descargas grandes o documentos, sin escribir expresiones regulares.', Icon: IconActivity },
  { id: 'user', etiqueta: 'Usuarios', ayuda: 'Una o varias cuentas concretas (locales o LDAP).', Icon: IconUsers },
  { id: 'group', etiqueta: 'Grupos', ayuda: 'Todos los miembros de uno o varios grupos.', Icon: IconGroups },
  { id: 'all', etiqueta: 'Todo el tráfico', ayuda: 'Aplica a cualquier persona y sitio.', Icon: IconGlobe },
]

const clave = (o: { kind: string; value: string }) => `${o.kind}:${o.value}`

export default function DelayPools() {
  const [pools, setPools] = useState<DelayPool[]>([])
  const [acls, setAcls] = useState<Acl[]>([])
  const [groups, setGroups] = useState<string[]>([])
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [search, setSearch] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [nombre, setNombre] = useState('')
  const [seleccion, setSeleccion] = useState<Objetivo[]>([])
  const [categoria, setCategoria] = useState<Objetivo['kind']>('acl')
  const [filtro, setFiltro] = useState('')
  const [velocidad, setVelocidad] = useState(512)
  const [unidad, setUnidad] = useState(1024)
  const [compartido, setCompartido] = useState(true)
  const [activa, setActiva] = useState(true)
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  // Regla antigua con forma que el editor nuevo no puede representar (clases 3-5, ráfagas distintas…).
  const [tecnica, setTecnica] = useState<DelayPool | null>(null)

  const { showToast, ToastContainer } = useToast()

  const loadPools = () => {
    api.listDelayPools().then(r => { setPools(r); setLoadError(false) })
      .catch(() => { showToast(traducir("Error al cargar reglas de ancho de banda"), 'error'); setLoadError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPools()
    api.listAcls().then(setAcls).catch(() => {})
    api.listGroups().then(g => setGroups(g.map((x: any) => x.name))).catch(() => {})
    api.getDelayPoolPresets().then(setPresets).catch(() => {})
  }, [])

  // ACLs propias del mecanismo (usuario/tipo de tráfico) no se ofrecen como «ACL»: ya
  // salen como Usuarios y Tipo de tráfico, y mostrarlas dos veces confundiría.
  const aclsElegibles = useMemo(
    () => acls.filter(a => !a.name.startsWith('bw_') && !a.name.startsWith('cuota_')),
    [acls],
  )

  // Usuarios: se buscan en el servidor según lo que se escribe en el filtro (máx. 50), no se descargan todos.
  const { nombres: usuarios, hayMas: hayMasUsuarios } = useSugerenciasUsuarios(filtro, categoria === 'user')

  const opciones = useMemo(() => {
    const q = filtro.trim().toLowerCase()
    const lista: { value: string; label: string; detalle?: string }[] =
      categoria === 'acl' ? aclsElegibles.map(a => ({ value: a.name, label: a.display_name || a.name, detalle: a.display_name ? a.name : a.type }))
      : categoria === 'tipo' ? presets.map(p => ({ value: p.clave, label: traducir(p.etiqueta), detalle: traducir(p.descripcion) }))
      : categoria === 'user' ? usuarios.map(u => ({ value: u, label: u }))
      : categoria === 'group' ? groups.map(g => ({ value: g, label: g }))
      : []
    return q && categoria !== 'user' ? lista.filter(o => `${o.label} ${o.detalle ?? ''}`.toLowerCase().includes(q)) : lista
  }, [categoria, aclsElegibles, presets, usuarios, groups, filtro])

  const estaElegido = (kind: string, value: string) => seleccion.some(o => o.kind === kind && o.value === value)
  const alternar = (kind: Objetivo['kind'], value: string) =>
    setSeleccion(prev => {
      if (kind === 'all') return prev.some(o => o.kind === 'all') ? prev.filter(o => o.kind !== 'all') : [{ kind: 'all', value: '' }]
      const sinTodo = prev.filter(o => o.kind !== 'all')
      return sinTodo.some(o => o.kind === kind && o.value === value)
        ? sinTodo.filter(o => !(o.kind === kind && o.value === value))
        : [...sinTodo, { kind, value }]
    })
  const cuenta = (kind: string) => seleccion.filter(o => o.kind === kind).length

  const etiquetaObjetivo = (o: Objetivo): string => {
    if (o.kind === 'all') return traducir('Todo el tráfico')
    if (o.kind === 'tipo') { const p = presets.find(x => x.clave === o.value); return p ? traducir(p.etiqueta) : o.value }
    if (o.kind === 'acl') { const a = acls.find(x => x.name === o.value); return a?.display_name || o.value }
    return o.value
  }
  const iconoDe = (kind: string) => CATEGORIAS.find(c => c.id === kind)?.Icon ?? IconTag

  const resetForm = () => {
    setEditingId(null); setNombre(''); setSeleccion([]); setCategoria('acl'); setFiltro('')
    setVelocidad(512); setUnidad(1024); setCompartido(true); setActiva(true); setError(''); setTecnica(null)
  }

  const abrirNueva = () => { resetForm(); setShowForm(true) }

  // Reglas antiguas: se intenta representarlas con el editor nuevo. Si su forma no
  // encaja (varios niveles con valores distintos, clases 3-5), se editan en técnico.
  const abrirEdicion = (p: DelayPool) => {
    resetForm()
    setEditingId(p.id); setNombre(p.description || ''); setActiva(p.enabled)
    if (p.targets) {
      setSeleccion(p.targets.map(t => ({ kind: t.kind, value: t.value })))
      const bps = p.download_bps || 0
      const u = bps >= 1048576 && bps % 1048576 === 0 ? 1048576 : 1024
      setUnidad(u); setVelocidad(Math.round((bps / u) * 100) / 100); setCompartido(p.shared)
    } else {
      const partes = p.parameters.trim().split(/\s+/).map(x => x.split('/'))
      const plana1 = p.pool_class === 1 && partes.length === 1 && partes[0][0] === partes[0][1]
      const plana2 = p.pool_class === 2 && partes.length === 2 && partes[1][0] === partes[1][1]
      if (!plana1 && !plana2) { setTecnica(p); setShowForm(true); return }
      const bps = limiteAntiguo(p)
      const u = bps >= 1048576 && bps % 1048576 === 0 ? 1048576 : 1024
      setUnidad(u); setVelocidad(Math.round((bps / u) * 100) / 100); setCompartido(plana1)
      if (!p.acl_name) setSeleccion([{ kind: 'all', value: '' }])
      else if (groups.includes(p.acl_name)) setSeleccion([{ kind: 'group', value: p.acl_name }])
      else setSeleccion([{ kind: 'acl', value: p.acl_name }])
    }
    setShowForm(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (tecnica) {
      setGuardando(true)
      try {
        await api.updateDelayPool(tecnica.id, { description: nombre, enabled: activa })
        notificarCambioPendiente(); loadPools(); setShowForm(false); resetForm()
        showToast(traducir("Regla actualizada"))
      } catch (err: any) { setError(err.message) } finally { setGuardando(false) }
      return
    }
    if (seleccion.length === 0) { setError(traducir("Elige a qué aplica la regla: pulsa alguno de los iconos.")); return }
    if (!(velocidad > 0)) { setError(traducir("Indica una velocidad mayor que cero.")); return }
    const datos = {
      description: nombre, enabled: activa, shared: compartido,
      targets: seleccion.map(o => ({ kind: o.kind, value: o.value })),
      download_bps: Math.round(velocidad * unidad),
    }
    setGuardando(true)
    try {
      if (editingId) await api.updateDelayPool(editingId, datos)
      else await api.createDelayPool(datos)
      notificarCambioPendiente(); loadPools(); setShowForm(false); resetForm()
      showToast(editingId ? traducir("Regla actualizada") : traducir("Regla creada"))
    } catch (err: any) {
      setError(err.message); showToast(`Error: ${err.message}`, 'error')
    } finally { setGuardando(false) }
  }

  const handleDelete = async (p: DelayPool) => {
    if (!(await confirmar(traducir("¿Eliminar la regla de ancho de banda «{n}»?", { n: p.description || `#${p.id}` })))) return
    try {
      await api.deleteDelayPool(p.id)
      notificarCambioPendiente(); loadPools()
      showToast(traducir("Regla eliminada correctamente"))
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const handleToggle = async (p: DelayPool) => {
    try {
      await api.updateDelayPool(p.id, { enabled: !p.enabled })
      notificarCambioPendiente(); loadPools()
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  // «Aplica a» de la tabla: chips con lo que elegiste (o la ACL de una regla antigua).
  const objetivosDe = (p: DelayPool): Objetivo[] =>
    p.targets ?? (!p.acl_name ? [{ kind: 'all', value: '' }]
      : groups.includes(p.acl_name) ? [{ kind: 'group', value: p.acl_name }] : [{ kind: 'acl', value: p.acl_name }])

  const term = search.trim().toLowerCase()
  const visibles = term
    ? pools.filter(p => (p.description ?? '').toLowerCase().includes(term) || objetivosDe(p).some(o => etiquetaObjetivo(o).toLowerCase().includes(term)))
    : pools

  const catActual = CATEGORIAS.find(c => c.id === categoria)!

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Ancho de banda")}</h1>
          <p className="page-sub">{traducir("Reglas de velocidad máxima por usuario, grupo, dominio o tipo de tráfico")}</p>
        </div>
        <button onClick={abrirNueva} className="btn btn-primary">{traducir('+ Nueva regla')}</button>
      </div>

      <div className="note note-info mb-6">
        <p className="note-text">
          {traducir("Limita la velocidad de descarga: lo que el servidor le manda al usuario. Squid no puede limitar la velocidad de subida ni reservar ancho de banda para nadie (solo pone techos); eso se hace con el control de tráfico del sistema operativo.")}
        </p>
      </div>

      {showForm && (
        <Modal title={editingId ? traducir('Editar regla') : traducir('Nueva regla')} onClose={() => { resetForm(); setShowForm(false) }} maxWidth="max-w-2xl">
          <form onSubmit={handleSave}>
            <div className="mb-4">
              <label htmlFor="dp-name" className="field-label block mb-1.5">{traducir("Nombre de la regla")}</label>
              <input id="dp-name" type="text" value={nombre} onChange={e => setNombre(e.target.value)}
                placeholder={traducir("ej: Límite para invitados")} className="input" required autoFocus />
            </div>

            {tecnica ? (
              <div className="note note-warn mb-4">
                <p className="note-text">{traducir("Esta regla usa una configuración que el editor simple no puede representar (por red, por tag, o velocidades de ráfaga distintas al límite). Aquí solo puedes cambiar el nombre y si está activa.")}</p>
                <p className="note-text font-mono mt-1">{`class ${tecnica.pool_class} · ${tecnica.parameters}`}</p>
              </div>
            ) : (
              <>
                <div className="mb-4">
                  <div className="field-label mb-2">{traducir("Aplica a")} <span className="font-normal text-ink-3">— {traducir("puedes combinar varios")}</span></div>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                    {CATEGORIAS.map(c => {
                      const n = c.id === 'all' ? (cuenta('all') ? 1 : 0) : cuenta(c.id)
                      const activo = categoria === c.id
                      return (
                        <button key={c.id} type="button" onClick={() => { setCategoria(c.id); setFiltro('') }}
                          className={`relative flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center transition
                            ${activo ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-line hover:bg-brand-50/60 text-ink-2'}`}>
                          <c.Icon className="w-6 h-6" />
                          <span className="text-[12px] font-medium leading-tight">{traducir(c.etiqueta)}</span>
                          {n > 0 && <span className="absolute -top-1.5 -right-1.5 min-w-[20px] h-5 px-1 rounded-full bg-brand-600 text-white text-[11px] font-bold grid place-items-center">{n}</span>}
                        </button>
                      )
                    })}
                  </div>

                  <div className="mt-3 border border-line-soft rounded-xl p-3">
                    <p className="text-[12px] text-ink-3 mb-2">{traducir(catActual.ayuda)}</p>
                    {categoria === 'all' ? (
                      <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
                        <input type="checkbox" checked={estaElegido('all', '')} onChange={() => alternar('all', '')} />
                        {traducir("Aplicar a todo el tráfico de todos los usuarios")}
                      </label>
                    ) : (
                      <>
                        <input type="text" value={filtro} onChange={e => setFiltro(e.target.value)} className="input mb-2"
                          placeholder={traducir("Buscar…")} />
                        <div className="max-h-44 overflow-y-auto divide-y divide-line-soft">
                          {opciones.map(o => (
                            <label key={o.value} className="flex items-center gap-2.5 py-1.5 px-1 text-sm cursor-pointer hover:bg-brand-50/60 rounded">
                              <input type="checkbox" checked={estaElegido(categoria, o.value)} onChange={() => alternar(categoria, o.value)} />
                              <span className="text-ink-2">{o.label}</span>
                              {o.detalle && <span className="text-[11.5px] text-ink-3 truncate">{o.detalle}</span>}
                            </label>
                          ))}
                          {categoria === 'user' && hayMasUsuarios && (
                            <p className="text-[12.5px] text-ink-3 py-2 text-center">{traducir("Se muestran los primeros 50: escribe para afinar la búsqueda.")}</p>
                          )}
                          {opciones.length === 0 && <p className="text-[13px] text-ink-3 py-3 text-center">{traducir("No hay nada que elegir aquí todavía.")}</p>}
                        </div>
                      </>
                    )}
                  </div>

                  {seleccion.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {seleccion.map(o => {
                        const I = iconoDe(o.kind)
                        return (
                          <span key={clave(o)} className="inline-flex items-center gap-1.5 bg-brand-50 text-brand-700 pl-2 pr-1 py-1 rounded-full text-xs font-medium">
                            <I className="w-3.5 h-3.5" />{etiquetaObjetivo(o)}
                            <button type="button" onClick={() => alternar(o.kind, o.value)} aria-label={traducir("Quitar")}
                              className="w-4 h-4 rounded-full hover:bg-brand-600 hover:text-white grid place-items-center"><IconClose className="w-3 h-3" /></button>
                          </span>
                        )
                      })}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label htmlFor="dp-speed" className="field-label block mb-1.5">{traducir("Velocidad máxima de descarga")}</label>
                    <div className="flex gap-2">
                      <input id="dp-speed" type="number" min={0.01} step="any" value={velocidad}
                        onChange={e => setVelocidad(parseFloat(e.target.value) || 0)} className="input flex-1" required />
                      <select value={unidad} onChange={e => setUnidad(parseInt(e.target.value))} className="input w-28">
                        {UNIDADES.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
                      </select>
                    </div>
                    <p className="field-help mt-1">{traducir("1 MB/s equivale a unos 8 Mbit/s.")}</p>
                  </div>
                  <div>
                    <div className="field-label mb-1.5">{traducir("¿Cómo se aplica el límite?")}</div>
                    <label className="flex items-start gap-2 text-sm text-ink-2 cursor-pointer mb-2">
                      <input type="radio" className="mt-1" checked={compartido} onChange={() => setCompartido(true)} />
                      <span>{traducir("Un límite total: todo lo elegido comparte esta velocidad")}
                        <span className="block text-[11.5px] text-ink-3">{traducir("Ej.: con {v}, si 10 personas navegan a la vez, se reparten esos {v} entre todas.", { v: `${velocidad} ${UNIDADES.find(u => u.value === unidad)?.label ?? ''}` })}</span>
                      </span>
                    </label>
                    <label className="flex items-start gap-2 text-sm text-ink-2 cursor-pointer">
                      <input type="radio" className="mt-1" checked={!compartido} onChange={() => setCompartido(false)} />
                      <span>{traducir("Un límite por dispositivo: cada computadora o teléfono (dirección IP) desde el que se navegue con lo elegido recibe este límite por separado")}
                        <span className="block text-[11.5px] text-ink-3">{traducir("Ej.: con {v}, si 3 equipos descargan a la vez, cada uno recibe hasta {v}.", { v: `${velocidad} ${UNIDADES.find(u => u.value === unidad)?.label ?? ''}` })}</span>
                      </span>
                    </label>
                  </div>
                </div>
              </>
            )}

            <label className="flex items-center gap-2 text-sm text-ink-2 mb-4">
              <input type="checkbox" checked={activa} onChange={e => setActiva(e.target.checked)} />
              {traducir("Activa")}
            </label>

            {error && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <button type="submit" className="btn btn-primary" disabled={guardando}>
                  {guardando ? traducir("Guardando…") : editingId ? traducir('Guardar Cambios') : traducir('Crear regla')}
                </button>
                <button type="button" onClick={() => { resetForm(); setShowForm(false) }} className="btn btn-outline">{traducir("Cancelar")}</button>
              </div>
              <RequiereAplicar />
            </div>
          </form>
        </Modal>
      )}

      <div className="mb-4">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder={traducir("Buscar por nombre o a quién aplica…")} className="input w-full sm:max-w-sm" />
      </div>

      {loading ? (
        <LoadingState />
      ) : loadError && pools.length === 0 ? (
        <ErrorState onRetry={loadPools} />
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left">{traducir("Nombre")}</th>
                <th className="text-left">{traducir("Aplica a")}</th>
                <th className="text-left">{traducir("Límite")}</th>
                <th className="text-left">{traducir("Estado")}</th>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {visibles.map(p => {
                const objs = objetivosDe(p)
                const bps = p.targets ? (p.download_bps || 0) : limiteAntiguo(p)
                return (
                  <tr key={p.id} className={!p.enabled ? 'opacity-50' : ''}>
                    <td className="px-5 py-3 font-medium text-ink">
                      {p.description || traducir("(sin nombre)")}
                      {p.gestionado && <span className="block text-[11px] font-normal text-ink-3">{traducir("Creada automáticamente por una cuota")}</span>}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex flex-wrap gap-1 max-w-[320px]">
                        {objs.slice(0, 3).map(o => {
                          const I = iconoDe(o.kind)
                          return <span key={clave(o)} className="inline-flex items-center gap-1 bg-line-soft text-ink-2 px-2 py-0.5 rounded-full text-xs"><I className="w-3 h-3" />{etiquetaObjetivo(o)}</span>
                        })}
                        {objs.length > 3 && <span className="text-xs text-ink-3 self-center" title={objs.slice(3).map(etiquetaObjetivo).join(', ')}>+{objs.length - 3}</span>}
                      </div>
                    </td>
                    <td className="px-5 py-3 tabular">
                      <span className="inline-flex items-center gap-1.5"><IconGauge className="w-3.5 h-3.5 text-ink-3" />{formatVelocidad(bps)}</span>
                      <span className="block text-[11px] text-ink-3">{p.targets ? (p.shared ? traducir("límite total") : traducir("por dispositivo")) : (p.pool_class === 2 ? traducir("por dispositivo") : traducir("límite total"))}</span>
                    </td>
                    <td className="px-5 py-3">
                      <button onClick={() => handleToggle(p)} title={p.enabled ? traducir("Clic para desactivar") : traducir("Clic para activar")}
                        className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${p.enabled ? 'pill-ok' : 'pill-danger'}`}>
                        {p.enabled ? traducir('Activo') : traducir('Inactivo')}
                      </button>
                    </td>
                    <td className="px-5 py-3 text-right whitespace-nowrap">
                      <button onClick={() => abrirEdicion(p)} className="btn-icon" title={traducir("Editar")}><IconEdit /></button>
                      <button onClick={() => handleDelete(p)} className="btn-icon btn-icon-danger" title={traducir("Eliminar")}><IconTrash /></button>
                    </td>
                  </tr>
                )
              })}
              {visibles.length === 0 && (
                <tr><td colSpan={5} className="px-5 py-12 text-center text-ink-3">
                  {pools.length === 0 ? traducir("No hay reglas de ancho de banda configuradas.") : traducir("Ninguna regla coincide con la búsqueda.")}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
