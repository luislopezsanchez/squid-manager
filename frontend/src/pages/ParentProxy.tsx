import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { api, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import RequiereAplicar from '../components/RequiereAplicar'

interface Config {
  enabled: boolean
  host: string
  port: number
  username: string
  password: string
  never_direct: boolean
  direct_domains: string
  ca_cert: string
  auth_method: 'fixed' | 'passthru'
}

const VACIA: Config = {
  enabled: false,
  host: '',
  port: 3128,
  username: '',
  password: '',
  never_direct: true,
  direct_domains: '',
  ca_cert: '',
  auth_method: 'fixed',
}

export default function ParentProxy() {
  const [config, setConfig] = useState<Config>(VACIA)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [resultado, setResultado] = useState<{ ok: boolean; message: string } | null>(null)
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    api.getParentProxy()
      .then((d: Config) => setConfig({ ...VACIA, ...d }))
      .catch(() => showToast(traducir("Error al cargar la configuración"), 'error'))
      .finally(() => setLoading(false))
  }, [])

  const set = (campo: keyof Config, valor: any) => {
    setConfig(c => ({ ...c, [campo]: valor }))
    setResultado(null)
  }

  // El archivo se lee en el navegador y rellena el campo, en lugar de subirlo:
  // así se ve lo que se va a guardar antes de guardarlo, y el backend no
  // necesita un endpoint aparte para recibir ficheros.
  const cargarArchivo = (e: React.ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0]
    if (!archivo) return

    const lector = new FileReader()
    lector.onload = () => {
      const texto = String(lector.result || '')
      if (!texto.includes('-----BEGIN CERTIFICATE-----')) {
        showToast(
          `«${archivo.name}» no contiene un certificado en formato PEM. ` +
          'Si es binario (DER), conviértelo antes: ' +
          'openssl x509 -inform der -in cert.der -out cert.pem',
          'error',
        )
        return
      }
      set('ca_cert', texto.trim())
      showToast(`Certificado cargado desde ${archivo.name}`)
    }
    lector.onerror = () => showToast(traducir("No se pudo leer el archivo"), 'error')
    lector.readAsText(archivo)

    // Permite volver a elegir el mismo archivo si hizo falta corregirlo.
    e.target.value = ''
  }

  const probar = async () => {
    setTesting(true)
    setResultado(null)
    try {
      setResultado(await api.testParentProxy({
        host: config.host,
        port: config.port,
        username: config.username,
        password: config.password,
      }))
    } catch (e: any) {
      setResultado({ ok: false, message: e.message })
    } finally {
      setTesting(false)
    }
  }

  const guardar = async () => {
    setSaving(true)
    try {
      const r = await api.updateParentProxy(config)
      if (r.status === 'error') {
        showToast(r.message, 'error')
      } else {
        notificarCambioPendiente()
        showToast(traducir("Configuración guardada. Aplica los cambios para que surta efecto."))
      }
    } catch (e: any) {
      showToast(`Error al guardar: ${e.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  return (
    <div className="p-6 md:p-7 max-w-3xl">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Proxy padre")}</h1>
      <p className="text-sm text-ink-3 mb-6">{traducir("Salir a Internet a través de otro proxy. Necesario en redes donde el cortafuegos no permite la salida directa y todo el tráfico debe pasar por el proxy corporativo.")}</p>

      <div className="card p-5 mb-5">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={e => set('enabled', e.target.checked)}
            className="w-4 h-4"
          />
          <div>
            <span className="text-sm font-medium text-ink-2">{traducir("Usar un proxy padre")}</span>
            <p className="text-xs text-ink-3 mt-0.5">{traducir("Apagado, SquidManager sale directamente a Internet.")}</p>
          </div>
        </label>
      </div>

      <div className={config.enabled ? '' : 'opacity-50 pointer-events-none'}>
        <div className="card p-5 mb-5 space-y-4">
          <h2 className="text-base font-bold text-ink">{traducir("Dirección")}</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label htmlFor="parent-proxy-host" className="block text-sm font-medium text-ink-2 mb-1">{traducir("Servidor")}</label>
              <input
                id="parent-proxy-host"
                type="text"
                value={config.host}
                onChange={e => set('host', e.target.value)}
                placeholder="proxy.empresa.local"
                className="w-full px-3 py-1.5 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
              />
            </div>
            <div>
              <label htmlFor="parent-proxy-port" className="block text-sm font-medium text-ink-2 mb-1">{traducir("Puerto")}</label>
              <input
                id="parent-proxy-port"
                type="number"
                value={config.port}
                onChange={e => set('port', parseInt(e.target.value) || 0)}
                className="w-full px-3 py-1.5 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
              />
            </div>
          </div>
        </div>

        <div className="card p-5 mb-5 space-y-4">
          <div>
            <h2 className="text-base font-bold text-ink">{traducir("Credenciales")}</h2>
            <p className="text-xs text-ink-3 mt-0.5">{traducir("Opcionales: muchos proxies internos no piden autenticación. Déjalo vacío si el tuyo no la exige.")}</p>
          </div>

          <div>
            <label htmlFor="parent-proxy-auth-method" className="block text-sm font-medium text-ink-2 mb-1">{traducir("Cómo presentar credenciales al padre")}</label>
            <select
              id="parent-proxy-auth-method"
              value={config.auth_method}
              onChange={e => set('auth_method', e.target.value as Config['auth_method'])}
              className="w-full px-3 py-1.5 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 text-sm"
            >
              <option value="fixed">{traducir('Fijas — usuario y contraseña de aquí abajo (solo Basic)')}</option>
              <option value="passthru">{traducir('Reenviar las del cliente (passthru) — para un padre que exige Digest, NTLM o Negotiate')}</option>
            </select>
          </div>

          {config.auth_method === 'fixed' ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="parent-proxy-username" className="block text-sm font-medium text-ink-2 mb-1">{traducir("Usuario")}</label>
                  <input
                    id="parent-proxy-username"
                    type="text"
                    value={config.username}
                    onChange={e => set('username', e.target.value)}
                    autoComplete="off"
                    className="w-full px-3 py-1.5 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="parent-proxy-password" className="block text-sm font-medium text-ink-2 mb-1">{traducir("Contraseña")}</label>
                  <input
                    id="parent-proxy-password"
                    type="password"
                    value={config.password}
                    onChange={e => set('password', e.target.value)}
                    autoComplete="new-password"
                    className="w-full px-3 py-1.5 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
                  />
                </div>
              </div>

              <p className="text-xs text-ink-3">
                Squid solo sabe presentar autenticación <strong>{traducir("básica")}</strong>{traducir("a un proxy padre con credenciales fijas. Si el tuyo exige NTLM, Digest o Kerberos, la prueba de aquí abajo te lo dirá: no se resuelve con usuario y contraseña, hace falta 'passthru'.")}</p>
            </>
          ) : (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
              {traducir("'Passthru' reenvía tal cual las credenciales que ya trae el cliente hacia el padre. Es la única forma de llegar a un padre que exige Digest, NTLM o Negotiate — pero no se puede combinar con que este mismo SquidManager autentique a sus propios clientes (HTTP solo permite una credencial por petición). Si hay usuarios locales habilitados, LDAP o Kerberos activos, guardar esto se va a rechazar hasta que los desactives.")}
            </p>
          )}
        </div>

        <div className="card p-5 mb-5 space-y-4">
          <h2 className="text-base font-bold text-ink">{traducir("Comportamiento")}</h2>

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={config.never_direct}
              onChange={e => set('never_direct', e.target.checked)}
              className="w-4 h-4 mt-0.5"
            />
            <div>
              <span className="text-sm font-medium text-ink-2">{traducir("No intentar nunca la salida directa")}</span>
              <p className="text-xs text-ink-3 mt-0.5">{traducir("Recomendado cuando hay proxy corporativo: si el cortafuegos bloquea la salida directa, intentarla solo añade una espera antes de fallar igual. Desactívalo solo si tu red permite ambas salidas.")}</p>
            </div>
          </label>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="parent-proxy-ca-cert" className="block text-sm font-medium text-ink-2">{traducir("Certificado CA del proxy padre")}</label>
              <label className="btn btn-ghost btn-sm cursor-pointer">
                Cargar desde archivo
                <input
                  type="file"
                  accept=".crt,.pem,.cer,.txt,application/x-x509-ca-cert"
                  onChange={cargarArchivo}
                  className="hidden"
                />
              </label>
            </div>
            <textarea
              id="parent-proxy-ca-cert"
              value={config.ca_cert}
              onChange={e => set('ca_cert', e.target.value)}
              rows={4}
              placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              className="w-full px-3 py-2 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-xs"
            />
            <p className="text-xs text-ink-3 mt-1">
              Solo si el padre <strong>{traducir("también intercepta HTTPS")}</strong> (otro
              SquidManager, o cualquier proxy con inspección TLS). Al reenviarle
              el tráfico presenta su propio certificado, y sin esto Squid lo
              rechaza por autofirmado y <strong>{traducir("ninguna web HTTPS carga")}</strong>{traducir(". Si el padre es otro SquidManager, descárgalo de su panel en «Certificado CA» y cárgalo aquí con el botón, o pega su contenido.")}</p>
          </div>

          <div>
            <label htmlFor="parent-proxy-direct-domains" className="block text-sm font-medium text-ink-2 mb-1">{traducir("Destinos que no pasan por el padre")}</label>
            <textarea
              id="parent-proxy-direct-domains"
              value={config.direct_domains}
              onChange={e => set('direct_domains', e.target.value)}
              rows={3}
              placeholder={traducir(".intranet.local .empresa.com")}
              className="w-full px-3 py-2 border border-line rounded-lg focus:ring-2 focus:ring-primary-500 font-mono text-sm"
            />
            <p className="text-xs text-ink-3 mt-1">{traducir("Normalmente la intranet. Separados por espacios o uno por línea. Un punto delante incluye los subdominios.")}</p>
          </div>
        </div>
      </div>

      {resultado && (
        <div
          className={`mb-5 text-[13px] p-3 rounded-lg ${
            resultado.ok ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
          }`}
        >
          {resultado.ok ? '✓ ' : '✕ '}{resultado.message}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button onClick={guardar} disabled={saving} className="btn btn-primary btn-sm">
          {saving ? traducir('Guardando...') : traducir('Guardar')}
        </button>
        <button
          onClick={probar}
          disabled={testing || !config.host}
          className="btn btn-ghost btn-sm"
          title={traducir("Pregunta al proxy padre sin guardar nada")}
        >
          {testing ? traducir('Probando...') : traducir('Probar conexión')}
        </button>
      </div>

      <div className="mt-4"><RequiereAplicar /></div>
      <p className="text-xs text-ink-3 mt-2">{traducir("Al pulsar «Aplicar cambios» se comprueba que el proxy padre responde. Si no lo hace, el cambio se rechaza en lugar de dejar a todos sin navegación.")}</p>
    </div>
  )
}
