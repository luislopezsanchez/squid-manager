import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface NotifConfig {
  email_enabled: boolean
  smtp_host: string | null
  smtp_port: number
  smtp_user: string | null
  smtp_password_set: boolean
  smtp_from: string | null
  smtp_encryption: string
  email_recipients: string | null
  telegram_enabled: boolean
  telegram_bot_token_set: boolean
  telegram_chat_id: string | null
  notify_on_apply: boolean
  notify_on_user_change: boolean
  notify_on_acl_change: boolean
  notify_on_rule_change: boolean
  notify_on_security_alert: boolean
}

export default function Notifications() {
  const [config, setConfig] = useState<NotifConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [smtpPassword, setSmtpPassword] = useState('')
  const [telegramToken, setTelegramToken] = useState('')
  const [testingEmail, setTestingEmail] = useState(false)
  const [testingTelegram, setTestingTelegram] = useState(false)
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    api.getNotificationConfig().then(setConfig).catch(e => showToast(e.message, 'error')).finally(() => setLoading(false))
  }, [])

  const save = async () => {
    if (!config) return
    setSaving(true)
    try {
      const payload: any = {
        email_enabled: config.email_enabled,
        smtp_host: config.smtp_host,
        smtp_port: config.smtp_port,
        smtp_user: config.smtp_user,
        smtp_password: smtpPassword || undefined,
        smtp_from: config.smtp_from,
        smtp_encryption: config.smtp_encryption,
        email_recipients: config.email_recipients,
        telegram_enabled: config.telegram_enabled,
        telegram_bot_token: telegramToken || undefined,
        telegram_chat_id: config.telegram_chat_id,
        notify_on_apply: config.notify_on_apply,
        notify_on_user_change: config.notify_on_user_change,
        notify_on_acl_change: config.notify_on_acl_change,
        notify_on_rule_change: config.notify_on_rule_change,
        notify_on_security_alert: config.notify_on_security_alert,
      }
      await api.updateNotificationConfig(payload)
      showToast('Configuración guardada correctamente', 'success')
      setSmtpPassword('')
      setTelegramToken('')
      // Recargar config para actualizar los indicadores "(guardado)"
      const refreshed = await api.getNotificationConfig()
      setConfig(refreshed)
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const testEmail = async () => {
    if (!config) return
    // Validar campos mínimos
    if (!config.smtp_host) { showToast('Falta el servidor SMTP (host)', 'error'); return }
    if (!config.email_recipients) { showToast('Falta el destinatario (email)', 'error'); return }

    setTestingEmail(true)
    try {
      const r = await api.testEmail({
        smtp_host: config.smtp_host,
        smtp_port: config.smtp_port,
        smtp_user: config.smtp_user,
        smtp_password: smtpPassword || undefined,
        smtp_from: config.smtp_from,
        smtp_encryption: config.smtp_encryption,
        email_recipients: config.email_recipients,
      })
      showToast(r.message, r.ok ? 'success' : 'error')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setTestingEmail(false)
    }
  }

  const testTelegram = async () => {
    if (!config) return
    if (!telegramToken && !config.telegram_bot_token_set) { showToast('Falta el token del bot de Telegram', 'error'); return }
    if (!config.telegram_chat_id) { showToast('Falta el Chat ID de Telegram', 'error'); return }

    setTestingTelegram(true)
    try {
      const r = await api.testTelegram({
        telegram_bot_token: telegramToken || undefined,
        telegram_chat_id: config.telegram_chat_id || undefined,
      })
      showToast(r.message, r.ok ? 'success' : 'error')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setTestingTelegram(false)
    }
  }

  if (loading || !config) return <div className="p-8 text-center text-gray-500">Cargando...</div>

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-6" style={{ color: '#083151' }}>Notificaciones</h1>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-xs text-blue-800">
        Configura alertas por email y/o Telegram para enterarte de cambios críticos en el proxy.
        Guarda la configuración primero, o usa los botones de prueba para validar los datos actuales del formulario.
      </div>

      {/* Email */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-gray-900">📧 Notificaciones por Email</h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.email_enabled}
              onChange={e => setConfig({ ...config, email_enabled: e.target.checked })}
              className="w-4 h-4" style={{ accentColor: '#0b497c' }} />
            <span className="text-sm">Habilitar</span>
          </label>
        </div>
        {config.email_enabled && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Servidor SMTP</label>
                <input type="text" value={config.smtp_host || ''} placeholder="smtp.gmail.com"
                  onChange={e => setConfig({ ...config, smtp_host: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Puerto</label>
                <input type="number" value={config.smtp_port}
                  onChange={e => setConfig({ ...config, smtp_port: Number(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Método de cifrado / seguridad de conexión</label>
              <select value={config.smtp_encryption}
                onChange={e => setConfig({ ...config, smtp_encryption: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
                <option value="starttls">STARTTLS (puerto 587 — Gmail, Outlook, la mayoría)</option>
                <option value="ssl">SSL/TLS implícito (puerto 465 — algunos servicios)</option>
                <option value="none">Sin cifrado (servidores internos)</option>
              </select>
              <p className="text-xs text-gray-400 mt-1">
                La mayoría de servicios usan STARTTLS en el puerto 587. Si tu servicio pide SSL/TLS, elige "SSL/TLS implícito" (puerto 465).
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Usuario SMTP</label>
                <input type="text" value={config.smtp_user || ''}
                  onChange={e => setConfig({ ...config, smtp_user: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Contraseña SMTP {config.smtp_password_set && <span className="text-green-600">(guardada)</span>}
                </label>
                <input type="password" value={smtpPassword} placeholder={config.smtp_password_set ? '••••••••' : 'Nueva contraseña'}
                  onChange={e => setSmtpPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Remitente (From)</label>
              <input type="text" value={config.smtp_from || ''} placeholder="notificaciones@empresa.com"
                onChange={e => setConfig({ ...config, smtp_from: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Destinatarios (separados por coma)</label>
              <input type="text" value={config.email_recipients || ''} placeholder="admin1@empresa.com, admin2@empresa.com"
                onChange={e => setConfig({ ...config, email_recipients: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div className="flex items-center gap-3">
              <button onClick={testEmail} disabled={testingEmail}
                className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50" style={{ backgroundColor: '#299ac2' }}>
                {testingEmail ? 'Enviando...' : '✉️ Enviar email de prueba'}
              </button>
              <span className="text-xs text-gray-400">Prueba con los datos actuales del formulario (no hace falta guardar antes)</span>
            </div>
          </div>
        )}
      </div>

      {/* Telegram */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-gray-900">✈️ Notificaciones por Telegram</h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.telegram_enabled}
              onChange={e => setConfig({ ...config, telegram_enabled: e.target.checked })}
              className="w-4 h-4" style={{ accentColor: '#0b497c' }} />
            <span className="text-sm">Habilitar</span>
          </label>
        </div>
        {config.telegram_enabled && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Bot Token {config.telegram_bot_token_set && <span className="text-green-600">(guardado)</span>}
              </label>
              <input type="password" value={telegramToken} placeholder={config.telegram_bot_token_set ? '••••••••' : 'Nuevo token'}
                onChange={e => setTelegramToken(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Chat ID</label>
              <input type="text" value={config.telegram_chat_id || ''} placeholder="123456789"
                onChange={e => setConfig({ ...config, telegram_chat_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <p className="text-xs text-gray-400">
              Cómo obtener el token: habla con <code>@BotFather</code> en Telegram y crea un bot.
              El Chat ID lo obtienes hablando con tu bot y consultando <code>getUpdates</code>.
            </p>
            <button onClick={testTelegram} disabled={testingTelegram}
              className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50" style={{ backgroundColor: '#299ac2' }}>
              {testingTelegram ? 'Enviando...' : '✈️ Enviar mensaje de prueba'}
            </button>
          </div>
        )}
      </div>

      {/* Eventos a notificar */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h3 className="font-medium text-gray-900 mb-4">🔔 Eventos a notificar</h3>
        <div className="space-y-3">
          {[
            { key: 'notify_on_apply', label: 'Aplicación de cambios (reconfigure de Squid)', desc: 'Cuando alguien pulsa "Aplicar Cambios"' },
            { key: 'notify_on_user_change', label: 'Cambios en usuarios del proxy', desc: 'Crear, editar o eliminar usuarios' },
            { key: 'notify_on_acl_change', label: 'Cambios en ACLs', desc: 'Crear, editar o eliminar ACLs' },
            { key: 'notify_on_rule_change', label: 'Cambios en reglas de acceso', desc: 'Crear, editar, reordenar o eliminar reglas' },
            { key: 'notify_on_security_alert', label: 'Alertas de seguridad', desc: 'Intentos de acceso fallidos repetidos' },
          ].map(item => (
            <label key={item.key} className="flex items-start gap-3 cursor-pointer">
              <input type="checkbox"
                checked={(config as any)[item.key]}
                onChange={e => setConfig({ ...config, [item.key]: e.target.checked } as any)}
                className="w-4 h-4 mt-0.5" style={{ accentColor: '#0b497c' }} />
              <span>
                <span className="block text-sm font-medium text-gray-800">{item.label}</span>
                <span className="block text-xs text-gray-400">{item.desc}</span>
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Guardar */}
      <button onClick={save} disabled={saving}
        className="px-6 py-3 text-white rounded-lg font-medium disabled:opacity-50" style={{ backgroundColor: '#0b497c' }}>
        {saving ? 'Guardando...' : '💾 Guardar configuración'}
      </button>

      <ToastContainer />
    </div>
  )
}