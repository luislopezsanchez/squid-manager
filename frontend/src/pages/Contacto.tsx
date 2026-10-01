import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { useModulos } from '../utils/modules'
import { IconMail, IconInfo, IconFile, IconAssistant, IconCheck, IconShield } from '../components/Icons'

interface Info {
  app_version: string; deploy_mode: string; squid_version: string; sistema: string; python: string; panel_activo_desde_horas: number
  contacto_destino?: string
}

// Componentes de terceros que hacen posible el producto, cada uno con su propia licencia: se
// nombran para que quede claro de quién es cada cosa.
const TERCEROS: [string, string][] = [
  ['Squid', 'GPL v2+'], ['PostgreSQL / pgvector', 'PostgreSQL License'], ['nginx', 'BSD-2-Clause'],
  ['FastAPI / Starlette', 'MIT'], ['SQLAlchemy', 'MIT'], ['Pydantic', 'MIT'], ['PyJWT', 'MIT'],
  ['psycopg', 'LGPL v3'], ['ldap3', 'LGPL v3'], ['ReportLab', 'BSD'], ['openpyxl', 'MIT'],
  ['React', 'MIT'], ['Recharts', 'MIT'], ['Tailwind CSS', 'MIT'],
  ['Figtree', 'SIL OFL 1.1'], ['JetBrains Mono', 'SIL OFL 1.1'], ['HaGeZi DNS blocklists', 'GPL v3'],
]
const URL_REPO = 'https://github.com/luislopezsanchez/squid-manager'

function textoInfo(i: Info): string {
  return [
    `SquidManager ${i.app_version} (${i.deploy_mode})`,
    `Squid ${i.squid_version}`,
    i.sistema,
    `Python ${i.python}`,
    `${navigator.userAgent}`,
  ].join('\n')
}

export default function Contacto() {
  const { showToast, ToastContainer } = useToast()
  const { modulos } = useModulos()
  const [categoria, setCategoria] = useState('sugerencia')
  const [mensaje, setMensaje] = useState('')
  const [emailRespuesta, setEmailRespuesta] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [info, setInfo] = useState<Info | null>(null)
  // Para un error, adjuntar los datos técnicos es lo primero que pediría quien da soporte.
  const [adjuntar, setAdjuntar] = useState(true)

  useEffect(() => { api.getContactInfo().then(setInfo).catch(() => {}) }, [])

  const enviar = async () => {
    if (!mensaje.trim()) {
      showToast(traducir('Escribe un mensaje antes de enviar.'), 'warning')
      return
    }
    setEnviando(true)
    try {
      const cuerpo = adjuntar && info ? `${mensaje.trim()}\n\n--- ${traducir('Información técnica')} ---\n${textoInfo(info)}` : mensaje.trim()
      const r = await api.sendContact({ categoria, mensaje: cuerpo.slice(0, 5000), email_respuesta: emailRespuesta.trim() || undefined })
      showToast(
        r.enviado_por_email
          ? traducir('Mensaje enviado. Gracias por tu reporte.')
          : traducir('Mensaje guardado. No se pudo enviar por correo (revisa el SMTP en Notificaciones), pero quedó registrado.'),
        r.enviado_por_email ? 'success' : 'warning',
      )
      setMensaje(''); setEmailRespuesta('')
    } catch (e: any) {
      showToast(e.message, 'error')
    } finally {
      setEnviando(false)
    }
  }

  const copiar = async () => {
    if (!info) return
    try { await navigator.clipboard.writeText(textoInfo(info)); showToast(traducir('Información copiada'), 'success') }
    catch { showToast(traducir('No se pudo copiar: selecciona el texto a mano.'), 'warning') }
  }

  return (
    <div className="p-6 md:p-8 max-w-6xl">
      <ToastContainer />
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Contacto")}</h1>
      <p className="text-sm text-ink-3 mb-6">{traducir("Cuéntanos qué pasa o qué mejorarías. Con la información de tu instalación adjunta, podemos ayudarte más rápido.")}</p>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
        <div className="lg:col-span-3 card p-6 border border-line-soft space-y-4">
          <div className="flex items-center gap-3 mb-1">
            <span className="stat-icon"><IconMail /></span>
            <p className="text-sm text-ink-3">{traducir("Reporta un error, sugiere una mejora, o cuéntanos cualquier otra cosa sobre SquidManager.")}</p>
          </div>

          <div>
            <label htmlFor="contacto-categoria" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Categoría")}</label>
            <select id="contacto-categoria" value={categoria} onChange={e => setCategoria(e.target.value)} className="input text-sm bg-white">
              <option value="error">{traducir("Reportar un error")}</option>
              <option value="sugerencia">{traducir("Dar una sugerencia")}</option>
              <option value="otro">{traducir("Otro")}</option>
            </select>
          </div>

          <div>
            <label htmlFor="contacto-mensaje" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Mensaje")}</label>
            <textarea id="contacto-mensaje" rows={7} value={mensaje} onChange={e => setMensaje(e.target.value)}
              placeholder={categoria === 'error'
                ? traducir("Qué hacías, qué esperabas que pasara y qué pasó en realidad. Si aparece un mensaje de error, cópialo tal cual.")
                : traducir("Cuéntanos con el mayor detalle posible…")}
              className="input text-sm" />
            <p className="text-[11.5px] text-ink-3 mt-1 text-right tabular">{mensaje.length} / 5000</p>
          </div>

          <div>
            <label htmlFor="contacto-email" className="block text-xs font-medium text-ink-3 mb-1">{traducir("Tu email (opcional, para poder responderte)")}</label>
            <input id="contacto-email" type="email" value={emailRespuesta} onChange={e => setEmailRespuesta(e.target.value)} placeholder="tu@correo.com" className="input text-sm" />
          </div>

          <label className="flex items-start gap-2.5 text-sm text-ink-2 cursor-pointer">
            <input type="checkbox" className="mt-1" checked={adjuntar} onChange={e => setAdjuntar(e.target.checked)} />
            <span>
              {traducir("Adjuntar la información técnica de esta instalación")}
              <span className="block text-[12px] text-ink-3">{traducir("Versión, modo de despliegue, versión de Squid y sistema operativo. No incluye usuarios, direcciones ni claves.")}</span>
            </span>
          </label>

          {info && (
            <p className="text-[12px] text-ink-3">
              {info.contacto_destino
                ? <>{traducir("Destino de los mensajes:")} <strong className="text-ink-2">{info.contacto_destino}</strong>. {traducir("Siempre se guardan también en este servidor, y salen por el SMTP configurado en Notificaciones.")}</>
                : traducir("El envío por correo está desactivado en esta instalación: los mensajes solo se guardan en este servidor.")}
            </p>
          )}

          <button onClick={enviar} disabled={enviando} className="btn btn-primary disabled:opacity-50 px-6 py-3">
            {enviando ? traducir('Enviando…') : traducir('Enviar mensaje')}
          </button>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <section className="card p-5 border border-line-soft">
            <h2 className="text-sm font-semibold text-ink mb-3">{traducir("Antes de escribir")}</h2>
            <ul className="space-y-2.5 text-[13.5px]">
              <li><Link to="/documentacion" className="flex items-center gap-2 text-brand-700 hover:underline"><IconFile className="w-4 h-4" />{traducir("Buscar en la Documentación")}</Link></li>
              {modulos.asistente && <li><Link to="/asistente" className="flex items-center gap-2 text-brand-700 hover:underline"><IconAssistant className="w-4 h-4" />{traducir("Preguntarle al Asistente de IA")}</Link></li>}
              <li><Link to="/logs" className="flex items-center gap-2 text-brand-700 hover:underline"><IconInfo className="w-4 h-4" />{traducir("Revisar los Registros por si el error aparece ahí")}</Link></li>
            </ul>
          </section>

          <section className="card p-5 border border-line-soft">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-ink">{traducir("Tu instalación")}</h2>
              <button onClick={copiar} disabled={!info} className="btn btn-outline btn-sm">{traducir("Copiar")}</button>
            </div>
            {info ? (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
                <dt className="text-ink-3">SquidManager</dt><dd className="text-ink font-mono">v{info.app_version}</dd>
                <dt className="text-ink-3">{traducir("Despliegue")}</dt><dd className="text-ink">{info.deploy_mode === 'native' ? traducir('Nativo (sin Docker)') : 'Docker'}</dd>
                <dt className="text-ink-3">Squid</dt><dd className="text-ink font-mono">{info.squid_version}</dd>
                <dt className="text-ink-3">{traducir("Sistema")}</dt><dd className="text-ink">{info.sistema}</dd>
                <dt className="text-ink-3">Python</dt><dd className="text-ink font-mono">{info.python}</dd>
              </dl>
            ) : <p className="text-sm text-ink-3">{traducir("Cargando…")}</p>}
          </section>

          <section className="card p-5 border border-line-soft">
            <div className="flex items-center gap-3 mb-3">
              <img src="/brand/logo-64.png" alt="" className="w-10 h-10" />
              <div>
                <p className="font-semibold text-ink leading-tight">SquidManager {info ? `v${info.app_version}` : ''}</p>
                <p className="text-[12px] text-ink-3">{traducir("Proyecto 100% cubano.")}</p>
              </div>
            </div>
            <p className="text-[13px] text-ink-2"><strong>© 2026 Luis López Sánchez.</strong></p>
            <p className="text-[12.5px] text-ink-3 mt-2">{traducir("Software libre, bajo la licencia GNU AGPL-3.0 o posterior:")}</p>
            <ul className="text-[12.5px] mt-1.5 space-y-1">
              <li className="flex gap-2 text-ink-2"><IconCheck className="w-3.5 h-3.5 mt-0.5 flex-none text-ok" />{traducir("Puedes usarlo gratis, en tu empresa o con tus clientes, y modificarlo.")}</li>
              <li className="flex gap-2 text-ink-2"><IconCheck className="w-3.5 h-3.5 mt-0.5 flex-none text-ok" />{traducir("Si lo modificas y lo ofreces como servicio o lo distribuyes, publica tus cambios con la misma licencia y conserva este crédito.")}</li>
              <li className="flex gap-2 text-ink-2"><IconShield className="w-3.5 h-3.5 mt-0.5 flex-none text-danger" />{traducir("El nombre y el logo «SquidManager» están reservados: una versión modificada debe llamarse de otra forma.")}</li>
              <li className="flex gap-2 text-ink-3">{traducir("Se ofrece «tal cual», sin garantía; el autor no responde por daños derivados de su uso.")}</li>
            </ul>
            <p className="text-[12.5px] mt-2 flex flex-wrap gap-x-4 gap-y-1">
              <a href={URL_REPO} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">{traducir("Código fuente")}</a>
              <a href={`${URL_REPO}/blob/main/LICENSE`} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">{traducir("Licencia completa")}</a>
            </p>
            <details className="mt-3 text-[12px]">
              <summary className="cursor-pointer text-ink-3">{traducir("Software de terceros incluido")}</summary>
              <p className="text-ink-3 mt-1.5">{traducir("Cada componente conserva su propia licencia y a sus autores:")}</p>
              <ul className="mt-1 grid grid-cols-2 gap-x-3 text-ink-2">
                {TERCEROS.map(([n, l]) => <li key={n}>{n} <span className="text-ink-3">· {l}</span></li>)}
              </ul>
              <p className="mt-1.5"><a href={`${URL_REPO}/blob/main/THIRD_PARTY_NOTICES.md`} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">{traducir("Lista completa de licencias")}</a></p>
            </details>
          </section>
        </div>
      </div>
    </div>
  )
}
