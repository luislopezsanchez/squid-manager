// Notificaciones: el formulario XMPP manda lo que el administrador escribió y se muestra el estado de los canales.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.hoisted(() => localStorage.setItem('idioma', 'es'))

const config = {
  email_enabled: false, email_recipients: null, telegram_enabled: false, telegram_bot_token_set: false, telegram_chat_id: null,
  xmpp_enabled: true, xmpp_host: 'xmpp.empresa.local', xmpp_port: 5222, xmpp_jid: 'squid@empresa.local', xmpp_password_set: true,
  xmpp_encryption: 'starttls', xmpp_verify_cert: true, xmpp_recipients: 'admin@empresa.local', xmpp_room: null,
  notify_on_apply: true, notify_on_user_change: false, notify_on_acl_change: false, notify_on_rule_change: false,
  notify_on_security_alert: true, notify_on_node_down: true, notify_on_quota_reached: true, notify_on_blocked_access: false,
  blocked_threshold: 10, daily_report_enabled: false, daily_report_time: '23:55',
  daily_report_requisitos: { smtp: false, admin_con_email: false, destinatarios: [], ok: false },
}
const api = vi.hoisted(() => ({
  getNotificationConfig: vi.fn(), getNotificationEstado: vi.fn(), testXmpp: vi.fn(), updateNotificationConfig: vi.fn(),
}))
vi.mock('../api/client', () => ({ api }))
vi.mock('react-router-dom', () => ({ Link: ({ children }: any) => <a>{children}</a> }))

import Notifications from '../pages/Notifications'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Notificaciones por XMPP', () => {
  it('«Enviar mensaje de prueba» manda el servidor, la cuenta y el cifrado del formulario', async () => {
    api.getNotificationConfig.mockResolvedValue(config)
    api.getNotificationEstado.mockResolvedValue({})
    api.testXmpp.mockResolvedValue({ ok: true, message: 'Mensaje XMPP enviado a 1 destino(s)' })
    render(<Notifications />)
    await screen.findByText('Notificaciones por XMPP (chat interno)')
    fireEvent.change(screen.getByLabelText('Servidor (IP o nombre)'), { target: { value: '10.0.0.7' } })
    fireEvent.change(screen.getByLabelText('Cifrado'), { target: { value: 'ssl' } })
    const botones = screen.getAllByText('Enviar mensaje de prueba')
    fireEvent.click(botones[botones.length - 1])
    await waitFor(() => expect(api.testXmpp).toHaveBeenCalledTimes(1))
    expect(api.testXmpp.mock.calls[0][0]).toMatchObject({
      xmpp_host: '10.0.0.7', xmpp_port: 5222, xmpp_jid: 'squid@empresa.local', xmpp_encryption: 'ssl',
      xmpp_verify_cert: true, xmpp_recipients: 'admin@empresa.local',
    })
    expect(api.testXmpp.mock.calls[0][0].xmpp_password).toBeUndefined() // no se reenvía la clave guardada
  })

  it('muestra cuando un canal está en pausa por fallar varias veces seguidas', async () => {
    api.getNotificationConfig.mockResolvedValue(config)
    api.getNotificationEstado.mockResolvedValue({
      xmpp: { estado: 'pausado', fallos_seguidos: 3, descartados: 4, ultimo_error: 'No se pudo conectar al servidor XMPP',
              ultimo_error_en: Date.now() / 1000 - 120, ultimo_ok_en: null, pausado_segundos: 240 },
    })
    render(<Notifications />)
    expect(await screen.findByText(/Canal en pausa 4 min más/)).toBeTruthy()
    expect(screen.getByText('No se pudo conectar al servidor XMPP')).toBeTruthy()
  })
})
