import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

interface NotifConfig {
  email_enabled: boolean
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
      showToast(traducir("Configuración guardada correctamente"), 'success')
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
    if (!config.email_recipients) { showToast(traducir("Falta el destinatario (email)"), 'error'); return }

    setTestingEmail(true)
    try {
      const r = await api.testEmail({ email_recipients: config.email_recipients })
      showToast(r.message, r.ok ? 'success' : 'error')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setTestingEmail(false)
    }
  }

  const testTelegram = async () => {
    if (!config) return
    if (!telegramToken && !config.telegram_bot_token_set) { showToast(traducir("Falta el token del bot de Telegram"), 'error'); return }
    if (!config.telegram_chat_id) { showToast(traducir("Falta el Chat ID de Telegram"), 'error'); return }

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

  if (loading || !config) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-6" style={{ color: '#0A2C48' }}>{traducir("Notificaciones")}</h1>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-xs text-blue-800">{traducir("Configura alertas por email y/o Telegram para enterarte de cambios críticos en el proxy. Guarda la configuración primero, o usa los botones de prueba para validar los datos actuales del formulario.")}</div>

      {/* Email */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-ink">{traducir("Notificaciones por correo")}</h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.email_enabled}
              onChange={e => setConfig({ ...config, email_enabled: e.target.checked })}
              className="w-4 h-4" style={{ accentColor: '#0B497C' }} />
            <span className="text-sm">{traducir("Habilitar")}</span>
          </label>
        </div>
        {config.email_enabled && (
          <div className="space-y-3">
            <p className="text-xs text-ink-3 bg-blue-50 border border-blue-200 rounded-lg p-3">
              {traducir("El servidor SMTP se configura una sola vez para todo SquidManager en")}{' '}
              <Link to="/smtp" className="text-brand-700 font-medium underline">{traducir("Sistema > SMTP")}</Link>.
            </p>
            <div>
              <label htmlFor="email-recipients" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Destinatarios (separados por coma)")}</label>
              <input id="email-recipients" type="text" value={config.email_recipients || ''} placeholder={traducir("admin1@empresa.com, admin2@empresa.com")}
                onChange={e => setConfig({ ...config, email_recipients: e.target.value })}
                className="input text-sm" />
            </div>
            <div className="flex items-center gap-3">
              <button onClick={testEmail} disabled={testingEmail}
                className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50" style={{ backgroundColor: '#48B3D0' }}>
                {testingEmail ? traducir('Enviando…') : traducir('Enviar correo de prueba')}
              </button>
              <span className="text-xs text-ink-3">{traducir("Usa el servidor SMTP ya guardado en Sistema > SMTP")}</span>
            </div>
          </div>
        )}
      </div>

      {/* Telegram */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-ink">{traducir("Notificaciones por Telegram")}</h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.telegram_enabled}
              onChange={e => setConfig({ ...config, telegram_enabled: e.target.checked })}
              className="w-4 h-4" style={{ accentColor: '#0B497C' }} />
            <span className="text-sm">{traducir("Habilitar")}</span>
          </label>
        </div>
        {config.telegram_enabled && (
          <div className="space-y-3">
            <div>
              <label htmlFor="telegram-token" className="block text-xs font-medium text-ink-3 mb-1">
                Bot Token {config.telegram_bot_token_set && <span className="text-ok">{traducir("(guardado)")}</span>}
              </label>
              <input id="telegram-token" type="password" value={telegramToken} placeholder={config.telegram_bot_token_set ? '••••••••' : traducir('Nuevo token')}
                onChange={e => setTelegramToken(e.target.value)}
                className="input text-sm" />
            </div>
            <div>
              <label htmlFor="telegram-chat-id" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Chat ID")}</label>
              <input id="telegram-chat-id" type="text" value={config.telegram_chat_id || ''} placeholder="123456789"
                onChange={e => setConfig({ ...config, telegram_chat_id: e.target.value })}
                className="input text-sm" />
            </div>
            <p className="text-xs text-ink-3">
              Cómo obtener el token: habla con <code>{traducir("@BotFather")}</code> en Telegram y crea un bot.
              El Chat ID lo obtienes hablando con tu bot y consultando <code>{traducir("getUpdates")}</code>.
            </p>
            <button onClick={testTelegram} disabled={testingTelegram}
              className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50" style={{ backgroundColor: '#48B3D0' }}>
              {testingTelegram ? traducir('Enviando…') : traducir('Enviar mensaje de prueba')}
            </button>
          </div>
        )}
      </div>

      {/* Eventos a notificar */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-4">{traducir("Eventos a notificar")}</h3>
        <div className="space-y-3">
          {[
            { key: 'notify_on_apply', label: traducir("Aplicación de cambios (reconfigure de Squid)"), desc: 'Cuando alguien pulsa "Aplicar Cambios"' },
            { key: 'notify_on_user_change', label: traducir("Cambios en usuarios del proxy"), desc: 'Crear, editar o eliminar usuarios' },
            { key: 'notify_on_acl_change', label: traducir("Cambios en ACLs"), desc: 'Crear, editar o eliminar ACLs' },
            { key: 'notify_on_rule_change', label: traducir("Cambios en reglas de acceso"), desc: 'Crear, editar, reordenar o eliminar reglas' },
            { key: 'notify_on_security_alert', label: traducir("Alertas de seguridad"), desc: 'Intentos de acceso fallidos repetidos' },
          ].map(item => (
            <label key={item.key} className="flex items-start gap-3 cursor-pointer">
              <input type="checkbox"
                checked={(config as any)[item.key]}
                onChange={e => setConfig({ ...config, [item.key]: e.target.checked } as any)}
                className="w-4 h-4 mt-0.5" style={{ accentColor: '#0B497C' }} />
              <span>
                <span className="block text-sm font-medium text-ink">{item.label}</span>
                <span className="block text-xs text-ink-3">{item.desc}</span>
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Guardar */}
      <button onClick={save} disabled={saving}
        className="px-6 py-3 text-white rounded-lg font-medium disabled:opacity-50" style={{ backgroundColor: '#0B497C' }}>
        {saving ? traducir('Guardando…') : traducir('Guardar configuración')}
      </button>

      <ToastContainer />
    </div>
  )
}