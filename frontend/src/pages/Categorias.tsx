import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import RequiereAplicar from '../components/RequiereAplicar'

// Los nombres de ACL de Squid no admiten espacios, mayúsculas ni acentos
// (regex del backend: ^[A-Za-z][A-Za-z0-9_-]{0,63}$, ver squid_names.py).
// En vez de dejar que el admin escriba "Redes Sociales" y recién enterarse
// del error al guardar, se normaliza en vivo mientras escribe -mismo patrón
// que un campo de "slug" de URL en cualquier CMS.
function normalizarNombreAcl(texto: string): string {
  return texto
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^[^a-z]+/, '')
    .replace(/_+$/, '')
    .slice(0, 64)
}

interface Categoria {
  id: number
  name: string
  type: string
  value: string | null
  source: string
  line_count: number | null
  description: string | null
  enabled: boolean
}

export default function Categorias() {
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [showBulk, setShowBulk] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({ name: '', domains: '', description: '', enabled: true })
  const [error, setError] = useState('')
  const { showToast, ToastContainer } = useToast()

  const cargar = () => {
    api.listAcls({ isCategory: true }).then(setCategorias)
      .catch(() => showToast(traducir("Error al cargar las categorías"), 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { cargar() }, [])

  const domainsANombres = (texto: string) =>
    texto.split(/[\s,]+/).map(d => d.trim()).filter(Boolean)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const dominios = domainsANombres(form.domains)
    if (dominios.length === 0) {
      setError(traducir("Agregá al menos un dominio."))
      return
    }
    try {
      const data = {
        name: form.name, type: 'dstdomain', value: dominios.join(' '),
        description: form.description, enabled: form.enabled, is_category: true,
      }
      if (editingId) {
        await api.updateAcl(editingId, data)
        showToast(traducir("Categoría actualizada correctamente"))
      } else {
        await api.createAcl(data)
        showToast(traducir("Categoría creada correctamente"))
      }
      notificarCambioPendiente()
      setForm({ name: '', domains: '', description: '', enabled: true })
      setEditingId(null)
      setShowForm(false)
      cargar()
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    }
  }

  const handleEdit = (cat: Categoria) => {
    if (cat.source === 'file') {
      setBulkName(cat.name)
      setBulkModo('reemplazar')
      setShowBulk(true)
      setShowForm(false)
      return
    }
    setForm({ name: cat.name, domains: (cat.value || '').split(' ').join('\n'), description: cat.description || '', enabled: cat.enabled })
    setEditingId(cat.id)
    setShowForm(true)
    setShowBulk(false)
  }

  // --- Carga masiva desde archivo ---
  const [bulkName, setBulkName] = useState('')
  const [bulkModo, setBulkModo] = useState<'reemplazar' | 'agregar'>('reemplazar')
  const [bulkDescription, setBulkDescription] = useState('')
  const [bulkBusy, setBulkBusy] = useState(false)
  const bulkFileRef = useRef<HTMLInputElement>(null)

  const handleBulkUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    const file = bulkFileRef.current?.files?.[0]
    if (!file || !bulkName.trim()) return
    setBulkBusy(true)
    try {
      const result = await api.bulkUploadDomains(file, bulkName.trim(), bulkModo, 'dstdomain', bulkDescription || undefined, true)
      notificarCambioPendiente()
      showToast(
        `"${bulkName}": ${result.dominios_importados} ${traducir('dominios')}` +
        (result.total_rechazados > 0 ? `, ${result.total_rechazados} ${traducir('línea(s) rechazada(s)')}` : '')
      )
      setShowBulk(false)
      setBulkName('')
      setBulkDescription('')
      if (bulkFileRef.current) bulkFileRef.current.value = ''
      cargar()
    } catch (err: any) {
      showToast(`Error: ${err.message}`, 'error')
    } finally {
      setBulkBusy(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm(traducir("¿Eliminar esta categoría?"))) return
    try {
      await api.deleteAcl(id)
      notificarCambioPendiente()
      cargar()
      showToast(traducir("Categoría eliminada correctamente"))
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="page-title">{traducir("Categorías de dominios")}</h1>
          <p className="page-sub">{traducir("Agrupá dominios bajo un nombre reutilizable (ej: Redes sociales, Streaming) para usarlos al crear reglas de acceso o límites de ancho de banda.")}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowBulk(!showBulk); setShowForm(false) }}
            className="btn btn-ghost"
            title={traducir("Para categorías grandes: un dominio por línea")}
          >
            {showBulk ? traducir('Cancelar') : traducir('Cargar desde archivo')}
          </button>
          <button
            onClick={() => { setShowForm(!showForm); setShowBulk(false); setEditingId(null); setForm({ name: '', domains: '', description: '', enabled: true }) }}
            className="btn btn-primary"
          >
            {showForm ? traducir('Cancelar') : traducir('+ Nueva categoría')}
          </button>
        </div>
      </div>
      <p className="text-xs text-ink-3 mb-6">
        {traducir("Una categoría es, para Squid, una lista de dominios como cualquier otra — solo se muestra acá aparte, con un nombre más fácil de reconocer, en vez de mezclada con las ACLs técnicas de la página ACLs.")}
      </p>

      {showBulk && (
        <form onSubmit={handleBulkUpload} className="card p-6 mb-6">
          <h3 className="font-medium text-ink mb-1">{traducir('Cargar categoría desde archivo')}</h3>
          <p className="text-xs text-ink-3 mb-4">
            {traducir('Un dominio por línea (líneas vacías o que empiezan con # se ignoran). Listas grandes se guardan en un archivo aparte que Squid lee directo.')}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="cat-bulk-name" className="field-label block mb-1.5">{traducir("Nombre de la categoría")}</label>
              <input id="cat-bulk-name" type="text" value={bulkName} onChange={e => setBulkName(normalizarNombreAcl(e.target.value))}
                placeholder={traducir("ej: redes_sociales")} className="input font-mono text-sm" required
                list="cat-bulk-name-existentes" autoComplete="off" />
              <datalist id="cat-bulk-name-existentes">
                {categorias.map(c => <option key={c.id} value={c.name} />)}
              </datalist>
              <p className="text-xs text-ink-3 mt-1">
                {traducir("Se ajusta solo a minúsculas y guiones bajos mientras escribís, sin espacios ni acentos.")}{' '}
                {traducir("Elegí una de la lista para sumarle dominios a una categoría existente — escribir un nombre nuevo crea una categoría aparte, aunque se parezca a una que ya tenías.")}
              </p>
            </div>
            <div>
              <label htmlFor="cat-bulk-modo" className="field-label block mb-1.5">{traducir("Si la categoría ya existe")}</label>
              <select id="cat-bulk-modo" value={bulkModo} onChange={e => setBulkModo(e.target.value as any)} className="input">
                <option value="reemplazar">{traducir('Reemplazar toda la lista')}</option>
                <option value="agregar">{traducir('Agregar a lo que ya había')}</option>
              </select>
            </div>
          </div>
          <div className="mt-4">
            <label htmlFor="cat-bulk-description" className="field-label block mb-1.5">{traducir("Descripción (opcional)")}</label>
            <input id="cat-bulk-description" type="text" value={bulkDescription} onChange={e => setBulkDescription(e.target.value)}
              placeholder={traducir("ej: Redes sociales más usadas")} className="input" />
          </div>
          <div className="mt-4">
            <label htmlFor="cat-bulk-file" className="field-label block mb-1.5">{traducir("Archivo")}</label>
            <input id="cat-bulk-file" ref={bulkFileRef} type="file" accept=".txt,.csv,text/plain" className="input" required />
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button type="submit" disabled={bulkBusy} className="btn btn-primary">
              {bulkBusy ? traducir('Cargando…') : traducir('Cargar')}
            </button>
            <RequiereAplicar />
          </div>
        </form>
      )}

      {showForm && (
        <form onSubmit={handleSave} className="card p-6 mb-6">
          <h3 className="font-medium text-ink mb-4">{editingId ? traducir('Editar categoría') : traducir('Nueva categoría')}</h3>
          <div>
            <label htmlFor="cat-name" className="field-label block mb-1.5">{traducir("Nombre")}</label>
            <input id="cat-name" type="text" value={form.name} onChange={e => setForm({ ...form, name: normalizarNombreAcl(e.target.value) })}
              placeholder={traducir("ej: redes_sociales")} className="input font-mono text-sm" required disabled={!!editingId} />
            <p className="text-xs text-ink-3 mt-1">{traducir("Se ajusta solo a minúsculas y guiones bajos mientras escribís, sin espacios ni acentos — es el identificador técnico, usá la descripción de abajo para un nombre más legible.")}</p>
          </div>
          <div className="mt-4">
            <label htmlFor="cat-domains" className="field-label block mb-1.5">{traducir("Dominios (uno por línea)")}</label>
            <textarea id="cat-domains" rows={6} value={form.domains} onChange={e => setForm({ ...form, domains: e.target.value })}
              placeholder={".facebook.com\n.instagram.com\n.tiktok.com"} className="input font-mono text-sm" required />
          </div>
          <div className="mt-4">
            <label htmlFor="cat-description" className="field-label block mb-1.5">{traducir("Descripción (opcional)")}</label>
            <input id="cat-description" type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder={traducir("ej: Redes sociales más usadas")} className="input" />
          </div>
          {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <div className="mt-4 flex items-center gap-3">
            <button type="submit" className="btn btn-primary">
              {editingId ? traducir('Guardar Cambios') : traducir('Crear categoría')}
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
                <th className="text-left">{traducir("Descripción")}</th>
                <th className="text-left">{traducir("Dominios")}</th>
                <th className="text-left">{traducir("Estado")}</th>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {categorias.map(cat => (
                <tr key={cat.id} className="hover:bg-brand-50">
                  <td className="px-6 py-4 font-medium text-ink">{cat.name}</td>
                  <td className="px-6 py-4 text-sm text-ink-2">{cat.description || '—'}</td>
                  <td className="px-6 py-4 font-mono text-sm text-ink-2">
                    {cat.source === 'file'
                      ? `${(cat.line_count ?? 0).toLocaleString()} ${traducir('dominios')}`
                      : `${(cat.value || '').split(' ').filter(Boolean).length} ${traducir('dominios')}`}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${cat.enabled ? 'pill-ok' : 'pill-danger'}`}>
                      {cat.enabled ? traducir('Activa') : traducir('Inactiva')}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button onClick={() => handleEdit(cat)} className="text-primary-600 hover:text-primary-800 text-sm font-medium">
                      {cat.source === 'file' ? traducir('Reemplazar') : traducir('Editar')}
                    </button>
                    <button onClick={() => handleDelete(cat.id)} className="text-danger hover:text-danger text-sm font-medium">{traducir("Eliminar")}</button>
                  </td>
                </tr>
              ))}
              {categorias.length === 0 && (
                <tr><td colSpan={5} className="px-6 py-12 text-center text-ink-3">{traducir("Todavía no hay categorías. Creá una para agrupar dominios bajo un nombre reutilizable.")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
