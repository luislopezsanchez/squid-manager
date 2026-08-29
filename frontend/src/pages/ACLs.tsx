import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface Acl {
  id: number
  name: string
  type: string
  value: string
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

export default function ACLs() {
  const [acls, setAcls] = useState<Acl[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({ name: '', type: 'dstdomain', value: '', description: '', enabled: true })
  const [error, setError] = useState('')
  const { showToast, ToastContainer } = useToast()

  const loadAcls = () => {
    api.listAcls().then(setAcls).catch(e => showToast(traducir("Error al cargar ACLs"), 'error')).finally(() => setLoading(false))
  }

  useEffect(() => { loadAcls() }, [])

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
      setForm({ name: '', type: 'dstdomain', value: '', description: '', enabled: true })
      setEditingId(null)
      setShowForm(false)
      loadAcls()
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    }
  }

  const handleEdit = (acl: Acl) => {
    setForm({ name: acl.name, type: acl.type, value: acl.value, description: acl.description || '', enabled: acl.enabled })
    setEditingId(acl.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm(traducir("¿Eliminar esta ACL?"))) return
    try {
      await api.deleteAcl(id)
      loadAcls()
      showToast(traducir("ACL eliminada correctamente"))
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const selectedType = ACL_TYPES.find(t => t.value === form.type)

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Listas de Control de Acceso (ACLs)")}</h1>
          <p className="page-sub">{traducir("Define qué tráfico coincide con cada criterio")}</p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ name: '', type: 'dstdomain', value: '', description: '', enabled: true }) }}
          className="btn btn-primary"
        >
          {showForm ? traducir('Cancelar') : traducir('+ Nueva ACL')}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSave} className="card p-6 mb-6">
          <h3 className="font-medium text-ink mb-4">{editingId ? traducir('Editar ACL') : traducir('Nueva ACL')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="field-label block mb-1.5">{traducir("Nombre")}</label>
              <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder={traducir("ej: redes_sociales")} className="input" required />
            </div>
            <div>
              <label className="field-label block mb-1.5">{traducir("Tipo de ACL")}</label>
              <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}
                className="input">
                {ACL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-4">
            <label className="field-label block mb-1.5">{traducir("Valor")}</label>
            <input type="text" value={form.value} onChange={e => setForm({ ...form, value: e.target.value })}
              placeholder={selectedType?.example || ''} className="input font-mono text-sm" required />
            {selectedType && <p className="text-xs text-ink-3 mt-1">Ejemplo: {selectedType.example}</p>}
          </div>
          <div className="mt-4">
            <label className="field-label block mb-1.5">{traducir("Descripción (opcional)")}</label>
            <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder={traducir("ej: Bloquear acceso a redes sociales")} className="input" />
          </div>
          {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <div className="mt-4 flex gap-3">
            <button type="submit" className="btn btn-primary">
              {editingId ? traducir('Guardar Cambios') : traducir('Crear ACL')}
            </button>
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
                <th className="text-left">{traducir("Tipo")}</th>
                <th className="text-left">{traducir("Valor")}</th>
                <th className="text-left">{traducir("Estado")}</th>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {acls.map(acl => (
                <tr key={acl.id} className="hover:bg-brand-50">
                  <td className="px-6 py-4 font-medium text-ink">{acl.name}</td>
                  <td className="px-6 py-4"><span className="px-2 py-1 bg-brand-50 text-brand-700 text-xs font-mono rounded">{acl.type}</span></td>
                  <td className="px-6 py-4 font-mono text-sm text-ink-2 max-w-xs truncate">{acl.value}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${acl.enabled ? 'pill-ok' : 'pill-danger'}`}>
                      {acl.enabled ? 'Activa' : 'Inactiva'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button onClick={() => handleEdit(acl)} className="text-primary-600 hover:text-primary-800 text-sm font-medium">{traducir("Editar")}</button>
                    <button onClick={() => handleDelete(acl.id)} className="text-danger hover:text-danger text-sm font-medium">{traducir("Eliminar")}</button>
                  </td>
                </tr>
              ))}
              {acls.length === 0 && (
                <tr><td colSpan={5} className="px-6 py-12 text-center text-ink-3">{traducir("No hay ACLs personalizadas. Las ACLs predefinidas (localnet, Safe_ports, etc.) ya están incluidas automáticamente.")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}