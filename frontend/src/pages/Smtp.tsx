import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface SmtpConfigData {
  smtp_host: string | null
  smtp_port: number
  smtp_user: string | null
  smtp_password_set: boolean
  smtp_from: string | null
  smtp_encryption: string
}

export default function Smtp() {
  const [config, setConfig] = useState<SmtpConfigData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [smtpPassword, setSmtpPassword] = useState('')
  const [destinatarioPrueba, setDestinatarioPrueba] = useState('')
  const [testing, setTesting] = useState(false)
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    api.getSmtpConfig().then(setConfig).catch(e => showToast(e.message, 'error')).finally(() => setLoading(false))
  }, [])

  const save = async () => {
    if (!config) return
    setSaving(true)
    try {
      await api.updateSmtpConfig({
        smtp_host: config.smtp_host,
        smtp_port: config.smtp_port,
        smtp_user: config.smtp_user,
        smtp_password: smtpPassword || undefined,
        smtp_from: config.smtp_from,
        smtp_encryption: config.smtp_encryption,
      })
      showToast(traducir("Configuración guardada correctamente"), 'success')
      setSmtpPassword('')
      const refreshed = await api.getSmtpConfig()
      setConfig(refreshed)
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const test = async () => {
    if (!config) return
    if (!config.smtp_host) { showToast(traducir("Falta el servidor SMTP (host)"), 'error'); return }
    if (!destinatarioPrueba) { showToast(traducir("Falta el destinatario (email)"), 'error'); return }

    setTesting(true)
    try {
      const r = await api.testSmtp({
        smtp_host: config.smtp_host,
        smtp_port: config.smtp_port,
        smtp_user: config.smtp_user,
        smtp_password: smtpPassword || undefined,
        smtp_from: config.smtp_from,
        smtp_encryption: config.smtp_encryption,
        destinatario_prueba: destinatarioPrueba,
      })
      showToast(r.message, r.ok ? 'success' : 'error')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setTesting(false)
    }
  }

  const esGmail = (config?.smtp_host || '').toLowerCase().includes('gmail')

  if (loading || !config) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-2" style={{ color: '#0A2C48' }}>{traducir("SMTP")}</h1>
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-xs text-blue-800">
        {traducir("Servidor de correo saliente único para todo SquidManager: lo usan las alertas de Notificaciones y el formulario de Contacto.")}
      </div>

      <div className="card p-6 mb-6 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="smtp-host" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Servidor SMTP")}</label>
            <input id="smtp-host" type="text" value={config.smtp_host || ''} placeholder="smtp.gmail.com"
              onChange={e => setConfig({ ...config, smtp_host: e.target.value })}
              className="input text-sm" />
          </div>
          <div>
            <label htmlFor="smtp-port" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Puerto")}</label>
            <input id="smtp-port" type="number" value={config.smtp_port}
              onChange={e => setConfig({ ...config, smtp_port: Number(e.target.value) })}
              className="input text-sm" />
          </div>
        </div>
        {esGmail && (
          <div className="text-xs text-ink-3 bg-warn-soft border border-warn/20 rounded-lg p-3">
            {traducir("Gmail no acepta la contraseña normal de la cuenta por SMTP. Genera una \"contraseña de aplicación\" (16 caracteres) en")}{' '}
            <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" className="text-brand-700 font-medium underline">
              myaccount.google.com/apppasswords
            </a>{' '}
            {traducir("(requiere verificación en 2 pasos activada) y usa esa contraseña acá, no la de tu cuenta.")}
          </div>
        )}
        <div>
          <label htmlFor="smtp-encryption" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Método de cifrado / seguridad de conexión")}</label>
          <select id="smtp-encryption" value={config.smtp_encryption}
            onChange={e => setConfig({ ...config, smtp_encryption: e.target.value })}
            className="input text-sm bg-white">
            <option value="starttls">{traducir("STARTTLS (puerto 587 — Gmail, Outlook, la mayoría)")}</option>
            <option value="ssl">{traducir("SSL/TLS implícito (puerto 465 — algunos servicios)")}</option>
            <option value="none">{traducir("Sin cifrado (servidores internos)")}</option>
          </select>
          <p className="text-xs text-ink-3 mt-1">{traducir("La mayoría de servicios usan STARTTLS en el puerto 587. Si tu servicio pide SSL/TLS, elige \"SSL/TLS implícito\" (puerto 465).")}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="smtp-user" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Usuario SMTP")}</label>
            <input id="smtp-user" type="text" value={config.smtp_user || ''}
              onChange={e => setConfig({ ...config, smtp_user: e.target.value })}
              className="input text-sm" />
          </div>
          <div>
            <label htmlFor="smtp-password" className="block text-xs font-medium text-ink-3 mb-1">
              {traducir("Contraseña SMTP")} {config.smtp_password_set && <span className="text-ok">{traducir("(guardada)")}</span>}
            </label>
            <input id="smtp-password" type="password" value={smtpPassword} placeholder={config.smtp_password_set ? '••••••••' : traducir('Nueva contraseña')}
              onChange={e => setSmtpPassword(e.target.value)}
              className="input text-sm" />
          </div>
        </div>
        <div>
          <label htmlFor="smtp-from" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Remitente (From)")}</label>
          <input id="smtp-from" type="text" value={config.smtp_from || ''} placeholder={traducir("notificaciones@empresa.com")}
            onChange={e => setConfig({ ...config, smtp_from: e.target.value })}
            className="input text-sm" />
        </div>

        <div className="pt-2 border-t border-line-soft">
          <label htmlFor="destinatario-prueba" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Enviar prueba a")}</label>
          <div className="flex items-center gap-3">
            <input id="destinatario-prueba" type="email" value={destinatarioPrueba} placeholder="tu@correo.com"
              onChange={e => setDestinatarioPrueba(e.target.value)}
              className="input text-sm flex-1" />
            <button onClick={test} disabled={testing}
              className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 flex-none" style={{ backgroundColor: '#48B3D0' }}>
              {testing ? traducir('Enviando…') : traducir('Enviar correo de prueba')}
            </button>
          </div>
          <span className="text-xs text-ink-3">{traducir("Prueba con los datos actuales del formulario (no hace falta guardar antes)")}</span>
        </div>
      </div>

      <button onClick={save} disabled={saving}
        className="px-6 py-3 text-white rounded-lg font-medium disabled:opacity-50" style={{ backgroundColor: '#0B497C' }}>
        {saving ? traducir('Guardando…') : traducir('Guardar configuración')}
      </button>

      <ToastContainer />
    </div>
  )
}
