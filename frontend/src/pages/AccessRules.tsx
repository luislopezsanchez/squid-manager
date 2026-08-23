import { useState, useEffect } from 'react'
import { IconChevronDown, IconChevronUp, IconUsers } from '../components/Icons'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface AccessRule {
  id: number
  action: string
  acl_names: string
  order: number
  description: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

interface Acl {
  id: number
  name: string
  type: string
}

export default function AccessRules() {
  const [rules, setRules] = useState<AccessRule[]>([])
  const [acls, setAcls] = useState<Acl[]>([])
  const [groups, setGroups] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({ action: 'allow', acl_names: '', order: 0, description: '', enabled: true })
  const [error, setError] = useState('')
  const { showToast, ToastContainer } = useToast()

  const loadRules = () => {
    api.listAccessRules().then(setRules).catch(e => showToast('Error al cargar reglas', 'error')).finally(() => setLoading(false))
  }

  useEffect(() => {
    loadRules()
    api.listAcls().then(setAcls).catch(console.error)
    api.listGroups().then(setGroups).catch(() => {})
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      if (editingId) {
        await api.updateAccessRule(editingId, form)
        showToast(`Regla "${form.action} ${form.acl_names}" actualizada correctamente`)
      } else {
        await api.createAccessRule(form)
        showToast(`Regla "${form.action} ${form.acl_names}" creada correctamente`)
      }
      setForm({ action: 'allow', acl_names: '', order: rules.length, description: '', enabled: true })
      setEditingId(null)
      setShowForm(false)
      loadRules()
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    }
  }

  const handleEdit = (rule: AccessRule) => {
    setForm({ action: rule.action, acl_names: rule.acl_names, order: rule.order, description: rule.description || '', enabled: rule.enabled })
    setEditingId(rule.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar esta regla?')) return
    try {
      await api.deleteAccessRule(id)
      loadRules()
      showToast('Regla eliminada correctamente')
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const moveRule = async (index: number, direction: 'up' | 'down') => {
    const newRules = [...rules]
    const targetIndex = direction === 'up' ? index - 1 : index + 1
    if (targetIndex < 0 || targetIndex >= newRules.length) return
    ;[newRules[index], newRules[targetIndex]] = [newRules[targetIndex], newRules[index]]
    setRules(newRules)
    const ruleIds = newRules.map(r => r.id)
    try {
      await api.reorderRules(ruleIds)
      showToast('Orden de reglas actualizado')
    } catch (e: any) {
      showToast(`Error al reordenar: ${e.message}`, 'error')
      loadRules()
    }
  }

  const predefinedAcls = ['localnet', 'localhost', 'SSL_ports', 'Safe_ports', 'CONNECT', 'authenticated', 'all']
  const allAclNames = [...predefinedAcls, ...acls.map(a => a.name)]
  const groupNames = groups.map(g => g.name)

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Reglas de Acceso (http_access)</h1>
          <p className="page-sub">El orden importa: la primera regla que coincide determina el acceso</p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ action: 'allow', acl_names: '', order: rules.length, description: '', enabled: true }) }}
          className="btn btn-primary"
        >
          {showForm ? 'Cancelar' : '+ Nueva Regla'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSave} className="card p-6 mb-6">
          <h3 className="font-medium text-ink mb-4">{editingId ? 'Editar Regla' : 'Nueva Regla de Acceso'}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="field-label block mb-1.5">Acción</label>
              <select value={form.action} onChange={e => setForm({ ...form, action: e.target.value })}
                className="input">
                <option value="allow">allow (Permitir)</option>
                <option value="deny">deny (Denegar)</option>
              </select>
            </div>
            <div>
              <label className="field-label block mb-1.5">Orden</label>
              <input type="number" value={form.order} onChange={e => setForm({ ...form, order: parseInt(e.target.value) })}
                className="input" />
            </div>
          </div>
          <div className="mt-4">
            <label className="field-label block mb-1.5">ACLs (separadas por espacio)</label>
            <input type="text" value={form.acl_names} onChange={e => setForm({ ...form, acl_names: e.target.value })}
              placeholder="ej: localnet authenticated" className="input font-mono text-sm" required />
            <div className="mt-2 flex flex-wrap gap-2">
              {allAclNames.map(name => (
                <button key={name} type="button" onClick={() => {
                  const current = form.acl_names.trim()
                  setForm({ ...form, acl_names: current ? `${current} ${name}` : name })
                }}
                  className="px-2 py-1 bg-brand-50 text-brand-700 text-xs font-mono rounded hover:bg-blue-100">
                  {name}
                </button>
              ))}
              {groupNames.length > 0 && <span className="w-full text-xs text-ink-3 mt-1">Grupos de usuarios:</span>}
              {groupNames.map(name => (
                <button key={`g-${name}`} type="button" onClick={() => {
                  const current = form.acl_names.trim()
                  setForm({ ...form, acl_names: current ? `${current} ${name}` : name })
                }}
                  className="px-2 py-1 bg-emerald-50 text-emerald-700 text-xs font-mono rounded hover:bg-emerald-100 border border-emerald-200">
                  <IconUsers className="w-3.5 h-3.5 inline-block mr-1 -mt-0.5" />{name}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4">
            <label className="field-label block mb-1.5">Descripción (opcional)</label>
            <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder="ej: Permitir acceso a red local autenticada" className="input" />
          </div>
          {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <button type="submit" className="mt-4 btn btn-primary">
            {editingId ? 'Guardar Cambios' : 'Crear Regla'}
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12 text-ink-3">Cargando...</div>
      ) : (
        <div className="space-y-3">
          <div className="bg-line-soft rounded-xl p-4 border border-line">
            <h3 className="text-sm font-medium text-ink-3 mb-2">Reglas predefinidas (siempre activas):</h3>
            <div className="space-y-1 text-sm font-mono text-ink-3">
              <div>http_access deny !Safe_ports</div>
              <div>http_access deny CONNECT !SSL_ports</div>
              <div>http_access allow localhost manager</div>
              <div>http_access deny manager</div>
            </div>
          </div>

          {rules.map((rule, index) => (
            <div key={rule.id} className={`card p-4 flex items-center gap-4 ${!rule.enabled ? 'opacity-50' : ''}`}>
              <div className="flex flex-col gap-1">
                <button onClick={() => moveRule(index, 'up')} disabled={index === 0}
                  className="text-ink-3 hover:text-ink-2 disabled:opacity-20 p-1" aria-label="Subir"><IconChevronUp className="w-4 h-4" /></button>
                <button onClick={() => moveRule(index, 'down')} disabled={index === rules.length - 1}
                  className="text-ink-3 hover:text-ink-2 disabled:opacity-20 p-1" aria-label="Bajar"><IconChevronDown className="w-4 h-4" /></button>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className={`px-3 py-1 rounded-full text-sm font-bold ${rule.action === 'allow' ? 'pill-ok' : 'pill-danger'}`}>
                    {rule.action}
                  </span>
                  <span className="font-mono text-sm text-ink-2">{rule.acl_names}</span>
                </div>
                {rule.description && <p className="text-xs text-ink-3 mt-1">{rule.description}</p>}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-ink-3">#{rule.order}</span>
                <button onClick={() => handleEdit(rule)} className="text-primary-600 hover:text-primary-800 text-sm font-medium">Editar</button>
                <button onClick={() => handleDelete(rule.id)} className="text-danger hover:text-danger text-sm font-medium">Eliminar</button>
              </div>
            </div>
          ))}
          {rules.length === 0 && (
            <div className="card p-8 text-center text-ink-3">
              No hay reglas personalizadas. Squid usará las reglas por defecto (permitir autenticados, denegar el resto).
            </div>
          )}
        </div>
      )}
    </div>
  )
}