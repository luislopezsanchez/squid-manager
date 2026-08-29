import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface Setting {
  value: string
  category: string
  description: string | null
}

const CATEGORIES = [
  { key: 'network', label: traducir("Red") },
  { key: 'cache', label: traducir("Caché") },
  { key: 'security', label: traducir("Seguridad") },
  { key: 'logging', label: traducir("Registros") },
  { key: 'general', label: traducir("General") },
]

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, Setting>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [testingDns, setTestingDns] = useState(false)
  const [dnsResult, setDnsResult] = useState<{ ok: boolean; message: string } | null>(null)
  const { showToast, ToastContainer } = useToast()

  // Un DNS que no responde no rompe una web: deja de resolver todas a la vez.
  // Por eso se puede comprobar antes de guardar, y no solo al aplicar.
  const handleTestDns = async () => {
    setTestingDns(true)
    setDnsResult(null)
    try {
      setDnsResult(await api.testDns(settings['dns_nameservers']?.value || ''))
    } catch (e: any) {
      setDnsResult({ ok: false, message: e.message })
    } finally {
      setTestingDns(false)
    }
  }

  const loadSettings = () => {
    api.getSettings().then(setSettings).catch(e => showToast(traducir("Error al cargar configuración"), 'error')).finally(() => setLoading(false))
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

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Configuración de Squid")}</h1>
      <p className="text-sm text-ink-3 mb-6">{traducir("Parámetros generales del proxy. Los cambios se guardan en la BD.")}</p>

      {error && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{error}</div>}

      {CATEGORIES.map(cat => {
        const catSettings = Object.entries(settings).filter(([_, s]) => s.category === cat.key)
        if (catSettings.length === 0) return null

        return (
          <div key={cat.key} className="mb-8">
            <h2 className="text-lg font-bold text-ink mb-3">{cat.label}</h2>
            <div className="card divide-y divide-line-soft">
              {catSettings.map(([key, setting]) => (
                <div key={key} className="p-4">
                  <div className="flex items-center gap-4">
                    <div className="flex-1">
                      <label className="block text-sm font-mono font-medium text-ink-2">{key}</label>
                      {setting.description && <p className="text-xs text-ink-3 mt-0.5">{setting.description}</p>}
                    </div>
                    <div className="flex-1">
                      <input
                        type="text"
                        value={setting.value}
                        onChange={e => {
                          updateValue(key, e.target.value)
                          if (key === 'dns_nameservers') setDnsResult(null)
                        }}
                        placeholder={key === 'dns_nameservers' ? '172.27.0.1 1.1.1.1' : undefined}
                        className="w-full px-3 py-1.5 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                      />
                    </div>
                    {key === 'dns_nameservers' && (
                      <button
                        onClick={handleTestDns}
                        disabled={testingDns}
                        className="btn btn-ghost btn-sm"
                        title={traducir("Consulta a esos servidores para ver si responden, sin guardar nada")}
                      >
                        {testingDns ? traducir('Probando...') : traducir('Probar')}
                      </button>
                    )}
                    <button
                      onClick={() => handleSave(key)}
                      disabled={saving === key}
                      className="btn btn-primary btn-sm"
                    >
                      {saving === key ? '...' : traducir('Guardar')}
                    </button>
                  </div>

                  {key === 'dns_nameservers' && dnsResult && (
                    <div
                      className={`mt-3 text-[13px] p-2.5 rounded-lg ${
                        dnsResult.ok ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
                      }`}
                    >
                      {dnsResult.ok ? '✓ ' : '✕ '}{dnsResult.message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}