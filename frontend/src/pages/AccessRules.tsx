import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { IconUsers, IconGripVertical, IconChevronUp, IconChevronDown, IconShield } from '../components/Icons'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'
import RequiereAplicar from '../components/RequiereAplicar'
import Modal from '../components/Modal'
import { confirmar } from '../components/ConfirmDialog'

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

type FormRule = { action: string; acl_names: string; order: number; description: string; enabled: boolean }

function RuleFormModal({ form, setForm, editingId, allAclNames, groupNames, onClose, onSubmit, error }: {
  form: FormRule
  setForm: (f: FormRule) => void
  editingId: number | null
  allAclNames: string[]
  groupNames: string[]
  onClose: () => void
  onSubmit: (e: React.FormEvent) => void
  error: string
}) {
  const [aclSearch, setAclSearch] = useState('')
  const term = aclSearch.trim().toLowerCase()
  const aclNamesFiltradas = term ? allAclNames.filter(n => n.toLowerCase().includes(term)) : allAclNames
  const groupNamesFiltrados = term ? groupNames.filter(n => n.toLowerCase().includes(term)) : groupNames

  const agregarNombre = (name: string) => {
    const current = form.acl_names.trim()
    setForm({ ...form, acl_names: current ? `${current} ${name}` : name })
  }

  return (
    <Modal title={editingId ? traducir('Editar Regla') : traducir('Nueva Regla de Acceso')} onClose={onClose} maxWidth="max-w-3xl">
      <form onSubmit={onSubmit}>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label htmlFor="rule-action" className="field-label block mb-1.5">{traducir("Acción")}</label>
            <select id="rule-action" value={form.action} onChange={e => setForm({ ...form, action: e.target.value })}
              className="input">
              <option value="allow">{traducir("allow (Permitir)")}</option>
              <option value="deny">{traducir("deny (Denegar)")}</option>
            </select>
          </div>
          <div>
            <label htmlFor="rule-order" className="field-label block mb-1.5" title={traducir("Posición en la que se evalúa: la que ya esté ahí (y las siguientes) se corren un lugar. Después de creada, se reordena arrastrando la tarjeta.")}>
              {traducir("Posición")}
            </label>
            <input id="rule-order" type="number" min={0} value={form.order}
              onChange={e => setForm({ ...form, order: Math.max(0, parseInt(e.target.value) || 0) })}
              className="input w-20 text-center" />
          </div>
        </div>
        <div className="mt-4">
          <label htmlFor="rule-acl-names" className="field-label block mb-1.5">{traducir("ACLs (separadas por espacio)")}</label>
          <input id="rule-acl-names" type="text" value={form.acl_names} onChange={e => setForm({ ...form, acl_names: e.target.value })}
            placeholder={traducir("ej: localnet authenticated")} className="input font-mono text-sm" required />

          <input
            type="text"
            value={aclSearch}
            onChange={e => setAclSearch(e.target.value)}
            placeholder={traducir("Buscar ACL o grupo para añadir…")}
            className="input mt-2 text-sm"
          />
          <div className="mt-2 max-h-40 overflow-y-auto flex flex-wrap gap-2 content-start border border-line-soft rounded-lg p-2">
            {aclNamesFiltradas.map(name => (
              <button key={name} type="button" onClick={() => agregarNombre(name)}
                className="px-2 py-1 bg-brand-50 text-brand-700 text-xs font-mono rounded hover:bg-blue-100">
                {name}
              </button>
            ))}
            {groupNamesFiltrados.length > 0 && <span className="w-full text-xs text-ink-3 mt-1">{traducir("Grupos de usuarios:")}</span>}
            {groupNamesFiltrados.map(name => (
              <button key={`g-${name}`} type="button" onClick={() => agregarNombre(name)}
                className="px-2 py-1 bg-emerald-50 text-emerald-700 text-xs font-mono rounded hover:bg-emerald-100 border border-emerald-200">
                <IconUsers className="w-3.5 h-3.5 inline-block mr-1 -mt-0.5" />{name}
              </button>
            ))}
            {aclNamesFiltradas.length === 0 && groupNamesFiltrados.length === 0 && (
              <span className="text-xs text-ink-3 p-1">{traducir("Ninguna ACL ni grupo coincide con la búsqueda.")}</span>
            )}
          </div>
        </div>
        <div className="mt-4">
          <label htmlFor="rule-description" className="field-label block mb-1.5">{traducir("Descripción (opcional)")}</label>
          <input id="rule-description" type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
            placeholder={traducir("ej: Permitir acceso a red local autenticada")} className="input" />
        </div>
        {error && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
        <div className="mt-5 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <button type="submit" className="btn btn-primary">
              {editingId ? traducir('Guardar Cambios') : traducir('Crear Regla')}
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

export default function AccessRules() {
  const [rules, setRules] = useState<AccessRule[]>([])
  const [acls, setAcls] = useState<Acl[]>([])
  const [groups, setGroups] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<FormRule>({ action: 'allow', acl_names: '', order: 0, description: '', enabled: true })
  const [error, setError] = useState('')
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const { showToast, ToastContainer } = useToast()

  const loadRules = () => {
    api.listAccessRules().then(r => { setRules(r); setLoadError(false) })
      .catch(e => { showToast(traducir("Error al cargar reglas"), 'error'); setLoadError(true) })
      .finally(() => setLoading(false))
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
      notificarCambioPendiente()
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
    if (!(await confirmar(traducir("¿Eliminar esta regla?")))) return
    try {
      await api.deleteAccessRule(id)
      notificarCambioPendiente()
      loadRules()
      showToast(traducir("Regla eliminada correctamente"))
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const aplicarNuevoOrden = async (newRules: AccessRule[]) => {
    setRules(newRules)
    try {
      await api.reorderRules(newRules.map(r => r.id))
      notificarCambioPendiente()
      showToast(traducir("Orden de reglas actualizado"))
    } catch (e: any) {
      showToast(`Error al reordenar: ${e.message}`, 'error')
      loadRules()
    }
  }

  const moveRule = (index: number, direction: 'up' | 'down') => {
    const newRules = [...rules]
    const targetIndex = direction === 'up' ? index - 1 : index + 1
    if (targetIndex < 0 || targetIndex >= newRules.length) return
    ;[newRules[index], newRules[targetIndex]] = [newRules[targetIndex], newRules[index]]
    aplicarNuevoOrden(newRules)
  }

  // Arrastrar y soltar: alternativa a los botones subir/bajar, más rápida
  // cuando hay que mover una regla varios lugares de una vez. Drag & drop
  // nativo de HTML5 (sin librería): onDragStart guarda qué fila se está
  // moviendo, onDrop la reinserta donde se soltó y manda el mismo
  // PUT /reorder que ya usaban las flechas.
  const handleDrop = (index: number) => {
    if (dragIndex === null || dragIndex === index) { setDragIndex(null); setOverIndex(null); return }
    const newRules = [...rules]
    const [movida] = newRules.splice(dragIndex, 1)
    newRules.splice(index, 0, movida)
    setDragIndex(null)
    setOverIndex(null)
    aplicarNuevoOrden(newRules)
  }

  const predefinedAcls = ['localnet', 'localhost', 'SSL_ports', 'Safe_ports', 'CONNECT', 'authenticated', 'all']
  const allAclNames = [...predefinedAcls, ...acls.map(a => a.name)]
  const groupNames = groups.map(g => g.name)

  // Filtra por ACL/grupo, descripción, acción u orden -búsqueda a nivel de
  // página, distinta de la que ya existe DENTRO del modal para elegir
  // ACLs/grupos al armar una regla. Reordenar (arrastrar o flechas) se
  // deshabilita mientras hay un término activo: "subir" o "bajar" sobre un
  // subconjunto filtrado saltearía por encima de reglas ocultas, dando un
  // resultado distinto al que se ve en pantalla.
  const term = search.trim().toLowerCase()
  const filteredRules = term
    ? rules.filter(r =>
        r.acl_names.toLowerCase().includes(term) ||
        (r.description ?? '').toLowerCase().includes(term) ||
        r.action.toLowerCase().includes(term) ||
        String(r.order).includes(term)
      )
    : rules

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{traducir("Reglas de Acceso (http_access)")}</h1>
          <p className="page-sub">{traducir("El orden importa: la primera regla que coincide determina el acceso")}</p>
        </div>
        <button
          onClick={() => { setEditingId(null); setForm({ action: 'allow', acl_names: '', order: rules.length, description: '', enabled: true }); setShowForm(true) }}
          className="btn btn-primary"
        >
          {traducir('+ Nueva Regla')}
        </button>
      </div>

      {showForm && (
        <RuleFormModal
          form={form} setForm={setForm} editingId={editingId}
          allAclNames={allAclNames} groupNames={groupNames}
          onClose={() => setShowForm(false)}
          onSubmit={handleSave}
          error={error}
        />
      )}

      {loading ? (
        <LoadingState />
      ) : loadError && rules.length === 0 ? (
        <ErrorState onRetry={loadRules} />
      ) : (
        <div className="space-y-3">
          <details className="bg-line-soft rounded-xl border border-line group">
            <summary className="cursor-pointer select-none p-4 flex items-center gap-2 text-sm font-medium text-ink-2">
              <IconShield className="w-4 h-4 text-ink-3" />
              {traducir("Protecciones básicas de Squid (siempre activas)")}
              <span className="ml-auto text-xs font-normal text-ink-3 group-open:hidden">{traducir("Ver qué hacen")}</span>
            </summary>
            <div className="px-4 pb-4 text-[13px] text-ink-3 space-y-3">
              <p>{traducir("Squid las evalúa siempre primero, antes de tus reglas. Protegen al proxy de usos peligrosos y no se pueden quitar ni reordenar; tus reglas actúan sobre lo que estas dejan pasar.")}</p>
              {[
                ['http_access deny !Safe_ports', "Bloquea las peticiones a puertos que no son de navegación web normal. Solo deja pasar 80, 443, 21, 70, 210, 280, 488, 591 y 1025-65535. Evita que el proxy se use para llegar a servicios internos por puertos de sistema (22 SSH, 25 correo, 3306 base de datos...)."],
                ['http_access deny CONNECT !SSL_ports', "Los túneles HTTPS (método CONNECT) solo se permiten hacia el puerto 443. Sin esto, cualquiera con acceso al proxy podría abrir un túnel hacia cualquier puerto, por ejemplo un SSH externo."],
                ['http_access allow localhost manager', "Las estadísticas internas de Squid (el «Cache Manager», que usa este panel para mostrar el estado del caché) solo se pueden consultar desde el propio servidor."],
                ['http_access deny manager', "Cualquier otro equipo que intente leer esas estadísticas internas es rechazado."],
              ].map(([regla, explicacion]) => (
                <div key={regla}>
                  <div className="font-mono text-ink-2">{regla}</div>
                  <div>{traducir(explicacion)}</div>
                </div>
              ))}
            </div>
          </details>

          {rules.length > 0 && (
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={traducir("Buscar por ACL, grupo, descripción, acción u orden…")}
              className="input w-full sm:max-w-sm"
            />
          )}

          {rules.length > 1 && (
            term
              ? <p className="text-xs text-ink-3">{traducir("Reordenar (arrastrar o flechas) se deshabilita mientras hay una búsqueda activa.")}</p>
              : (
                <p className="text-xs text-ink-3 flex items-center gap-1.5">
                  <IconGripVertical className="w-3.5 h-3.5" />
                  {traducir("Arrastrá una regla desde el ícono de la izquierda para reordenarla, o usá las flechas.")}
                </p>
              )
          )}

          {filteredRules.map(rule => {
            const index = rules.indexOf(rule)
            return (
            <div
              key={rule.id}
              draggable={!term}
              onDragStart={() => setDragIndex(index)}
              onDragOver={e => { e.preventDefault(); if (overIndex !== index) setOverIndex(index) }}
              onDragEnd={() => { setDragIndex(null); setOverIndex(null) }}
              onDrop={() => handleDrop(index)}
              className={`card p-4 flex items-center gap-4 transition ${!rule.enabled ? 'opacity-50' : ''} ${
                dragIndex === index ? 'opacity-40' : ''
              } ${overIndex === index && dragIndex !== null && dragIndex !== index ? 'ring-2 ring-brand-400' : ''}`}
            >
              {!term && (
                <>
                  <span className="text-ink-3 cursor-grab active:cursor-grabbing" aria-hidden="true">
                    <IconGripVertical className="w-4 h-4" />
                  </span>
                  <div className="flex flex-col gap-1">
                    <button onClick={() => moveRule(index, 'up')} disabled={index === 0}
                      className="text-ink-3 hover:text-ink-2 disabled:opacity-20 p-1" aria-label={traducir("Subir")}><IconChevronUp className="w-4 h-4" /></button>
                    <button onClick={() => moveRule(index, 'down')} disabled={index === rules.length - 1}
                      className="text-ink-3 hover:text-ink-2 disabled:opacity-20 p-1" aria-label={traducir("Bajar")}><IconChevronDown className="w-4 h-4" /></button>
                  </div>
                </>
              )}
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
                <button onClick={() => handleEdit(rule)} className="text-primary-600 hover:text-primary-800 text-sm font-medium">{traducir("Editar")}</button>
                <button onClick={() => handleDelete(rule.id)} className="text-danger hover:text-danger text-sm font-medium">{traducir("Eliminar")}</button>
              </div>
            </div>
            )
          })}
          {rules.length === 0 && (
            <div className="card p-8 text-center text-ink-3">{traducir("No hay reglas personalizadas. Squid usará las reglas por defecto (permitir autenticados, denegar el resto).")}</div>
          )}
          {rules.length > 0 && filteredRules.length === 0 && (
            <div className="card p-8 text-center text-ink-3">{traducir("Ninguna regla coincide con la búsqueda.")}</div>
          )}
        </div>
      )}
    </div>
  )
}
