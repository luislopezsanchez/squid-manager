import { useState, useEffect } from 'react'
import { IconCheck, IconClose } from '../components/Icons'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

const FACILITIES = ['local0', 'local1', 'local2', 'local3', 'local4', 'local5', 'local6', 'local7', 'user', 'daemon', 'syslog']

export default function SyslogConfig() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    api.getSyslogConfig().then(setConfig).catch(() => showToast('Error al cargar la configuración de syslog', 'error')).finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const result = await api.updateSyslogConfig(config)
      showToast(result.message, 'success')
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await api.testSyslog(config)
      setTestResult({ ok: result.status === 'ok', message: result.message })
    } catch (e: any) {
      setTestResult({ ok: false, message: e.message })
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-ink-3">Cargando...</div>
  if (!config) return <div className="p-8 text-center text-ink-3">No se pudo cargar la configuración</div>

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">Syslog externo</h1>
      <p className="text-sm text-ink-3 mb-6">
        Reenvía los logs de acceso a un SIEM o herramienta de auditoría externa, en tiempo real. Es un canal
        opcional: mientras esté apagado, no se manda nada a ningún lado.
      </p>

      {/* Estado */}
      <div className={`rounded-xl p-4 mb-6 border ${config.enabled ? 'bg-green-50 border-green-200' : 'bg-brand-50 border-line'}`}>
        <div className="flex items-center gap-3">
          <span className={`inline-flex h-3 w-3 rounded-full ${config.enabled ? 'bg-ok' : 'bg-ink-3'}`} />
          <span className="font-medium text-ink">
            {config.enabled ? 'Reenvío activado' : 'Reenvío desactivado'}
          </span>
          <label className="ml-auto flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={e => setConfig({ ...config, enabled: e.target.checked })}
              className="w-5 h-5 rounded text-primary-600"
            />
            <span className="text-sm text-ink-2">Habilitar</span>
          </label>
        </div>
      </div>

      {/* Configuración */}
      <div className="card p-6 mb-6">
        <h2 className="font-medium text-ink mb-4">Destino</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="field-label block mb-1.5">Host</label>
            <input type="text" value={config.host ?? ''} onChange={e => setConfig({ ...config, host: e.target.value })}
              placeholder="siem.empresa.com o 10.0.0.5" className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">Puerto</label>
            <input type="number" value={config.port} onChange={e => setConfig({ ...config, port: Number(e.target.value) })}
              placeholder="514" className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">Protocolo</label>
            <select value={config.protocol} onChange={e => setConfig({ ...config, protocol: e.target.value })} className="input text-sm">
              <option value="udp">UDP (más simple, puede perder paquetes)</option>
              <option value="tcp">TCP (confiable, algo más de carga)</option>
            </select>
          </div>
          <div>
            <label className="field-label block mb-1.5">Facility</label>
            <select value={config.facility} onChange={e => setConfig({ ...config, facility: e.target.value })} className="input text-sm">
              {FACILITIES.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <div>
            <label className="field-label block mb-1.5">Formato del mensaje syslog</label>
            <select value={config.rfc_format} onChange={e => setConfig({ ...config, rfc_format: e.target.value })} className="input text-sm">
              <option value="rfc3164">RFC 3164 (clásico, el más compatible)</option>
              <option value="rfc5424">RFC 5424 (estructurado, con fecha ISO)</option>
            </select>
          </div>
          <div>
            <label className="field-label block mb-1.5">Contenido de cada línea</label>
            <select value={config.log_format} onChange={e => setConfig({ ...config, log_format: e.target.value })} className="input text-sm">
              <option value="raw">Log nativo de Squid (para AWStats, SARG, el módulo Squid de Splunk/ELK)</option>
              <option value="ndjson">JSON (para ingesta genérica en un SIEM)</option>
            </select>
          </div>
        </div>

        <div className="flex gap-3 mt-4">
          <button onClick={handleSave} disabled={saving} className="btn btn-primary disabled:opacity-50">
            {saving ? 'Guardando...' : 'Guardar Configuración'}
          </button>
          <button
            onClick={handleTest}
            disabled={testing || !config.host}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {testing ? 'Enviando...' : 'Enviar mensaje de prueba'}
          </button>
        </div>
        <p className="text-xs text-ink-3 mt-2">
          "Enviar mensaje de prueba" manda un mensaje ahora mismo con los datos de este formulario, sin necesidad
          de guardar antes — así se puede probar un destino nuevo sin activarlo todavía.
        </p>

        {testResult && (
          <div className={`mt-4 p-3 rounded-lg flex items-start gap-3 ${
            testResult.ok ? 'bg-green-50 border border-green-100' : 'bg-red-50 border border-red-100'
          }`}>
            <span className={`stat-icon flex-none ${testResult.ok ? 'stat-icon-ok' : 'stat-icon-danger'}`}>
              {testResult.ok ? <IconCheck /> : <IconClose />}
            </span>
            <p className="text-sm text-ink-2">{testResult.message}</p>
          </div>
        )}
      </div>

      <div className="card p-6">
        <h2 className="font-medium text-ink mb-2">Cómo funciona</h2>
        <ul className="text-sm text-ink-2 space-y-1.5 list-disc pl-5">
          <li>Un proceso en segundo plano sigue el access.log igual que <code className="font-mono text-xs">tail -f</code> y reenvía cada línea nueva al destino configurado — no es una exportación puntual, es continuo mientras esté habilitado.</li>
          <li>Revisa la configuración cada pocos segundos: activarlo, apagarlo o cambiar el destino surte efecto solo, sin reiniciar nada.</li>
          <li>Mientras está apagado, no se acumula nada para mandar de golpe al activarlo — solo se reenvía lo que llegue después.</li>
          <li>UDP no confirma entrega: si el destino no está escuchando, el mensaje se pierde en silencio. TCP si falla la conexión lo reintenta en el siguiente lote.</li>
        </ul>
      </div>
    </div>
  )
}
