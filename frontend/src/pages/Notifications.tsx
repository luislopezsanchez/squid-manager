import { traducir, idiomaActual } from '../i18n'
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { LoadingState, ErrorState } from '../components/AsyncState'

interface NotifConfig {
  email_enabled: boolean
  email_recipients: string | null
  telegram_enabled: boolean
  telegram_bot_token_set: boolean
  telegram_chat_id: string | null
  xmpp_enabled: boolean
  xmpp_host: string | null
  xmpp_port: number
  xmpp_jid: string | null
  xmpp_password_set: boolean
  xmpp_encryption: 'none' | 'starttls' | 'ssl'
  xmpp_verify_cert: boolean
  xmpp_recipients: string | null
  xmpp_room: string | null
  notify_on_apply: boolean
  notify_on_user_change: boolean
  notify_on_acl_change: boolean
  notify_on_rule_change: boolean
  notify_on_security_alert: boolean
  notify_on_node_down: boolean
  notify_on_quota_reached: boolean
  notify_on_blocked_access: boolean
  blocked_threshold: number
  daily_report_enabled: boolean
  daily_report_time: string
  daily_report_requisitos: { smtp: boolean; admin_con_email: boolean; destinatarios: string[]; ok: boolean }
}

export default function Notifications() {
  const [config, setConfig] = useState<NotifConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [telegramToken, setTelegramToken] = useState('')
  const [xmppPassword, setXmppPassword] = useState('')
  const [testingXmpp, setTestingXmpp] = useState(false)
  const [testingEmail, setTestingEmail] = useState(false)
  const [testingTelegram, setTestingTelegram] = useState(false)
  const [enviandoReporte, setEnviandoReporte] = useState(false)
  const { showToast, ToastContainer } = useToast()

  const cargar = () => {
    setLoading(true)
    api.getNotificationConfig().then(r => { setConfig(r); setLoadError(false) })
      .catch(e => { showToast(e.message, 'error'); setLoadError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { cargar() }, [])

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
        xmpp_enabled: config.xmpp_enabled,
        xmpp_host: config.xmpp_host,
        xmpp_port: Number(config.xmpp_port) || 5222,
        xmpp_jid: config.xmpp_jid,
        xmpp_password: xmppPassword || undefined,
        xmpp_encryption: config.xmpp_encryption,
        xmpp_verify_cert: config.xmpp_verify_cert,
        xmpp_recipients: config.xmpp_recipients,
        xmpp_room: config.xmpp_room,
        notify_on_apply: config.notify_on_apply,
        notify_on_user_change: config.notify_on_user_change,
        notify_on_acl_change: config.notify_on_acl_change,
        notify_on_rule_change: config.notify_on_rule_change,
        notify_on_security_alert: config.notify_on_security_alert,
        notify_on_node_down: config.notify_on_node_down,
        notify_on_quota_reached: config.notify_on_quota_reached,
        notify_on_blocked_access: config.notify_on_blocked_access,
        blocked_threshold: Number(config.blocked_threshold) || 10,
        daily_report_enabled: config.daily_report_enabled,
        daily_report_time: config.daily_report_time,
        idioma: idiomaActual(),
      }
      await api.updateNotificationConfig(payload)
      showToast(traducir("Configuración guardada correctamente"), 'success')
      setTelegramToken('')
      setXmppPassword('')
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

  const enviarReporte = async () => {
    setEnviandoReporte(true)
    try {
      const r = await api.sendDailyReportNow()
      showToast(r.message, r.ok ? 'success' : 'error')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setEnviandoReporte(false)
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

  const testXmpp = async () => {
    if (!config) return
    if (!config.xmpp_host) { showToast(traducir("Falta el servidor XMPP"), 'error'); return }
    if (!config.xmpp_jid) { showToast(traducir("Falta la cuenta XMPP (JID)"), 'error'); return }
    if (!xmppPassword && !config.xmpp_password_set) { showToast(traducir("Falta la contraseña de XMPP"), 'error'); return }
    if (!config.xmpp_recipients && !config.xmpp_room) { showToast(traducir("Falta al menos un destinatario o una sala de XMPP"), 'error'); return }

    setTestingXmpp(true)
    try {
      const r = await api.testXmpp({
        xmpp_host: config.xmpp_host,
        xmpp_port: Number(config.xmpp_port) || 5222,
        xmpp_jid: config.xmpp_jid,
        xmpp_password: xmppPassword || undefined,
        xmpp_encryption: config.xmpp_encryption,
        xmpp_verify_cert: config.xmpp_verify_cert,
        xmpp_recipients: config.xmpp_recipients || undefined,
        xmpp_room: config.xmpp_room || undefined,
      })
      showToast(r.message, r.ok ? 'success' : 'error')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setTestingXmpp(false)
    }
  }

  if (loading) return <LoadingState />
  if (loadError || !config) return <ErrorState onRetry={cargar} />

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-6" style={{ color: '#0A2C48' }}>{traducir("Notificaciones")}</h1>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-xs text-blue-800">{traducir("Configura alertas por email, Telegram y/o XMPP (chat interno) para enterarte de cambios críticos en el proxy. Guarda la configuración primero, o usa los botones de prueba para validar los datos actuales del formulario.")}</div>

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

      {/* XMPP */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium text-ink">{traducir("Notificaciones por XMPP (chat interno)")}</h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config.xmpp_enabled}
              onChange={e => setConfig({ ...config, xmpp_enabled: e.target.checked })}
              className="w-4 h-4" style={{ accentColor: '#0B497C' }} />
            <span className="text-sm">{traducir("Habilitar")}</span>
          </label>
        </div>
        {config.xmpp_enabled && (
          <div className="space-y-3">
            <p className="text-xs text-ink-3">
              {traducir("SquidManager se conecta como cliente a un servidor XMPP que ya tengas (Openfire, Prosody, ejabberd…). No instala ningún servidor.")}
            </p>
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label htmlFor="xmpp-host" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Servidor (IP o nombre)")}</label>
                <input id="xmpp-host" type="text" value={config.xmpp_host || ''} placeholder="xmpp.empresa.local"
                  onChange={e => setConfig({ ...config, xmpp_host: e.target.value })} className="input text-sm" />
              </div>
              <div>
                <label htmlFor="xmpp-port" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Puerto")}</label>
                <input id="xmpp-port" type="number" min={1} max={65535} value={config.xmpp_port}
                  onChange={e => setConfig({ ...config, xmpp_port: Number(e.target.value) })} className="input text-sm" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="xmpp-jid" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Cuenta emisora (JID)")}</label>
                <input id="xmpp-jid" type="text" value={config.xmpp_jid || ''} placeholder="squid@empresa.local"
                  onChange={e => setConfig({ ...config, xmpp_jid: e.target.value })} className="input text-sm" />
              </div>
              <div>
                <label htmlFor="xmpp-password" className="block text-xs font-medium text-ink-3 mb-1">
                  {traducir("Contraseña")} {config.xmpp_password_set && <span className="text-ok">{traducir("(guardado)")}</span>}
                </label>
                <input id="xmpp-password" type="password" value={xmppPassword} autoComplete="new-password"
                  placeholder={config.xmpp_password_set ? '••••••••' : traducir('Nueva contraseña')}
                  onChange={e => setXmppPassword(e.target.value)} className="input text-sm" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="xmpp-encryption" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Cifrado")}</label>
                <select id="xmpp-encryption" value={config.xmpp_encryption} className="input text-sm"
                  onChange={e => setConfig({ ...config, xmpp_encryption: e.target.value as NotifConfig['xmpp_encryption'] })}>
                  <option value="starttls">STARTTLS (5222)</option>
                  <option value="ssl">SSL/TLS (5223)</option>
                  <option value="none">{traducir("Sin cifrar")}</option>
                </select>
              </div>
              <label className="flex items-center gap-2 cursor-pointer self-end pb-2">
                <input type="checkbox" checked={config.xmpp_verify_cert}
                  onChange={e => setConfig({ ...config, xmpp_verify_cert: e.target.checked })}
                  className="w-4 h-4" style={{ accentColor: '#0B497C' }} />
                <span className="text-sm">{traducir("Verificar certificado del servidor")}</span>
              </label>
            </div>
            {config.xmpp_encryption === 'none' && (
              <p className="text-xs text-warn bg-warn-soft rounded-lg p-3">{traducir("Sin cifrar, la contraseña y los avisos viajan en claro por la red. Úsalo solo en una red de confianza.")}</p>
            )}
            <div>
              <label htmlFor="xmpp-recipients" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Destinatarios (JID separados por comas)")}</label>
              <input id="xmpp-recipients" type="text" value={config.xmpp_recipients || ''} placeholder="admin@empresa.local, soporte@empresa.local"
                onChange={e => setConfig({ ...config, xmpp_recipients: e.target.value })} className="input text-sm" />
            </div>
            <div>
              <label htmlFor="xmpp-room" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Sala de chat (opcional)")}</label>
              <input id="xmpp-room" type="text" value={config.xmpp_room || ''} placeholder="avisos@conference.empresa.local"
                onChange={e => setConfig({ ...config, xmpp_room: e.target.value })} className="input text-sm" />
            </div>
            <button onClick={testXmpp} disabled={testingXmpp}
              className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50" style={{ backgroundColor: '#48B3D0' }}>
              {testingXmpp ? traducir('Enviando…') : traducir('Enviar mensaje de prueba')}
            </button>
          </div>
        )}
      </div>

      {/* Eventos a notificar */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-4">{traducir("Eventos a notificar")}</h3>
        <div className="space-y-3">
          {[
            { key: 'notify_on_apply', label: traducir("Aplicación de cambios (reconfigure de Squid)"), desc: traducir('Cuando alguien pulsa "Aplicar Cambios"') },
            { key: 'notify_on_user_change', label: traducir("Cambios en usuarios del proxy"), desc: traducir('Crear, editar o eliminar usuarios') },
            { key: 'notify_on_acl_change', label: traducir("Cambios en ACLs"), desc: traducir('Crear, editar o eliminar ACLs') },
            { key: 'notify_on_rule_change', label: traducir("Cambios en reglas de acceso"), desc: traducir('Crear, editar, reordenar o eliminar reglas') },
            { key: 'notify_on_security_alert', label: traducir("Alertas de seguridad"), desc: traducir("Fuerza bruta, bloqueos en racha o picos de tráfico detectados automáticamente") },
            { key: 'notify_on_node_down', label: traducir("Estado de nodos (Monitoreo Centralizado)"), desc: traducir("Un nodo configurado deja de responder, o su Squid deja de responder aunque el panel siga arriba -y cuando vuelve a estar en línea") },
            { key: 'notify_on_quota_reached', label: traducir("Cuota agotada"), desc: traducir("Un usuario o grupo llegó al límite de su cuota de navegación (se le corta o se le limita la velocidad)") },
            { key: 'notify_on_blocked_access', label: traducir("Intentos de entrar a sitios bloqueados"), desc: traducir("Un usuario insiste contra una regla de denegación: se avisa con el usuario y los sitios a los que intentó entrar") },
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
        {config.notify_on_blocked_access && (
          <div className="mt-4 pt-4 border-t border-line-soft flex flex-wrap items-center gap-3 text-sm">
            <label htmlFor="blocked-threshold" className="text-ink-2">{traducir("Avisar cuando un usuario acumule")}</label>
            <input id="blocked-threshold" type="number" min={3} max={1000} value={config.blocked_threshold}
              onChange={e => setConfig({ ...config, blocked_threshold: Number(e.target.value) })} className="input text-sm w-24" />
            <span className="text-ink-2">{traducir("peticiones bloqueadas en 10 minutos")}</span>
            <span className="text-xs text-ink-3 w-full">{traducir("Se avisa una sola vez por usuario y por hora, aunque siga intentándolo.")}</span>
          </div>
        )}
        {!config.email_enabled && !config.telegram_enabled && !config.xmpp_enabled && (
          <p className="text-xs text-warn bg-warn-soft rounded-lg p-3 mt-4">{traducir("Ningún canal está habilitado: activa el correo, Telegram o XMPP arriba para que estos avisos lleguen.")}</p>
        )}
      </div>

      {/* Reporte diario */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-medium text-ink">{traducir("Reporte diario por correo")}</h3>
          <label className={`flex items-center gap-2 ${config.daily_report_requisitos.ok ? 'cursor-pointer' : 'opacity-60 cursor-not-allowed'}`}>
            <input type="checkbox" checked={config.daily_report_enabled} disabled={!config.daily_report_requisitos.ok && !config.daily_report_enabled}
              onChange={e => setConfig({ ...config, daily_report_enabled: e.target.checked })}
              className="w-4 h-4" style={{ accentColor: '#0B497C' }} />
            <span className="text-sm">{traducir("Habilitar")}</span>
          </label>
        </div>
        <p className="text-xs text-ink-3 mb-3">{traducir("Al final del día se envía a los administradores un resumen de las últimas 24 horas: usuarios y sitios, datos y peticiones, los que más navegaron, los sitios bloqueados más intentados, cuotas agotadas y alertas detectadas.")}</p>
        <ul className="text-xs space-y-1 mb-4">
          <li className={config.daily_report_requisitos.smtp ? 'text-ok' : 'text-danger'}>
            {config.daily_report_requisitos.smtp ? '✓' : '✗'} {traducir("Servidor SMTP configurado")}{' '}
            {!config.daily_report_requisitos.smtp && <Link to="/smtp" className="underline font-medium">{traducir("Configurar SMTP")}</Link>}
          </li>
          <li className={config.daily_report_requisitos.admin_con_email ? 'text-ok' : 'text-danger'}>
            {config.daily_report_requisitos.admin_con_email ? '✓' : '✗'} {traducir("Administrador con correo")}
            {config.daily_report_requisitos.admin_con_email
              ? <span className="text-ink-3"> — {config.daily_report_requisitos.destinatarios.join(', ')}</span>
              : <>{' '}<Link to="/admins" className="underline font-medium">{traducir("Agregar un correo a la cuenta")}</Link></>}
          </li>
        </ul>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="report-time" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Hora de envío (zona horaria de la instalación)")}</label>
            <input id="report-time" type="time" value={config.daily_report_time}
              onChange={e => setConfig({ ...config, daily_report_time: e.target.value })} className="input text-sm w-32" />
          </div>
          <button onClick={enviarReporte} disabled={enviandoReporte || !config.daily_report_requisitos.ok}
            className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50" style={{ backgroundColor: '#48B3D0' }}>
            {enviandoReporte ? traducir('Enviando…') : traducir('Enviar el reporte ahora')}
          </button>
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