import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

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

// Definir qué niveles tiene cada clase
const CLASS_LEVELS: Record<number, { label: string; levels: { key: string; label: string; desc: string }[] }> = {
  1: {
    label: 'Clase 1: Límite global',
    levels: [
      { key: 'global', label: 'Límite global', desc: 'Ancho de banda total compartido por todos los usuarios' },
    ],
  },
  2: {
    label: 'Clase 2: Límite individual',
    levels: [
      { key: 'global', label: 'Límite global', desc: 'Ancho de banda total para todos combinados' },
      { key: 'individual', label: 'Límite por usuario', desc: 'Ancho de banda máximo por cada usuario' },
    ],
  },
  3: {
    label: 'Clase 3: Límite por red',
    levels: [
      { key: 'global', label: 'Límite global', desc: 'Ancho de banda total para todos' },
      { key: 'network', label: 'Límite por red', desc: 'Ancho de banda por subred /24' },
      { key: 'individual', label: 'Límite por usuario', desc: 'Ancho de banda por usuario individual' },
    ],
  },
  4: {
    label: 'Clase 4: Límite por grupo',
    levels: [
      { key: 'global', label: 'Límite global', desc: 'Ancho de banda total' },
      { key: 'group', label: 'Límite por grupo', desc: 'Ancho de banda por grupo (requiere ACL tag)' },
    ],
  },
  5: {
    label: 'Clase 5: Límite avanzado',
    levels: [
      { key: 'global', label: 'Límite global', desc: 'Ancho de banda total' },
      { key: 'network', label: 'Límite por red', desc: 'Ancho de banda por subred' },
      { key: 'individual', label: 'Límite por usuario', desc: 'Ancho de banda por usuario' },
      { key: 'tag', label: 'Límite por tag', desc: 'Ancho de banda por tag de ACL' },
    ],
  },
}

const UNITS = [
  { value: 1, label: 'bytes/s' },
  { value: 1024, label: 'KB/s' },
  { value: 1048576, label: 'MB/s' },
]

// Convierte un valor humano (numero + unidad) a bytes para Squid
function toBytes(value: number, unitMultiplier: number): number {
  return Math.round(value * unitMultiplier)
}

// Intenta parsear parametros existentes de Squid a valores humanos
function parseParameters(params: string, poolClass: number): Record<string, { restore: number; limit: number; restoreUnit: number; limitUnit: number }> {
  const result: Record<string, { restore: number; limit: number; restoreUnit: number; limitUnit: number }> = {}
  const levels = CLASS_LEVELS[poolClass]?.levels || []
  // Squid format: "restore1/limit1 restore2/limit2 ..."
  const parts = params.trim().split(/\s+/)
  parts.forEach((part, i) => {
    const [restoreStr, limitStr] = part.split('/')
    const restore = parseInt(restoreStr) || 0
    const limit = parseInt(limitStr) || 0
    // Auto-detectar unidad (si > 1MB usar MB, si > 1KB usar KB, sino bytes)
    const restoreUnit = restore >= 1048576 ? 1048576 : restore >= 1024 ? 1024 : 1
    const limitUnit = limit >= 1048576 ? 1048576 : limit >= 1024 ? 1024 : 1
    const levelKey = levels[i]?.key || `level${i}`
    result[levelKey] = {
      restore: Math.round(restore / restoreUnit * 100) / 100,
      limit: Math.round(limit / limitUnit * 100) / 100,
      restoreUnit,
      limitUnit,
    }
  })
  return result
}

// Convierte los valores humanos al formato de Squid
function buildParameters(poolClass: number, speeds: Record<string, { restore: number; limit: number; restoreUnit: number; limitUnit: number }>): string {
  const levels = CLASS_LEVELS[poolClass]?.levels || []
  const parts: string[] = []
  for (const level of levels) {
    const s = speeds[level.key]
    if (s && s.restore > 0 && s.limit > 0) {
      const restoreBytes = toBytes(s.restore, s.restoreUnit)
      const limitBytes = toBytes(s.limit, s.limitUnit)
      parts.push(`${restoreBytes}/${limitBytes}`)
    } else {
      parts.push('0/0')
    }
  }
  return parts.join(' ')
}

export default function DelayPools() {
  const [pools, setPools] = useState<DelayPool[]>([])
  const [acls, setAcls] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({
    pool_class: 2,
    acl_name: '',
    description: '',
    enabled: true,
  })
  // Speeds: { global: { restore: 64, limit: 64, restoreUnit: 1024, limitUnit: 1024 }, ... }
  const [speeds, setSpeeds] = useState<Record<string, { restore: number; limit: number; restoreUnit: number; limitUnit: number }>>({})
  const [error, setError] = useState('')
  const { showToast, ToastContainer } = useToast()

  const loadPools = () => {
    api.listDelayPools().then(setPools).catch(e => showToast('Error al cargar delay pools', 'error')).finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPools()
    api.listAcls().then(setAcls).catch(console.error)
  }, [])

  // Inicializar speeds cuando cambia la clase
  useEffect(() => {
    const levels = CLASS_LEVELS[form.pool_class]?.levels || []
    const newSpeeds: Record<string, { restore: number; limit: number; restoreUnit: number; limitUnit: number }> = {}
    for (const level of levels) {
      newSpeeds[level.key] = speeds[level.key] || { restore: 64, limit: 64, restoreUnit: 1024, limitUnit: 1024 }
    }
    setSpeeds(newSpeeds)
  }, [form.pool_class])

  const updateSpeed = (levelKey: string, field: 'restore' | 'limit' | 'restoreUnit' | 'limitUnit', value: number) => {
    setSpeeds(prev => ({
      ...prev,
      [levelKey]: { ...prev[levelKey], [field]: value },
    }))
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validar que todos los niveles tengan valores > 0
    const levels = CLASS_LEVELS[form.pool_class]?.levels || []
    for (const level of levels) {
      const s = speeds[level.key]
      if (!s || s.restore <= 0 || s.limit <= 0) {
        setError(`El nivel "${level.label}" debe tener valores mayores a 0`)
        return
      }
    }

    const parameters = buildParameters(form.pool_class, speeds)

    try {
      const data = { ...form, acl_name: form.acl_name || null, parameters }
      if (editingId) {
        await api.updateDelayPool(editingId, data)
        showToast('Delay pool actualizado correctamente')
      } else {
        await api.createDelayPool(data)
        showToast('Delay pool creado correctamente')
      }
      setForm({ pool_class: 2, acl_name: '', description: '', enabled: true })
      setSpeeds({})
      setEditingId(null)
      setShowForm(false)
      loadPools()
    } catch (err: any) {
      setError(err.message)
      showToast(`Error: ${err.message}`, 'error')
    }
  }

  const handleEdit = (pool: DelayPool) => {
    const parsed = parseParameters(pool.parameters, pool.pool_class)
    setSpeeds(parsed)
    setForm({
      pool_class: pool.pool_class,
      acl_name: pool.acl_name || '',
      description: pool.description || '',
      enabled: pool.enabled,
    })
    setEditingId(pool.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar este delay pool?')) return
    try {
      await api.deleteDelayPool(id)
      loadPools()
      showToast('Delay pool eliminado correctamente')
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const currentClass = CLASS_LEVELS[form.pool_class]

  // Formatear parametros para mostrar en la lista de forma legible
  const formatDisplay = (params: string, poolClass: number) => {
    const parsed = parseParameters(params, poolClass)
    const levels = CLASS_LEVELS[poolClass]?.levels || []
    return levels.map(level => {
      const s = parsed[level.key]
      if (!s) return null
      const rUnit = UNITS.find(u => u.value === s.restoreUnit)?.label || 'bytes/s'
      const lUnit = UNITS.find(u => u.value === s.limitUnit)?.label || 'bytes/s'
      return `${level.label}: ${s.restore} ${rUnit} / ${s.limit} ${lUnit}`
    }).filter(Boolean).join(' | ')
  }

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Delay Pools</h1>
          <p className="page-sub">Control de ancho de banda por usuario, red o grupo</p>
        </div>
        <button
          onClick={() => {
            setShowForm(!showForm)
            setEditingId(null)
            setForm({ pool_class: 2, acl_name: '', description: '', enabled: true })
            setSpeeds({})
          }}
          className="btn btn-primary"
        >
          {showForm ? 'Cancelar' : '+ Nuevo Delay Pool'}
        </button>
      </div>

      {/* Info */}
      <div className="bg-blue-50 rounded-xl p-4 mb-6 border border-blue-100">
        <h3 className="text-sm font-medium text-blue-900 mb-1">¿Cómo funciona?</h3>
        <p className="text-xs text-blue-700">
          Cada nivel tiene dos valores: <strong>Restauración</strong> (velocidad a la que se recupera el ancho de banda)
          y <strong>Límite</strong> (velocidad máxima permitida). Selecciona la unidad (KB/s, MB/s) y el sistema
          convierte automáticamente al formato que Squid necesita.
        </p>
      </div>

      {showForm && (
        <form onSubmit={handleSave} className="card p-6 mb-6">
          <h3 className="font-medium text-ink mb-4">{editingId ? 'Editar Delay Pool' : 'Nuevo Delay Pool'}</h3>

          {/* Selector de clase */}
          <div className="mb-6">
            <label className="field-label block mb-1.5">Tipo de limitación</label>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.values(CLASS_LEVELS).map(c => (
                <button
                  key={c.label}
                  type="button"
                  onClick={() => setForm({ ...form, pool_class: Object.keys(CLASS_LEVELS).find(k => CLASS_LEVELS[Number(k)].label === c.label) ? Number(Object.keys(CLASS_LEVELS).find(k => CLASS_LEVELS[Number(k)].label === c.label)) : form.pool_class })}
                  className={`text-left p-3 rounded-lg border-2 transition ${
                    form.pool_class === Object.keys(CLASS_LEVELS).find(k => CLASS_LEVELS[Number(k)].label === c.label)
                      ? 'border-primary-500 bg-primary-50' : 'border-line hover:border-line'
                  }`}
                >
                  <p className="font-medium text-sm text-ink">{c.label}</p>
                  <p className="text-xs text-ink-3 mt-1">{c.levels.length} nivel(es) de limitación</p>
                </button>
              ))}
            </div>
          </div>

          {/* Campos de velocidad por nivel */}
          <div className="space-y-4 mb-6">
            <h4 className="text-sm font-medium text-ink-2">Configurar velocidades</h4>
            {currentClass?.levels.map((level, idx) => {
              const s = speeds[level.key] || { restore: 64, limit: 64, restoreUnit: 1024, limitUnit: 1024 }
              return (
                <div key={level.key} className="bg-brand-50 rounded-lg p-4 border border-line-soft">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-6 h-6 bg-brand-700 text-white text-xs font-bold rounded-full flex items-center justify-center">{idx + 1}</span>
                    <span className="font-medium text-ink text-sm">{level.label}</span>
                  </div>
                  <p className="text-xs text-ink-3 mb-3">{level.desc}</p>
                  <div className="grid grid-cols-2 gap-4">
                    {/* Restauración */}
                    <div>
                      <label className="block text-xs font-medium text-ink-2 mb-1">Velocidad de restauración</label>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="1"
                          step="0.1"
                          value={s.restore}
                          onChange={e => updateSpeed(level.key, 'restore', parseFloat(e.target.value) || 0)}
                          className="flex-1 px-3 py-1.5 border border-line rounded-lg text-sm focus:ring-2 focus:ring-primary-500"
                        />
                        <select
                          value={s.restoreUnit}
                          onChange={e => updateSpeed(level.key, 'restoreUnit', parseInt(e.target.value))}
                          className="px-2 py-1.5 border border-line rounded-lg text-sm bg-white focus:ring-2 focus:ring-primary-500"
                        >
                          {UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
                        </select>
                      </div>
                      <p className="text-xs text-ink-3 mt-1">A qué velocidad se recupera el bucket</p>
                    </div>
                    {/* Límite */}
                    <div>
                      <label className="block text-xs font-medium text-ink-2 mb-1">Límite máximo</label>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="1"
                          step="0.1"
                          value={s.limit}
                          onChange={e => updateSpeed(level.key, 'limit', parseFloat(e.target.value) || 0)}
                          className="flex-1 px-3 py-1.5 border border-line rounded-lg text-sm focus:ring-2 focus:ring-primary-500"
                        />
                        <select
                          value={s.limitUnit}
                          onChange={e => updateSpeed(level.key, 'limitUnit', parseInt(e.target.value))}
                          className="px-2 py-1.5 border border-line rounded-lg text-sm bg-white focus:ring-2 focus:ring-primary-500"
                        >
                          {UNITS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
                        </select>
                      </div>
                      <p className="text-xs text-ink-3 mt-1">Velocidad máxima permitida</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Vista previa del formato Squid */}
          <div className="bg-slate-900 rounded-lg p-3 mb-4">
            <p className="text-xs text-slate-400 mb-1">Formato Squid generado:</p>
            <p className="text-green-400 font-mono text-sm">delay_parameters {editingId || 'N'} {buildParameters(form.pool_class, speeds)}</p>
          </div>

          {/* ACL y descripción */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="field-label block mb-1.5">ACL asociada (opcional)</label>
              <select value={form.acl_name} onChange={e => setForm({ ...form, acl_name: e.target.value })}
                className="input">
                <option value="">Sin ACL (aplica a todos)</option>
                {acls.map((a: any) => <option key={a.id} value={a.name}>{a.name}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label block mb-1.5">Descripción (opcional)</label>
              <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                placeholder="ej: Limitar a 64KB/s para red local" className="input" />
            </div>
          </div>

          {error && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}
          <button type="submit" className="btn btn-primary">
            {editingId ? 'Guardar Cambios' : 'Crear Delay Pool'}
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-center py-12 text-ink-3">Cargando...</div>
      ) : (
        <div className="space-y-3">
          {pools.map(pool => (
            <div key={pool.id} className={`card p-5 ${!pool.enabled ? 'opacity-50' : ''}`}>
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="px-3 py-1 bg-purple-100 text-purple-800 text-sm font-bold rounded-full">
                      {CLASS_LEVELS[pool.pool_class]?.label || `Clase ${pool.pool_class}`}
                    </span>
                    {pool.acl_name && (
                      <span className="px-2 py-1 bg-brand-50 text-brand-700 text-xs font-mono rounded">ACL: {pool.acl_name}</span>
                    )}
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${pool.enabled ? 'pill-ok' : 'pill-danger'}`}>
                      {pool.enabled ? 'Activo' : 'Inactivo'}
                    </span>
                  </div>
                  {/* Mostrar velocidades de forma legible */}
                  <div className="text-sm text-ink-2 space-y-1 mb-2">
                    {formatDisplay(pool.parameters, pool.pool_class).split(' | ').map((part, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className="text-ink-3">•</span>
                        <span>{part}</span>
                      </div>
                    ))}
                  </div>
                  {pool.description && <p className="text-sm text-ink-3">{pool.description}</p>}
                  {/* Formato técnico */}
                  <p className="text-xs text-ink-3 font-mono mt-1">Squid: {pool.parameters}</p>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={() => handleEdit(pool)} className="text-primary-600 hover:text-primary-800 text-sm font-medium">Editar</button>
                  <button onClick={() => handleDelete(pool.id)} className="text-danger hover:text-danger text-sm font-medium">Eliminar</button>
                </div>
              </div>
            </div>
          ))}
          {pools.length === 0 && (
            <div className="card p-8 text-center text-ink-3">
              No hay delay pools configurados. Crea uno para controlar el ancho de banda.
            </div>
          )}
        </div>
      )}
    </div>
  )
}