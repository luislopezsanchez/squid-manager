import { useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { IconMail } from '../components/Icons'

export default function Contacto() {
  const { showToast, ToastContainer } = useToast()
  const [categoria, setCategoria] = useState('sugerencia')
  const [mensaje, setMensaje] = useState('')
  const [emailRespuesta, setEmailRespuesta] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async () => {
    if (!mensaje.trim()) {
      showToast(traducir('Escribe un mensaje antes de enviar.'), 'warning')
      return
    }
    setEnviando(true)
    try {
      const r = await api.sendContact({
        categoria,
        mensaje: mensaje.trim(),
        email_respuesta: emailRespuesta.trim() || undefined,
      })
      showToast(
        r.enviado_por_email
          ? traducir('Mensaje enviado. Gracias por tu reporte.')
          : traducir('Mensaje guardado. No se pudo enviar por correo (revisa el SMTP en Notificaciones), pero quedó registrado.'),
        r.enviado_por_email ? 'success' : 'warning',
      )
      setMensaje('')
      setEmailRespuesta('')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="p-6 md:p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Contacto")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Cómo comunicarte con soporte.")}
      </p>

      <div className="card p-6 border border-line-soft space-y-4">
        <div className="flex items-center gap-3 mb-1">
          <span className="stat-icon"><IconMail /></span>
          <p className="text-sm text-ink-3">
            {traducir("Reporta un error, sugiere una mejora, o cuéntanos cualquier otra cosa sobre SquidManager.")}
          </p>
        </div>

        <div>
          <label htmlFor="contacto-categoria" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Categoría")}</label>
          <select id="contacto-categoria" value={categoria} onChange={e => setCategoria(e.target.value)}
            className="input text-sm bg-white">
            <option value="error">{traducir("Reportar un error")}</option>
            <option value="sugerencia">{traducir("Dar una sugerencia")}</option>
            <option value="otro">{traducir("Otro")}</option>
          </select>
        </div>

        <div>
          <label htmlFor="contacto-mensaje" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Mensaje")}</label>
          <textarea id="contacto-mensaje" rows={6} value={mensaje} onChange={e => setMensaje(e.target.value)}
            placeholder={traducir("Contanos con el mayor detalle posible…")}
            className="input text-sm" />
        </div>

        <div>
          <label htmlFor="contacto-email" className="block text-xs font-medium text-ink-3 mb-1">
            {traducir("Tu email (opcional, para poder responderte)")}
          </label>
          <input id="contacto-email" type="email" value={emailRespuesta} onChange={e => setEmailRespuesta(e.target.value)}
            placeholder="tu@correo.com" className="input text-sm" />
        </div>

        <button onClick={enviar} disabled={enviando}
          className="px-6 py-3 text-white rounded-lg font-medium disabled:opacity-50" style={{ backgroundColor: '#0B497C' }}>
          {enviando ? traducir('Enviando…') : traducir('Enviar mensaje')}
        </button>
      </div>

      <ToastContainer />
    </div>
  )
}
