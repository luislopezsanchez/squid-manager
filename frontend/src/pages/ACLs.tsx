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
  { value: 'src', label: 'IP de origen (src)', example: '192.168.1.0/24' },
  { value: 'dst', label: 'IP de destino (dst)', example: '10.0.0.0/8' },
  { value: 'dstdomain', label: 'Dominio de destino (dstdomain)', example: '.facebook.com' },
  { value: 'dstdom_regex', label: 'Regex de dominio (dstdom_regex)', example: '\\.social\\.' },
  { value: 'url_regex', label: 'Regex de URL (url_regex)', example: '\\.mp4$' },
  { value: 'urlpath_regex', label: 'Regex de path URL (urlpath_regex)', example: '/download/' },
  { value: 'port', label: 'Puerto destino (port)', example: '443 80' },
  { value: 'proto', label: 'Protocolo (proto)', example: 'HTTP FTP' },
  { value: 'method', label: 'Método HTTP (method)', example: 'GET POST' },
  { value: 'time', label: 'Horario (time)', example: 'M-F 09:00-17:00' },
  { value: 'proxy_auth', label: 'Usuario autenticado (proxy_auth)', example: 'REQUIRED' },
  { value: 'maxconn', label: 'Conexiones máximas (maxconn)', example: '10' },
  { value: 'browser', label: 'User-Agent (browser)', example: 'Chrome' },
  { value: 'rep_mime_type', label: 'MIME type de respuesta (rep_mime_type)', example: 'video/' },
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
    api.listAcls().then(setAcls).catch(e => showToast('Error al cargar ACLs', 'error')).finally(() => setLoading(false))
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
    if (!confirm('¿Eliminar esta ACL?')) return
    try {
      await api.deleteAcl(id)
      loadAcls()
      showToast('ACL eliminada correctamente')
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const selectedType = ACL_TYPES.find(t => t.value === form.type)

  return (
    <div className="p-8">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Listas de Control de Acceso (ACLs)</h1>
          <p className="text-sm text-gray-500 mt-1">Define qué tráfico coincide con cada criterio</p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ name: '', type: 'dstdomain', value: '', description: '', enabled: true }) }}
          className="bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 transition"
        >
          {showForm ? 'Cancelar' : '+ Nueva ACL'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSave} className="bg-white rounded-xl shadow-sm p-6 mb-6 border border-gray-100">
          <h3 className="font-medium text-gray-900 mb-4">{editingId ? 'Editar ACL' : 'Nueva ACL'}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
              <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder="ej: redes_sociales" className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de ACL</label>
              <select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 bg-white">
                {ACL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Valor</label>
            <input type="text" value={form.value} onChange={e => setForm({ ...form, value: e.target.value })}
              placeholder={selectedType?.example || ''} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm" required />
            {selectedType && <p className="text-xs text-gray-400 mt-1">Ejemplo: {selectedType.example}</p>}
          </div>
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Descripción (opcional)</label>
            <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder="ej: Bloquear acceso a redes sociales" className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500" />
          </div>
          {error && <div className="mt-4 bg-red-50 text-red-600 text-sm p-3 rounded-lg">{error}</div>}
          <div className="mt-4 flex gap-3">
            <button type="submit" className="bg-primary-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-primary-700">
              {editingId ? 'Guardar Cambios' : 'Crear ACL'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Cargando...</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Nombre</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Tipo</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Valor</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {acls.map(acl => (
                <tr key={acl.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">{acl.name}</td>
                  <td className="px-6 py-4"><span className="px-2 py-1 bg-blue-50 text-blue-700 text-xs font-mono rounded">{acl.type}</span></td>
                  <td className="px-6 py-4 font-mono text-sm text-gray-600 max-w-xs truncate">{acl.value}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${acl.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                      {acl.enabled ? 'Activa' : 'Inactiva'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button onClick={() => handleEdit(acl)} className="text-primary-600 hover:text-primary-800 text-sm font-medium">Editar</button>
                    <button onClick={() => handleDelete(acl.id)} className="text-red-600 hover:text-red-800 text-sm font-medium">Eliminar</button>
                  </td>
                </tr>
              ))}
              {acls.length === 0 && (
                <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  No hay ACLs personalizadas. Las ACLs predefinidas (localnet, Safe_ports, etc.) ya están incluidas automáticamente.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}