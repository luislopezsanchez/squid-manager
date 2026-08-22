import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface Setting {
  value: string
  category: string
  description: string | null
}

const CATEGORIES = [
  { key: 'network', label: 'Red', icon: '🌐' },
  { key: 'cache', label: 'Caché', icon: '💾' },
  { key: 'security', label: 'Seguridad', icon: '🔒' },
  { key: 'logging', label: 'Logging', icon: '📋' },
  { key: 'general', label: 'General', icon: '⚙️' },
]

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, Setting>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState('')
  const { showToast, ToastContainer } = useToast()

  const loadSettings = () => {
    api.getSettings().then(setSettings).catch(e => showToast('Error al cargar configuración', 'error')).finally(() => setLoading(false))
  }

  useEffect(() => { loadSettings() }, [])

  const handleSave = async (key: string) => {
    setSaving(key)
    setError('')
    try {
      const setting = settings[key]
      await api.updateSetting(key, setting.value, setting.category, setting.description || '')
      showToast(`Configuración "${key}" guardada correctamente`)
    } catch (e: any) {
      setError(e.message)
      showToast(`Error al guardar: ${e.message}`, 'error')
    } finally {
      setSaving(null)
    }
  }

  const updateValue = (key: string, value: string) => {
    setSettings({ ...settings, [key]: { ...settings[key], value } })
  }

  if (loading) return <div className="p-8 text-center text-gray-500">Cargando...</div>

  return (
    <div className="p-8">
      <ToastContainer />
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Configuración de Squid</h1>
      <p className="text-sm text-gray-500 mb-6">Parámetros generales del proxy. Los cambios se guardan en la BD.</p>

      {error && <div className="mb-4 bg-red-50 text-red-600 text-sm p-3 rounded-lg">{error}</div>}

      {CATEGORIES.map(cat => {
        const catSettings = Object.entries(settings).filter(([_, s]) => s.category === cat.key)
        if (catSettings.length === 0) return null

        return (
          <div key={cat.key} className="mb-8">
            <h2 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
              <span>{cat.icon}</span> {cat.label}
            </h2>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 divide-y divide-gray-100">
              {catSettings.map(([key, setting]) => (
                <div key={key} className="p-4 flex items-center gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-mono font-medium text-gray-700">{key}</label>
                    {setting.description && <p className="text-xs text-gray-400 mt-0.5">{setting.description}</p>}
                  </div>
                  <div className="flex-1">
                    <input
                      type="text"
                      value={setting.value}
                      onChange={e => updateValue(key, e.target.value)}
                      className="w-full px-3 py-1.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                    />
                  </div>
                  <button
                    onClick={() => handleSave(key)}
                    disabled={saving === key}
                    className="px-4 py-1.5 bg-primary-600 text-white text-sm rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50"
                  >
                    {saving === key ? '...' : 'Guardar'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}