import { traducir } from '../i18n'
import { IconEdit, IconTrash, IconUpload } from '../components/Icons'
import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import RequiereAplicar from '../components/RequiereAplicar'
import Modal from '../components/Modal'
import Pagination from '../components/Pagination'
import { usePaginacion } from '../hooks/usePaginacion'
import { normalizarNombreAcl } from '../utils/aclNames'
import { confirmar } from '../components/ConfirmDialog'

interface Acl {
  id: number
  name: string
  type: string
  // null para una ACL 'file': su contenido vive solo en el archivo del
  // servidor (puede tener millones de líneas), no viaja por la API. Usar
  // line_count para mostrar cuántos dominios tiene.
  value: string | null
  source: string
  line_count: number | null
  description: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

const ACL_TYPES = [
  { value: 'src', label: traducir("IP de origen (src)"), example: '192.168.1.0/24' },
  { value: 'dst', label: traducir("IP de destino (dst)"), example: '10.0.0.0/8' },
  { value: 'dstdomain', label: traducir("Dominio de destino (dstdomain)"), example: '.facebook.com' },
  { value: 'dstdom_regex', label: traducir("Regex de dominio (dstdom_regex)"), example: '\\.social\\.' },
  { value: 'url_regex', label: traducir("Regex de URL (url_regex)"), example: '\\.mp4$' },
  { value: 'urlpath_regex', label: traducir("Regex de path URL (urlpath_regex)"), example: '/download/' },
  { value: 'port', label: traducir("Puerto destino (port)"), example: '443 80' },
  { value: 'proto', label: traducir("Protocolo (proto)"), example: 'HTTP FTP' },
  { value: 'method', label: traducir("Método HTTP (method)"), example: 'GET POST' },
  { value: 'time', label: traducir("Horario (time)"), example: 'M-F 09:00-17:00' },
  { value: 'proxy_auth', label: traducir("Usuario autenticado (proxy_auth)"), example: 'REQUIRED' },
  { value: 'maxconn', label: traducir("Conexiones máximas (maxconn)"), example: '10' },
  { value: 'browser', label: traducir("User-Agent (browser)"), example: 'Chrome' },
  { value: 'rep_mime_type', label: traducir("MIME type de respuesta (rep_mime_type)"), example: 'video/' },
]

const ACLS_POR_PAGINA = 50

type FormAcl = { name: string; type: string; value: string; description: string; enabled: boolean }
const FORM_VACIO: FormAcl = { name: '', type: 'dstdomain', value: '', description: '', enabled: true }

/** Modal de crear/editar una ACL "de siempre" (no las 'file', que se
 * cargan/reemplazan desde BulkUploadModal). */
function AclFormModal({ form, setForm, editingId, onClose, onSubmit, error }: {
  form: FormAcl
  setForm: (f: FormAcl) => void
  editingId: number | null
  onClose: () => void
  onSubmit: (e: React.FormEvent) => void
  error: string
}) {
  const selectedType = ACL_TYPES.find(t => t.value === form.type)
  return (
    <Modal title={editingId ? traducir('Editar ACL') : traducir('Nueva ACL')} onClose={onClose} maxWidth="max-w-xl">
      <form onSubmit={onSubmit}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="acl-name" className="field-label block mb-1.5">{traducir("Nombre")}</label>
            <input id="acl-name" type="text" value={form.name} onChange={e => setForm({ ...form, name: normalizarNombreAcl(e.target.value) })}
              placeholder={traducir("ej: redes_sociales")} className="input font-mono text-sm" required autoFocus />
            <p className="field-help mt-1">{traducir("Identificador técnico — se ajusta solo a minúsculas y guiones bajos, sin espacios ni acentos.")}</p>
          </div>
          <div>
            <label htmlFor="acl-type" className="field-label block mb-1.5">{traducir("Tipo de ACL")}</label>
            <select id="acl-type" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}
              className="input">
              {ACL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
        </div>
        <div className="mt-4">
          <label htmlFor="acl-value" className="field-label block mb-1.5">{traducir("Valor")}</label>
          <input id="acl-value" type="text" value={form.value} onChange={e => setForm({ ...form, value: e.target.value })}
            placeholder={selectedType?.example || ''} className="input font-mono text-sm" required />
          {selectedType && (
            <p className="text-xs text-ink-3 mt-1">
              {traducir("Ejemplo:")} <span className="font-mono">{selectedType.example}</span>
              {' · '}
              <a href="/documentacion?articulo=acls" target="_blank" rel="noopener noreferrer"
                 className="text-brand-600 hover:underline">{traducir("¿Cómo se escribe el valor? Ver documentación de ACLs")}</a>
            </p>
          )}
        </div>
        <div className="mt-4">
          <label htmlFor="acl-description" className="field-label block mb-1.5">{traducir("Descripción (opcional)")}</label>
          <input id="acl-description" type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
            placeholder={traducir("ej: Bloquear acceso a redes sociales")} className="input" />
        </div>
        {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
        <div className="mt-5 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <button type="submit" className="btn btn-primary">
              {editingId ? traducir('Guardar Cambios') : traducir('Crear ACL')}
            </button>
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">{traducir("Cancelar")}</button>
          </div>
          <RequiereAplicar />
        </div>
      </form>
    </Modal>
  )
}

function BulkUploadModal({ bulkAclName, setBulkAclName, bulkType, setBulkType, bulkModo, setBulkModo,
  bulkBusy, bulkFileRef, onClose, onSubmit }: {
  bulkAclName: string
  setBulkAclName: (v: string) => void
  bulkType: 'dstdomain' | 'dstdom_regex'
  setBulkType: (v: 'dstdomain' | 'dstdom_regex') => void
  bulkModo: 'reemplazar' | 'agregar'
  setBulkModo: (v: 'reemplazar' | 'agregar') => void
  bulkBusy: boolean
  bulkFileRef: React.RefObject<HTMLInputElement>
  onClose: () => void
  onSubmit: (e: React.FormEvent) => void
}) {
  return (
    <Modal title={traducir('Cargar dominios desde archivo')} onClose={onClose} maxWidth="max-w-xl">
      <p className="text-xs text-ink-3 mb-4">
        {traducir('Un dominio por línea (líneas vacías o que empiezan con # se ignoran). Listas grandes se guardan en un archivo aparte que Squid lee directo, no como una única línea gigante en squid.conf.')}
      </p>
      <form onSubmit={onSubmit}>
        <div className="grid grid-cols-1 gap-4">
          <div>
            <label htmlFor="acl-bulk-name" className="field-label block mb-1.5">{traducir("Nombre de la ACL")}</label>
            <input id="acl-bulk-name" type="text" value={bulkAclName} onChange={e => setBulkAclName(normalizarNombreAcl(e.target.value))}
              placeholder={traducir("ej: blocklist_publicidad")} className="input" required autoFocus />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="acl-bulk-type" className="field-label block mb-1.5">{traducir("Tipo")}</label>
              <select id="acl-bulk-type" value={bulkType} onChange={e => setBulkType(e.target.value as any)} className="input">
                <option value="dstdomain">{traducir('Dominio (dstdomain)')}</option>
                <option value="dstdom_regex">{traducir('Regex de dominio (dstdom_regex)')}</option>
              </select>
            </div>
            <div>
              <label htmlFor="acl-bulk-modo" className="field-label block mb-1.5">{traducir("Si la ACL ya existe")}</label>
              <select id="acl-bulk-modo" value={bulkModo} onChange={e => setBulkModo(e.target.value as any)} className="input">
                <option value="reemplazar">{traducir('Reemplazar toda la lista')}</option>
                <option value="agregar">{traducir('Agregar a lo que ya había')}</option>
              </select>
            </div>
          </div>
        </div>
        <div className="mt-4">
          <label htmlFor="acl-bulk-file" className="field-label block mb-1.5">{traducir("Archivo")}</label>
          <input id="acl-bulk-file" ref={bulkFileRef} type="file" accept=".txt,.csv,text/plain" className="input" required />
        </div>
        <div className="mt-5 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <button type="submit" disabled={bulkBusy} className="btn btn-primary">
              {bulkBusy ? traducir('Cargando…') : traducir('Cargar')}
            </button>
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg font-medium border border-line hover:bg-brand-50 transition">{traducir("Cancelar")}</button>
          </div>
          <RequiereAplicar />
        </div>
        {bulkBusy && (
          <div className="mt-3">
            <div className="indeterminate-bar-track h-1.5 w-full rounded-full bg-line-soft">
              <div className="indeterminate-bar-fill h-full rounded-full bg-primary-500" />
            </div>
            <p className="text-xs text-ink-3 mt-1.5">
              {traducir('Leyendo y validando el archivo… con listas de millones de dominios puede tardar varios segundos.')}
            </p>
          </div>
        )}
      </form>
    </Modal>
  )
}

export default function ACLs() {
  const [acls, setAcls] = useState<Acl[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<FormAcl>(FORM_VACIO)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const { showToast, ToastContainer } = useToast()
  // Las categorías de dominio (HaGeZi, o las creadas a mano) son ACLs
  // dstdomain/dstdom_regex por dentro, pero tienen su propia página
  // ("Categorías de dominios") con edición de metadatos y sincronización.
  // Mostrarlas también acá por defecto duplicaba la lista y confundía
  // dónde había que administrar cada una -se ocultan salvo que se pida
  // verlas explícitamente.
  const [verCategorias, setVerCategorias] = useState(false)

  // Dónde se usa cada ACL (las que no aparecen no las usa ninguna regla).
  const [usos, setUsos] = useState<Record<string, string[]>>({})

  const loadAcls = (incluirCategorias = verCategorias) => {
    api.getAclUsage().then(setUsos).catch(() => {})
    api.listAcls({ isCategory: incluirCategorias ? undefined : false })
      .then(r => { setAcls(r); setLoadError(false) })
      .catch(() => { showToast(traducir("Error al cargar ACLs"), 'error'); setLoadError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadAcls(verCategorias) }, [verCategorias])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      if (editingId) {
        await api.updateAcl(editingId, form)
        showToast(`ACL "${form.name}" actualizada correctamente`)
      } else {
        await api.createAcl(form)
        showToast(`ACL "${form.name}" creada correctamente`)
      }
      notificarCambioPendiente()
      setForm(FORM_VACIO)
      setEditingId(null)
      setShowForm(false)
      loadAcls()
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    }
  }

  const handleEdit = (acl: Acl) => {
    if (acl.source === 'file') {
      setBulkAclName(acl.name)
      setBulkType(acl.type as any)
      setBulkModo('reemplazar')
      setShowBulk(true)
      setShowForm(false)
      return
    }
    setForm({ name: acl.name, type: acl.type, value: acl.value ?? '', description: acl.description || '', enabled: acl.enabled })
    setEditingId(acl.id)
    setShowForm(true)
  }

  // --- Carga masiva de dominios ---
  const [showBulk, setShowBulk] = useState(false)
  const [bulkAclName, setBulkAclName] = useState('')
  const [bulkModo, setBulkModo] = useState<'reemplazar' | 'agregar'>('reemplazar')
  const [bulkType, setBulkType] = useState<'dstdomain' | 'dstdom_regex'>('dstdomain')
  const [bulkBusy, setBulkBusy] = useState(false)
  const bulkFileRef = useRef<HTMLInputElement>(null)

  const handleBulkUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    const file = bulkFileRef.current?.files?.[0]
    if (!file || !bulkAclName.trim()) return
    setBulkBusy(true)
    try {
      const result = await api.bulkUploadDomains(file, bulkAclName.trim(), bulkModo, bulkType)
      notificarCambioPendiente()
      showToast(
        `"${bulkAclName}": ${result.dominios_importados} dominios (${result.acl.source === 'file' ? 'archivo' : 'inline'})` +
        (result.total_rechazados > 0 ? `, ${result.total_rechazados} línea(s) rechazada(s)` : '')
      )
      setShowBulk(false)
      setBulkAclName('')
      if (bulkFileRef.current) bulkFileRef.current.value = ''
      loadAcls()
    } catch (err: any) {
      showToast(`Error: ${err.message}`, 'error')
    } finally {
      setBulkBusy(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!(await confirmar(traducir("¿Eliminar esta ACL?")))) return
    try {
      await api.deleteAcl(id)
      notificarCambioPendiente()
      loadAcls()
      showToast(traducir("ACL eliminada correctamente"))
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  // Búsqueda: por nombre, tipo, valor o descripción -con la lista
  // creciendo (HaGeZi, blocklists a medida, categorías propias) encontrar
  // una ACL puntual desplazándose a mano dejaba de ser práctico. Pedido en
  // vivo, 2026-09-27.
  const term = search.trim().toLowerCase()
  const filteredAcls = term
    ? acls.filter(a =>
        a.name.toLowerCase().includes(term) ||
        a.type.toLowerCase().includes(term) ||
        (a.value ?? '').toLowerCase().includes(term) ||
        (a.description ?? '').toLowerCase().includes(term)
      )
    : acls

  const { pagina, setPagina, totalPaginas } = usePaginacion(filteredAcls.length, ACLS_POR_PAGINA)
  useEffect(() => { setPagina(0) }, [search, verCategorias])
  const aclsPagina = filteredAcls.slice(pagina * ACLS_POR_PAGINA, (pagina + 1) * ACLS_POR_PAGINA)

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Listas de Control de Acceso (ACLs)")}</h1>
          <p className="page-sub">
            {traducir("Define qué tráfico coincide con cada criterio")}
            {" · "}
            <Link to="/categorias" className="text-brand-700 hover:underline">{traducir("Categorías de dominios")}</Link>
            {" "}
            {traducir("se administran aparte")}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowBulk(true)}
            className="btn btn-ghost"
            title={traducir("Para listas grandes (blocklists): un dominio por línea")}
          >
            {traducir('Cargar dominios')}
          </button>
          <button
            onClick={() => { setForm(FORM_VACIO); setEditingId(null); setShowForm(true) }}
            className="btn btn-primary"
          >
            {traducir('+ Nueva ACL')}
          </button>
        </div>
      </div>

      {showBulk && (
        <BulkUploadModal
          bulkAclName={bulkAclName} setBulkAclName={setBulkAclName}
          bulkType={bulkType} setBulkType={setBulkType}
          bulkModo={bulkModo} setBulkModo={setBulkModo}
          bulkBusy={bulkBusy} bulkFileRef={bulkFileRef}
          onClose={() => setShowBulk(false)}
          onSubmit={handleBulkUpload}
        />
      )}

      {showForm && (
        <AclFormModal
          form={form} setForm={setForm} editingId={editingId}
          onClose={() => setShowForm(false)}
          onSubmit={handleSave}
          error={error}
        />
      )}

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={traducir("Buscar por nombre, tipo, valor o descripción…")}
          className="input flex-1"
        />
        <label className="flex items-center gap-2 text-sm text-ink-2 whitespace-nowrap">
          <input type="checkbox" checked={verCategorias} onChange={e => setVerCategorias(e.target.checked)} />
          {traducir("Mostrar también las categorías de dominio")}
        </label>
      </div>

      {loading ? (
        <LoadingState />
      ) : loadError && acls.length === 0 ? (
        <ErrorState onRetry={() => loadAcls()} />
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left">{traducir("Nombre")}</th>
                <th className="text-left">{traducir("Tipo")}</th>
                <th className="text-left">{traducir("Valor")}</th>
                <th className="text-left">{traducir("Estado")}</th>
                <th className="text-left">{traducir("Uso")}</th>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {aclsPagina.map(acl => (
                <tr key={acl.id} className="hover:bg-brand-50">
                  <td className="px-6 py-4 font-medium text-ink">{acl.name}</td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-brand-50 text-brand-700 text-xs font-mono rounded">{acl.type}</span>
                    {acl.source === 'file' && (
                      <span className="ml-1 px-2 py-1 bg-amber-50 text-amber-700 text-xs font-mono rounded" title={traducir("Cargada desde archivo, no se edita a mano")}>
                        {traducir("archivo")}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 font-mono text-sm text-ink-2 max-w-xs truncate">
                    {acl.source === 'file'
                      ? `${(acl.line_count ?? 0).toLocaleString()} ${traducir('dominios')}`
                      : acl.value}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${acl.enabled ? 'pill-ok' : 'pill-danger'}`}>
                      {acl.enabled ? traducir('Activa') : traducir('Inactiva')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {usos[acl.name] ? (
                      <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full pill-info cursor-help" title={usos[acl.name].join('\n')}>
                        {traducir("En uso")} · {usos[acl.name].length}
                      </span>
                    ) : (
                      <span className="inline-flex px-2 py-1 text-xs rounded-full pill-mute cursor-help" title={traducir("Ninguna regla de acceso ni de ancho de banda la usa todavía: no tiene efecto hasta que la uses en una regla.")}>
                        {traducir("Sin uso")}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => handleEdit(acl)} className="btn-icon"
                        title={acl.source === 'file' ? traducir('Reemplazar') : traducir('Editar')}
                        aria-label={acl.source === 'file' ? traducir('Reemplazar') : traducir('Editar')}>
                        {acl.source === 'file' ? <IconUpload /> : <IconEdit />}
                      </button>
                      <button onClick={() => handleDelete(acl.id)} className="btn-icon btn-icon-danger"
                        title={traducir("Eliminar")} aria-label={traducir("Eliminar")}>
                        <IconTrash />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {aclsPagina.length === 0 && (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-ink-3">
                  {acls.length === 0
                    ? traducir("No hay ACLs personalizadas. Las ACLs predefinidas (localnet, Safe_ports, etc.) ya están incluidas automáticamente.")
                    : traducir("Ninguna ACL coincide con la búsqueda.")}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {filteredAcls.length > 0 && (
        <Pagination pagina={pagina} totalPaginas={totalPaginas} total={filteredAcls.length}
          porPagina={ACLS_POR_PAGINA} onChange={setPagina} />
      )}
    </div>
  )
}
