import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import RequiereAplicar from '../components/RequiereAplicar'
import { IconRefresh, IconUpload, IconEdit, IconTrash } from '../components/Icons'
import { LoadingState, ErrorState } from '../components/AsyncState'
import { normalizarNombreAcl } from '../utils/aclNames'

interface Categoria {
  id: number
  name: string
  display_name: string | null
  type: string
  value: string | null
  source: string
  line_count: number | null
  description: string | null
  enabled: boolean
  sync_url: string | null
  last_synced_at: string | null
  last_sync_status: string | null
}

export default function Categorias() {
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [showBulk, setShowBulk] = useState(false)
  const [editingCat, setEditingCat] = useState<Categoria | null>(null)
  const [form, setForm] = useState({ name: '', displayName: '', domains: '', description: '', enabled: true, desconectarSync: false })
  const [error, setError] = useState('')
  const { showToast, ToastContainer } = useToast()

  const cargar = () => {
    api.listAcls({ isCategory: true }).then(r => { setCategorias(r); setLoadError(false) })
      .catch(() => { showToast(traducir("Error al cargar las categorías"), 'error'); setLoadError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { cargar() }, [])

  const domainsANombres = (texto: string) =>
    texto.split(/[\s,]+/).map(d => d.trim()).filter(Boolean)

  const formVacio = { name: '', displayName: '', domains: '', description: '', enabled: true, desconectarSync: false }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const editandoArchivo = editingCat && editingCat.source === 'file'
    let dominios: string[] = []
    if (!editandoArchivo) {
      dominios = domainsANombres(form.domains)
      if (dominios.length === 0) {
        setError(traducir("Agregá al menos un dominio."))
        return
      }
    }

    try {
      const data: any = {
        display_name: form.displayName || '',
        description: form.description, enabled: form.enabled,
      }
      if (!editandoArchivo) {
        data.value = dominios.join(' ')
        data.type = 'dstdomain'
        data.is_category = true
      }
      if (editingCat) {
        if (form.desconectarSync) data.sync_url = ''
        await api.updateAcl(editingCat.id, data)
        showToast(traducir("Categoría actualizada correctamente"))
      } else {
        data.name = form.name
        await api.createAcl(data)
        showToast(traducir("Categoría creada correctamente"))
      }
      notificarCambioPendiente()
      setForm(formVacio)
      setEditingCat(null)
      setShowForm(false)
      cargar()
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    }
  }

  const handleEdit = (cat: Categoria) => {
    setForm({
      name: cat.name,
      displayName: cat.display_name || '',
      domains: cat.source === 'inline' ? (cat.value || '').split(' ').join('\n') : '',
      description: cat.description || '',
      enabled: cat.enabled,
      desconectarSync: false,
    })
    setEditingCat(cat)
    setShowForm(true)
    setShowBulk(false)
  }

  // --- Carga masiva desde archivo (crear nueva, o sumar/reemplazar una existente) ---
  const [bulkName, setBulkName] = useState('')
  const [bulkModo, setBulkModo] = useState<'reemplazar' | 'agregar'>('reemplazar')
  const [bulkDescription, setBulkDescription] = useState('')
  const [bulkBusy, setBulkBusy] = useState(false)
  const bulkFileRef = useRef<HTMLInputElement>(null)

  const handleOpenBulkFor = (cat: Categoria) => {
    setBulkName(cat.name)
    setBulkModo('agregar')
    setBulkDescription(cat.description || '')
    setShowBulk(true)
    setShowForm(false)
  }

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

  // --- Categorías predefinidas (HaGeZi) ---
  const [hagenziBusy, setHagenziBusy] = useState(false)

  const handleLoadHagezi = async () => {
    setHagenziBusy(true)
    try {
      const result = await api.loadHagenziPreset()
      notificarCambioPendiente()
      const exitosas = (result.resultados || []).filter((r: any) => r.ok).length
      showToast(
        traducir("Categorías de HaGeZi cargadas") + `: ${exitosas}/${(result.resultados || []).length}`
      )
      cargar()
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setHagenziBusy(false)
    }
  }

  const [syncingId, setSyncingId] = useState<number | null>(null)

  const handleSyncNow = async (id: number) => {
    setSyncingId(id)
    try {
      await api.syncCategoryNow(id)
      notificarCambioPendiente()
      cargar()
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setSyncingId(null)
    }
  }

  const editandoArchivo = !!editingCat && editingCat.source === 'file'

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-2 flex-wrap gap-3">
        <div>
          <h1 className="page-title">{traducir("Categorías de dominios")}</h1>
          <p className="page-sub">{traducir("Agrupá dominios bajo un nombre reutilizable (ej: Redes sociales, Streaming) para usarlos al crear reglas de acceso o límites de ancho de banda.")}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleLoadHagezi}
            disabled={hagenziBusy}
            className="btn btn-accent"
            title={traducir("Crea (o actualiza) 9 categorías ya armadas (apuestas, contenido adulto, piratería, redes sociales, sitios falsos, evasión del proxy, pop-ups, amenazas de seguridad y acortadores de URL), y las deja sincronizando solas una vez al día")}
          >
            {hagenziBusy ? traducir('Cargando…') : traducir('Cargar categorías predefinidas (HaGeZi)')}
          </button>
          <button
            onClick={() => { setShowBulk(!showBulk); setShowForm(false); if (!showBulk) { setBulkName(''); setBulkModo('reemplazar'); setBulkDescription('') } }}
            className="btn btn-outline"
            title={traducir("Para categorías grandes: un dominio por línea")}
          >
            {showBulk ? traducir('Cancelar') : traducir('Cargar desde archivo')}
          </button>
          <button
            onClick={() => { setShowForm(!showForm); setShowBulk(false); setEditingCat(null); setForm(formVacio) }}
            className="btn btn-primary"
          >
            {showForm ? traducir('Cancelar') : traducir('+ Nueva categoría')}
          </button>
        </div>
      </div>
      <p className="text-xs text-ink-3 mb-1">
        {traducir("Una categoría es, para Squid, una lista de dominios como cualquier otra — solo se muestra acá aparte, con un nombre más fácil de reconocer, en vez de mezclada con las ACLs técnicas de la página ACLs.")}
      </p>
      <p className="text-xs text-ink-3 mb-6">
        {traducir("«Cargar categorías predefinidas» trae 9 listas públicas de HaGeZi dns-blocklists (apuestas, contenido adulto, piratería, redes sociales, sitios falsos, evasión del proxy, pop-ups, amenazas de seguridad y acortadores de URL), con nombre técnico hagezi_* para conectarlas con la fuente original, pero se muestran en la tabla con un nombre más legible. Se actualizan solas una vez al día, sumando dominios nuevos sin borrar los que agregues vos a mano.")}
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
          <h3 className="font-medium text-ink mb-4">{editingCat ? traducir('Editar categoría') : traducir('Nueva categoría')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="cat-name" className="field-label block mb-1.5">{traducir("Nombre")}</label>
              <input id="cat-name" type="text" value={form.name} onChange={e => setForm({ ...form, name: normalizarNombreAcl(e.target.value) })}
                placeholder={traducir("ej: redes_sociales")} className="input font-mono text-sm" required disabled={!!editingCat} />
              <p className="text-xs text-ink-3 mt-1">{traducir("Identificador técnico — se ajusta solo a minúsculas y guiones bajos, sin espacios ni acentos. No se puede cambiar después de creada.")}</p>
            </div>
            <div>
              <label htmlFor="cat-display-name" className="field-label block mb-1.5">{traducir("Nombre para mostrar (opcional)")}</label>
              <input id="cat-display-name" type="text" value={form.displayName} onChange={e => setForm({ ...form, displayName: e.target.value })}
                placeholder={traducir("ej: Redes sociales")} className="input" />
              <p className="text-xs text-ink-3 mt-1">{traducir("Este es el que se ve en la tabla. Vacío = se muestra el nombre técnico.")}</p>
            </div>
          </div>

          {editandoArchivo ? (
            <div className="mt-4 rounded-lg border border-line bg-brand-50 p-4 text-sm text-ink-3">
              {traducir("Esta categoría tiene muchos dominios guardados en un archivo aparte. Para cambiar la lista, usá el ícono de subir archivo (")}
              <IconUpload className="inline w-3.5 h-3.5 align-text-bottom mx-0.5" />
              {traducir(") en la tabla")}
              {editingCat?.sync_url && traducir(', o "Sincronizar ahora" si es automática')}.
            </div>
          ) : (
            <div className="mt-4">
              <label htmlFor="cat-domains" className="field-label block mb-1.5">{traducir("Dominios (uno por línea)")}</label>
              <textarea id="cat-domains" rows={6} value={form.domains} onChange={e => setForm({ ...form, domains: e.target.value })}
                placeholder={".facebook.com\n.instagram.com\n.tiktok.com"} className="input font-mono text-sm" required />
            </div>
          )}

          <div className="mt-4">
            <label htmlFor="cat-description" className="field-label block mb-1.5">{traducir("Descripción (opcional)")}</label>
            <input id="cat-description" type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder={traducir("ej: Redes sociales más usadas")} className="input" />
          </div>

          <label className="mt-4 flex items-center gap-2 cursor-pointer w-fit">
            <input type="checkbox" checked={form.enabled} onChange={e => setForm({ ...form, enabled: e.target.checked })}
              className="w-5 h-5 rounded text-primary-600" />
            <span className="text-sm text-ink-2">{traducir("Activa")}</span>
          </label>

          {editingCat?.sync_url && (
            <label className="mt-3 flex items-center gap-2 cursor-pointer w-fit">
              <input type="checkbox" checked={form.desconectarSync} onChange={e => setForm({ ...form, desconectarSync: e.target.checked })}
                className="w-5 h-5 rounded text-primary-600" />
              <span className="text-sm text-ink-2">{traducir("Dejar de sincronizar automáticamente")}</span>
            </label>
          )}

          {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <div className="mt-4 flex items-center gap-3">
            <button type="submit" className="btn btn-primary">
              {editingCat ? traducir('Guardar Cambios') : traducir('Crear categoría')}
            </button>
            <RequiereAplicar />
          </div>
        </form>
      )}

      {loading ? (
        <LoadingState />
      ) : loadError && categorias.length === 0 ? (
        <ErrorState onRetry={cargar} />
      ) : (
        <div className="card overflow-hidden">
          <table className="table-panel">
            <thead>
              <tr>
                <th className="text-left">{traducir("Nombre")}</th>
                <th className="text-left">{traducir("Descripción")}</th>
                <th className="text-left">{traducir("Dominios")}</th>
                <th className="text-left">{traducir("Estado")}</th>
                <th className="text-left">{traducir("Sincronización")}</th>
                <th className="text-right">{traducir("Acciones")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {categorias.map(cat => (
                <tr key={cat.id} className="hover:bg-brand-50">
                  <td className="px-6 py-4">
                    <div className="font-medium text-ink">{cat.display_name || cat.name}</div>
                    {cat.display_name && cat.display_name !== cat.name && (
                      <div className="text-xs text-ink-3 font-mono mt-0.5">{cat.name}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-ink-2">{cat.description || '—'}</td>
                  <td className="px-6 py-4 font-mono text-sm text-ink-2">
                    {cat.source === 'file'
                      ? `${(cat.line_count ?? 0).toLocaleString()} ${traducir('dominios')}`
                      : `${(cat.value || '').split(' ').filter(Boolean).length} ${traducir('dominio' + ((cat.value || '').split(' ').filter(Boolean).length === 1 ? '' : 's'))}`}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${cat.enabled ? 'pill-ok' : 'pill-danger'}`}>
                      {cat.enabled ? traducir('Activa') : traducir('Inactiva')}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-xs text-ink-3">
                    {cat.sync_url ? (
                      <div>
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${cat.last_sync_status?.startsWith('Error') || cat.last_sync_status?.includes('ningún dominio') ? 'pill-danger' : 'pill-ok'}`}>
                          {traducir('Automática')}
                        </span>
                        <p className="mt-1">
                          {cat.last_synced_at
                            ? `${traducir('Última vez')}: ${new Date(cat.last_synced_at).toLocaleString()}`
                            : traducir('Todavía no se sincronizó')}
                        </p>
                        {cat.last_sync_status && <p className="text-ink-3">{cat.last_sync_status}</p>}
                      </div>
                    ) : (
                      <span>{traducir('Manual')}</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {cat.sync_url && (
                        <button onClick={() => handleSyncNow(cat.id)} disabled={syncingId === cat.id}
                          className="btn-icon" title={syncingId === cat.id ? traducir('Sincronizando…') : traducir('Sincronizar ahora')}>
                          <IconRefresh className={syncingId === cat.id ? 'animate-spin' : ''} />
                        </button>
                      )}
                      <button onClick={() => handleOpenBulkFor(cat)} className="btn-icon" title={traducir('Actualizar lista desde archivo')}>
                        <IconUpload />
                      </button>
                      <button onClick={() => handleEdit(cat)} className="btn-icon" title={traducir('Editar')}>
                        <IconEdit />
                      </button>
                      <button onClick={() => handleDelete(cat.id)} className="btn-icon btn-icon-danger" title={traducir('Eliminar')}>
                        <IconTrash />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {categorias.length === 0 && (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-ink-3">{traducir("Todavía no hay categorías. Creá una para agrupar dominios bajo un nombre reutilizable.")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
