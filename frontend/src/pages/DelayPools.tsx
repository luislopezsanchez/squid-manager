import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import RequiereAplicar from '../components/RequiereAplicar'
import { normalizarNombreAcl } from '../utils/aclNames'

interface DelayPool {
  id: number
  pool_class: number
  parameters: string
  acl_name: string | null
  description: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

interface Acl {
  id: number
  name: string
  type: string
  value: string | null
  is_category: boolean
  display_name: string | null
}

interface Group {
  id: number
  name: string
  description: string | null
  members: string[]
}

interface ProxyUser {
  id: number
  username: string
  enabled: boolean
}

const UNITS = [
  { value: 1, label: traducir("bytes/s") },
  { value: 1024, label: traducir("KB/s") },
  { value: 1048576, label: traducir("MB/s") },
]

// Bucket "sin límite práctico" para la parte agregada de un grupo cuando
// cada integrante tiene su propio tope (clase 2 de Squid: aggregate +
// individual): el número que de verdad le importa al admin es el
// individual -el agregado solo existe porque el formato de Squid lo pide,
// así que se fija muy alto para que nunca sea la restricción real.
const AGREGADO_SIN_LIMITE = 1073741824 // 1 GB/s

function formatSpeed(bytes: number): string {
  if (bytes >= 1048576) {
    const mb = bytes / 1048576
    return `${Number.isInteger(mb) ? mb : mb.toFixed(1)} MB/s`
  }
  if (bytes >= 1024) {
    const kb = bytes / 1024
    return `${Number.isInteger(kb) ? kb : kb.toFixed(1)} KB/s`
  }
  return `${bytes} bytes/s`
}

// Formato de Squid para una regla simple: siempre restauración == límite
// (un único número, sin distinguir ráfaga de velocidad sostenida) -eso es
// lo que la mayoría de los admins espera de "limitar a X KB/s", y evita
// pedir dos valores por nivel para el caso común.
function buildSimpleParameters(poolClass: number, speedBytes: number): string {
  if (poolClass === 2) {
    return `${AGREGADO_SIN_LIMITE}/${AGREGADO_SIN_LIMITE} ${speedBytes}/${speedBytes}`
  }
  return `${speedBytes}/${speedBytes}`
}

// El número que importa mostrar en la tabla: para una regla de grupo con
// tope individual (clase 2) es el segundo par (individual), no el
// agregado -que es un valor "de relleno", ver AGREGADO_SIN_LIMITE.
function limiteVisible(pool: DelayPool): number {
  const partes = pool.parameters.trim().split(/\s+/)
  const ultimo = partes[partes.length - 1] || '0/0'
  const [, limite] = ultimo.split('/')
  return parseInt(limite) || 0
}

function aclLabel(acl: Acl): string {
  return acl.display_name || acl.name
}

// Arma un patrón url_regex a partir de una lista de extensiones escritas
// a mano ("mp4, zip, iso") -con "-i" para que no importen mayúsculas.
// Ancla al final de la URL: es la convención estándar para esto en Squid,
// con la salvedad de que una URL con parámetros después de la extensión
// (ej. "archivo.mp4?token=...") no matchea -no hay forma de evitarlo sin
// inspeccionar la respuesta, que los delay pools no hacen.
function buildExtRegex(extensiones: string): string {
  const lista = extensiones
    .split(',')
    .map(e => e.trim().replace(/^\./, '').toLowerCase())
    .filter(Boolean)
    .map(e => e.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  if (lista.length === 0) return ''
  return `-i \\.(${lista.join('|')})$`
}

const NUEVO_TIPO_ARCHIVO = '__nuevo_tipo_archivo__'

interface OpcionObjetivo { key: string; label: string; grupo: string }

// Una sola lista con TODO lo que se puede limitar -usuarios, grupos,
// dominios/categorías y tipos de archivo- en vez de pedir primero "a qué
// tipo de cosa se aplica" y recién después "a cuál de ellas". Ya viene
// resuelta: elegir una opción alcanza para saber qué ACL (o qué crear)
// hace falta, sin que el admin tenga que entender la diferencia entre una
// ACL y un grupo.
function construirOpciones(acls: Acl[], groups: Group[], proxyUsers: ProxyUser[]): OpcionObjetivo[] {
  const opciones: OpcionObjetivo[] = []
  for (const u of proxyUsers) {
    opciones.push({ key: `user:${u.username}`, label: u.username, grupo: traducir("Usuarios") })
  }
  for (const g of groups) {
    opciones.push({ key: `group:${g.name}`, label: g.name, grupo: traducir("Grupos") })
  }
  for (const a of acls.filter(a => a.type === 'dstdomain' || a.type === 'dstdom_regex')) {
    opciones.push({ key: `acl:${a.name}`, label: aclLabel(a), grupo: traducir("Dominios y categorías") })
  }
  for (const a of acls.filter(a => a.type === 'url_regex' || a.type === 'req_mime_type')) {
    opciones.push({ key: `acl:${a.name}`, label: aclLabel(a), grupo: traducir("Tipos de archivo") })
  }
  return opciones
}

// A partir de un pool ya creado, adivina qué opción de la lista simple lo
// generaría -para precargar el editor. Si la forma no calza con el
// modelo simple (una clase 3/4/5, una ACL que no es ninguna de las
// conocidas, varios niveles con valores distintos), se marca `simple:
// false` y se cae al editor técnico en vez de forzar una reinterpretación
// que podría no ser la que el admin quiso.
function inferirObjetivo(pool: DelayPool, acls: Acl[], groups: Group[]): { key: string; individual: boolean; simple: boolean } {
  const niveles = pool.parameters.trim().split(/\s+/).map(p => {
    const [r, l] = p.split('/')
    return { restore: parseInt(r) || 0, limit: parseInt(l) || 0 }
  })
  const formaPlanaClase1 = pool.pool_class === 1 && niveles.length === 1 && niveles[0].restore === niveles[0].limit
  const formaPlanaClase2 = pool.pool_class === 2 && niveles.length === 2 && niveles[1].restore === niveles[1].limit

  if (!pool.acl_name) {
    return { key: 'all', individual: false, simple: formaPlanaClase1 }
  }
  const group = groups.find(g => g.name === pool.acl_name)
  if (group) {
    if (formaPlanaClase1) return { key: `group:${group.name}`, individual: false, simple: true }
    if (formaPlanaClase2) return { key: `group:${group.name}`, individual: true, simple: true }
    return { key: `group:${group.name}`, individual: false, simple: false }
  }
  const acl = acls.find(a => a.name === pool.acl_name)
  if (!acl) return { key: 'all', individual: false, simple: false }
  if (acl.type === 'proxy_auth' && acl.value && !acl.value.includes(' ') && acl.value !== 'REQUIRED') {
    return { key: `user:${acl.value}`, individual: false, simple: formaPlanaClase1 }
  }
  return { key: `acl:${acl.name}`, individual: false, simple: formaPlanaClase1 }
}

export default function DelayPools() {
  const [pools, setPools] = useState<DelayPool[]>([])
  const [acls, setAcls] = useState<Acl[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [proxyUsers, setProxyUsers] = useState<ProxyUser[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [showRawEditor, setShowRawEditor] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const [name, setName] = useState('')
  const [targetKey, setTargetKey] = useState('all')
  const [groupIndividual, setGroupIndividual] = useState(false)
  const [speed, setSpeed] = useState(64)
  const [speedUnit, setSpeedUnit] = useState(1024)
  const [enabled, setEnabled] = useState(true)

  const [newFileName, setNewFileName] = useState('')
  const [newFileExt, setNewFileExt] = useState('')
  const [creatingFileAcl, setCreatingFileAcl] = useState(false)

  // Editor técnico (clase de Squid 1-5 elegida a mano): solo hace falta
  // para combinaciones que el modelo simple no cubre (por red, por tag,
  // ráfaga distinta al límite sostenido) -reservado a pools importados de
  // un squid.conf existente con esa forma, o a quien lo pida a propósito.
  const [rawPoolClass, setRawPoolClass] = useState(2)
  const [rawAclName, setRawAclName] = useState('')
  const [rawParameters, setRawParameters] = useState('')

  const [error, setError] = useState('')
  const { showToast, ToastContainer } = useToast()

  const loadPools = () => {
    api.listDelayPools().then(setPools).catch(() => showToast(traducir("Error al cargar delay pools"), 'error')).finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPools()
    api.listAcls().then(setAcls).catch(console.error)
    // Los grupos y los usuarios de proxy no son ACLs -Squid los ve como
    // proxy_auth, pero SquidManager los administra en sus propias páginas
    // (Gestión > Grupos, Gestión > Usuarios)- por eso hacen falta estas
    // llamadas aparte para poder ofrecerlos como objetivo de una regla.
    api.listGroups().then(setGroups).catch(console.error)
    api.listUsers().then(setProxyUsers).catch(console.error)
  }, [])

  const opciones = construirOpciones(acls, groups, proxyUsers)

  const resetForm = () => {
    setName('')
    setTargetKey('all')
    setGroupIndividual(false)
    setSpeed(64)
    setSpeedUnit(1024)
    setEnabled(true)
    setNewFileName('')
    setNewFileExt('')
    setShowRawEditor(false)
    setRawPoolClass(2)
    setRawAclName('')
    setRawParameters('')
    setEditingId(null)
    setError('')
  }

  // Crea la ACL url_regex a partir del mini-formulario de extensiones -se
  // llama desde handleSave, como un paso más de guardar la regla, no como
  // una acción aparte: pedirle al admin que primero apriete "crear lista"
  // y recién después "crear regla" era un segundo paso escondido que no
  // se entendía como parte del mismo formulario.
  const crearAclDeTipoArchivo = async (): Promise<string> => {
    const nombreAcl = normalizarNombreAcl(newFileName) || normalizarNombreAcl(`archivos_${newFileExt}`)
    const pattern = buildExtRegex(newFileExt)
    if (!nombreAcl) throw new Error(traducir("Elegí un nombre para esta lista de extensiones."))
    if (!pattern) throw new Error(traducir("Escribí al menos una extensión (ej: mp4, zip, iso)."))
    await api.createAcl({
      name: nombreAcl, type: 'url_regex', value: pattern,
      description: traducir("Extensiones: {ext}", { ext: newFileExt }),
    })
    return nombreAcl
  }

  // Si el objetivo es "usuario específico", hace falta una ACL proxy_auth
  // con ese nombre de usuario como valor -se reutiliza una ya existente
  // (por si otra regla ya apunta al mismo usuario) o se crea sola, sin que
  // el admin tenga que pasar por la página de ACLs para esto.
  const resolverAclDeUsuario = async (username: string): Promise<string> => {
    const existente = acls.find(a => a.type === 'proxy_auth' && a.value === username)
    if (existente) return existente.name
    const nombre = normalizarNombreAcl(`usuario_${username}`)
    await api.createAcl({
      name: nombre, type: 'proxy_auth', value: username,
      description: traducir("Usuario específico: {u}", { u: username }),
    })
    return nombre
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (showRawEditor) {
      if (!rawParameters.trim()) { setError(traducir("Los parámetros no pueden quedar vacíos.")); return }
      try {
        const data = { pool_class: rawPoolClass, parameters: rawParameters, acl_name: rawAclName || null, description: name, enabled }
        if (editingId) { await api.updateDelayPool(editingId, data); showToast(traducir("Delay pool actualizado correctamente")) }
        else { await api.createDelayPool(data); showToast(traducir("Delay pool creado correctamente")) }
        notificarCambioPendiente()
        resetForm()
        setShowForm(false)
        loadPools()
      } catch (err: any) {
        setError(err.message)
        showToast(`Error: ${err.message}`, 'error')
      }
      return
    }

    if (!name.trim()) { setError(traducir("Ponele un nombre a esta regla.")); return }
    if (speed <= 0) { setError(traducir("La velocidad debe ser mayor a 0.")); return }

    try {
      setCreatingFileAcl(targetKey === NUEVO_TIPO_ARCHIVO)
      let aclName: string | null = null
      let poolClass = 1
      let nuevaAclDeArchivo = false
      if (targetKey.startsWith('user:')) {
        aclName = await resolverAclDeUsuario(targetKey.slice('user:'.length))
      } else if (targetKey.startsWith('group:')) {
        aclName = targetKey.slice('group:'.length)
        poolClass = groupIndividual ? 2 : 1
      } else if (targetKey === NUEVO_TIPO_ARCHIVO) {
        aclName = await crearAclDeTipoArchivo()
        nuevaAclDeArchivo = true
      } else if (targetKey.startsWith('acl:')) {
        aclName = targetKey.slice('acl:'.length)
      }
      const speedBytes = Math.round(speed * speedUnit)
      const data = {
        pool_class: poolClass,
        parameters: buildSimpleParameters(poolClass, speedBytes),
        acl_name: aclName,
        description: name,
        enabled,
      }
      if (editingId) {
        await api.updateDelayPool(editingId, data)
        showToast(traducir("Delay pool actualizado correctamente"))
      } else {
        await api.createDelayPool(data)
        showToast(traducir("Delay pool creado correctamente"))
      }
      notificarCambioPendiente()
      resetForm()
      setShowForm(false)
      loadPools()
      if (targetKey.startsWith('user:') || nuevaAclDeArchivo) api.listAcls().then(setAcls).catch(console.error)
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    } finally {
      setCreatingFileAcl(false)
    }
  }

  const handleEdit = (pool: DelayPool) => {
    setName(pool.description || '')
    setEnabled(pool.enabled)
    setEditingId(pool.id)

    const inferido = inferirObjetivo(pool, acls, groups)
    if (inferido.simple) {
      setShowRawEditor(false)
      setTargetKey(inferido.key)
      setGroupIndividual(inferido.individual)
      const bytes = limiteVisible(pool)
      const unidad = bytes >= 1048576 ? 1048576 : bytes >= 1024 ? 1024 : 1
      setSpeed(Math.round((bytes / unidad) * 100) / 100)
      setSpeedUnit(unidad)
    } else {
      setShowRawEditor(true)
      setRawPoolClass(pool.pool_class)
      setRawAclName(pool.acl_name || '')
      setRawParameters(pool.parameters)
    }
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm(traducir("¿Eliminar este delay pool?"))) return
    try {
      await api.deleteDelayPool(id)
      notificarCambioPendiente()
      loadPools()
      showToast(traducir("Delay pool eliminado correctamente"))
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  // Texto de la columna "Aplica a" -reusa la misma inferencia que
  // precarga el editor, para que la tabla y el formulario coincidan.
  const describeTarget = (pool: DelayPool): string => {
    const inferido = inferirObjetivo(pool, acls, groups)
    if (inferido.key === 'all') return traducir("Todo el tráfico")
    if (inferido.key.startsWith('user:')) return traducir("Usuario: {nombre}", { nombre: inferido.key.slice(5) })
    if (inferido.key.startsWith('group:')) {
      const nombre = inferido.key.slice(6)
      return inferido.individual
        ? traducir("Grupo {nombre} (límite por equipo)", { nombre })
        : traducir("Grupo {nombre}", { nombre })
    }
    if (inferido.key.startsWith('acl:')) {
      const acl = acls.find(a => a.name === inferido.key.slice(4))
      return acl ? aclLabel(acl) : inferido.key.slice(4)
    }
    return pool.acl_name || traducir("Todo el tráfico")
  }

  const opcionesAgrupadas = opciones.reduce<Record<string, OpcionObjetivo[]>>((acc, o) => {
    (acc[o.grupo] = acc[o.grupo] || []).push(o)
    return acc
  }, {})
  const previewClass = targetKey.startsWith('group:') && groupIndividual ? 2 : 1

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Ancho de banda")}</h1>
          <p className="page-sub">{traducir("Reglas de velocidad máxima por usuario, grupo, dominio o tipo de archivo")}</p>
        </div>
        <button
          onClick={() => { if (showForm) { resetForm(); setShowForm(false) } else { resetForm(); setShowForm(true) } }}
          className="btn btn-primary"
        >
          {showForm ? traducir('Cancelar') : traducir('+ Nueva regla')}
        </button>
      </div>

      <div className="note note-info mb-6">
        <p className="note-text">
          {traducir("Esto limita la velocidad de descarga (lo que el servidor manda al cliente). Squid no puede limitar la velocidad de subida con este mecanismo.")}
        </p>
      </div>

      {showForm && (
        <form onSubmit={handleSave} className="card p-6 mb-6">
          <h3 className="font-medium text-ink mb-4">{editingId ? traducir('Editar regla') : traducir('Nueva regla')}</h3>

          {showRawEditor ? (
            <>
              <div className="note note-warn mb-4">
                <p className="note-text">{traducir("Esta regla usa una configuración que el editor simple no puede representar (por red, por tag, o velocidades de ráfaga distintas al límite). Se edita en formato técnico de Squid.")}</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label htmlFor="dp-raw-name" className="field-label block mb-1.5">{traducir("Nombre")}</label>
                  <input id="dp-raw-name" type="text" value={name} onChange={e => setName(e.target.value)} className="input" required />
                </div>
                <div>
                  <label htmlFor="dp-raw-class" className="field-label block mb-1.5">{traducir("Clase de Squid (1-5)")}</label>
                  <input id="dp-raw-class" type="number" min={1} max={5} value={rawPoolClass} onChange={e => setRawPoolClass(parseInt(e.target.value) || 1)} className="input" />
                </div>
                <div>
                  <label htmlFor="dp-raw-acl" className="field-label block mb-1.5">{traducir("ACL asociada (opcional)")}</label>
                  <select id="dp-raw-acl" value={rawAclName} onChange={e => setRawAclName(e.target.value)} className="input">
                    <option value="">{traducir("Sin ACL (aplica a todos)")}</option>
                    {acls.map(a => <option key={a.id} value={a.name}>{a.name}</option>)}
                    {groups.map(g => <option key={`g-${g.id}`} value={g.name}>{g.name}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="dp-raw-params" className="field-label block mb-1.5">{traducir("Parámetros (restauración/límite por nivel)")}</label>
                  <input id="dp-raw-params" type="text" value={rawParameters} onChange={e => setRawParameters(e.target.value)} placeholder="65536/65536 8192/8192" className="input font-mono text-sm" />
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="mb-4">
                <label htmlFor="dp-name" className="field-label block mb-1.5">{traducir("Nombre de la regla")}</label>
                <input id="dp-name" type="text" value={name} onChange={e => setName(e.target.value)}
                  placeholder={traducir("ej: Límite para invitados")} className="input" required />
              </div>

              <div className="mb-4">
                <label htmlFor="dp-target" className="field-label block mb-1.5">{traducir("Aplica a")}</label>
                <select id="dp-target" value={targetKey} onChange={e => setTargetKey(e.target.value)} className="input">
                  <option value="all">{traducir("Todo el tráfico")}</option>
                  {Object.entries(opcionesAgrupadas).map(([grupo, lista]) => (
                    <optgroup key={grupo} label={grupo}>
                      {lista.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
                      {grupo === traducir("Tipos de archivo") && (
                        <option value={NUEVO_TIPO_ARCHIVO}>{traducir("+ Crear un tipo de archivo nuevo...")}</option>
                      )}
                    </optgroup>
                  ))}
                  {!opciones.some(o => o.grupo === traducir("Tipos de archivo")) && (
                    <optgroup label={traducir("Tipos de archivo")}>
                      <option value={NUEVO_TIPO_ARCHIVO}>{traducir("+ Crear un tipo de archivo nuevo...")}</option>
                    </optgroup>
                  )}
                </select>
                {targetKey.startsWith('group:') && (
                  <>
                    <label className="flex items-center gap-2 text-sm text-ink-2 mt-2">
                      <input type="checkbox" checked={groupIndividual} onChange={e => setGroupIndividual(e.target.checked)} />
                      {traducir("Cada equipo tiene su propio límite, en vez de compartir un único cupo total")}
                    </label>
                    {groupIndividual && (
                      <p className="field-help mt-1">
                        {traducir("El límite se aplica por dirección IP de origen, no por nombre de usuario: dos integrantes navegando desde el mismo equipo o la misma IP comparten el cupo entre ellos.")}
                      </p>
                    )}
                  </>
                )}
                {opciones.length === 0 && (
                  <p className="field-help mt-1">
                    {traducir("Para elegir un usuario, grupo, dominio o tipo de archivo, primero tiene que existir alguno (Gestión → Usuarios, Grupos, ACLs o Categorías de dominios).")}
                  </p>
                )}
              </div>

              {targetKey === NUEVO_TIPO_ARCHIVO && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4 bg-brand-50 rounded-lg p-4 border border-line-soft">
                  <div>
                    <label htmlFor="dp-new-file-name" className="field-label block mb-1.5">{traducir("Nombre para esta lista")}</label>
                    <input id="dp-new-file-name" type="text" value={newFileName}
                      onChange={e => setNewFileName(normalizarNombreAcl(e.target.value))}
                      placeholder={traducir("ej: archivos_pesados")} className="input" />
                  </div>
                  <div>
                    <label htmlFor="dp-new-file-ext" className="field-label block mb-1.5">{traducir("Extensiones (separadas por coma)")}</label>
                    <input id="dp-new-file-ext" type="text" value={newFileExt} onChange={e => setNewFileExt(e.target.value)}
                      placeholder={traducir("ej: mp4, zip, iso, exe")} className="input" />
                  </div>
                  <p className="text-xs text-ink-3 md:col-span-2">{traducir("La lista se crea sola al guardar la regla, con estos datos.")}</p>
                </div>
              )}

              <div className="mb-4">
                <label htmlFor="dp-speed" className="field-label block mb-1.5">{traducir("Velocidad máxima de descarga")}</label>
                <div className="flex gap-2 max-w-sm">
                  <input id="dp-speed" type="number" min="0.1" step="0.1" value={speed}
                    onChange={e => setSpeed(parseFloat(e.target.value) || 0)} className="input" />
                  <select value={speedUnit} onChange={e => setSpeedUnit(parseInt(e.target.value))} className="input">
                    {UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
                  </select>
                </div>
              </div>

              <div className="bg-slate-900 rounded-lg p-3 mb-4">
                <p className="text-xs text-slate-400 mb-1">{traducir("Formato Squid generado:")}</p>
                <p className="text-green-400 font-mono text-sm">
                  delay_class N {previewClass}<br />
                  delay_parameters N {buildSimpleParameters(previewClass, Math.round(speed * speedUnit))}
                </p>
              </div>

              <button type="button" className="text-xs text-ink-3 hover:text-brand-700 underline mb-4"
                onClick={() => { setShowRawEditor(true); setRawPoolClass(2); setRawAclName(''); setRawParameters('') }}>
                {traducir("¿Necesitás algo más avanzado (por red, por tag)? Usar el editor técnico")}
              </button>
            </>
          )}

          <label className="flex items-center gap-2 text-sm text-ink-2 mb-4">
            <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
            {traducir("Activa")}
          </label>

          {error && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <div className="flex items-center gap-3">
            <button type="submit" className="btn btn-primary" disabled={creatingFileAcl}>
              {creatingFileAcl ? traducir("Creando...") : editingId ? traducir('Guardar Cambios') : traducir('Crear regla')}
            </button>
            <RequiereAplicar />
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12 text-ink-3">{traducir("Cargando...")}</div>
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
              {pools.map(pool => (
                <tr key={pool.id} className={!pool.enabled ? 'opacity-50' : ''}>
                  <td className="px-5 py-3 font-medium text-ink">{pool.description || traducir("(sin nombre)")}</td>
                  <td className="px-5 py-3">{describeTarget(pool)}</td>
                  <td className="px-5 py-3 tabular">{formatSpeed(limiteVisible(pool))}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${pool.enabled ? 'pill-ok' : 'pill-danger'}`}>
                      {pool.enabled ? traducir('Activo') : traducir('Inactivo')}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right space-x-2">
                    <button onClick={() => handleEdit(pool)} className="text-primary-600 hover:text-primary-800 text-sm font-medium">{traducir("Editar")}</button>
                    <button onClick={() => handleDelete(pool.id)} className="text-danger hover:text-danger text-sm font-medium">{traducir("Eliminar")}</button>
                  </td>
                </tr>
              ))}
              {pools.length === 0 && (
                <tr><td colSpan={5} className="px-5 py-12 text-center text-ink-3">{traducir("No hay reglas de ancho de banda configuradas.")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
