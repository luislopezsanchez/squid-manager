import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { IconApple, IconDownload, IconFirefox, IconLinux, IconWindows } from '../components/Icons'
import { api, getToken } from '../api/client'
import { useToast } from '../components/Toast'

export default function CertificadoCA() {
  // El proxy corre en la misma maquina que sirve este panel.
  const proxyHost = typeof window !== 'undefined' ? window.location.hostname : 'tu-servidor'

  const [caInfo, setCaInfo] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    // Verificar si el certificado CA está disponible
    fetch('/api/squid/ca-cert', {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then(r => {
        if (r.ok) {
          setCaInfo({ available: true })
        } else {
          setCaInfo({ available: false })
        }
      })
      .catch(() => setCaInfo({ available: false }))
      .finally(() => setLoading(false))
  }, [])

  const handleDownload = () => {
    downloadArtifact('/api/squid/ca-cert', 'squidmanager-ca.crt', 'Certificado CA descargado correctamente')
  }

  const downloadArtifact = (path: string, filename: string, successMsg: string) => {
    const token = getToken()
    fetch(path, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.blob()
      })
      .then(blob => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
        showToast(successMsg)
      })
      .catch(e => showToast(`Error: ${e.message}`, 'error'))
  }

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Certificado CA de Squid")}</h1>
      <p className="text-sm text-ink-3 mb-6">{traducir("Para que los navegadores confíen en el proxy SSL Bump, debes instalar este certificado en cada equipo cliente")}</p>

      {/* Estado */}
      <div className={`rounded-xl p-4 mb-6 border ${caInfo?.available ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
        <div className="flex items-center gap-3">
          <span className={`inline-flex h-3 w-3 rounded-full ${caInfo?.available ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="font-medium text-ink">
            {caInfo?.available ? traducir('Certificado CA disponible') : traducir('Certificado CA no disponible')}
          </span>
        </div>
      </div>

      {/* Descargar */}
      {caInfo?.available && (
        <div className="card p-6 mb-6">
          <h2 className="font-medium text-ink mb-4">{traducir("Descargar certificado")}</h2>
          <button
            onClick={handleDownload}
            className="btn btn-primary px-6 py-3"
          >
            <IconDownload className="w-5 h-5" />{traducir("Descargar squidmanager-ca.crt")}</button>
        </div>
      )}

      {/* Despliegue automático */}
      {caInfo?.available && (
        <div className="card p-6 mb-6">
          <h2 className="font-medium text-ink mb-2">{traducir("Despliegue automático del certificado")}</h2>
          <p className="text-sm text-ink-3 mb-4">{traducir("Evita el trabajo manual: descarga un artefacto listo para desplegar el certificado en todos los equipos sin que cada usuario tenga que hacer pasos complicados.")}</p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Active Directory / GPO */}
            <div className="border border-line rounded-lg p-4 flex flex-col">
              <div className="stat-icon mx-auto mb-2"><IconWindows className="w-[18px] h-[18px]" /></div>
              <h3 className="font-medium text-ink mb-1">{traducir("Active Directory (GPO)")}</h3>
              <p className="text-xs text-ink-3 mb-3 flex-1">{traducir("Despliegue automático a todos los PCs del dominio. Ejecuta este script PowerShell una vez en el Domain Controller y listo.")}</p>
              <button
                onClick={() => downloadArtifact('/api/squid/ca-deploy/deploy-gpo.ps1', 'deploy-gpo.ps1', 'Script GPO descargado')}
                className="w-full px-3 py-2 text-white rounded-lg text-sm font-medium bg-blue-700 hover:bg-blue-800 inline-flex items-center justify-center gap-1.5"
              >
                <IconDownload className="w-4 h-4" /> deploy-gpo.ps1
              </button>
            </div>

            {/* Windows sin dominio */}
            <div className="border border-line rounded-lg p-4 flex flex-col">
              <div className="stat-icon mx-auto mb-2"><IconWindows className="w-[18px] h-[18px]" /></div>
              <h3 className="font-medium text-ink mb-1">{traducir("Windows (un clic)")}</h3>
              <p className="text-xs text-ink-3 mb-3 flex-1">{traducir("Para equipos sin dominio. El usuario hace doble clic en este archivo (como administrador) y el certificado se instala solo.")}</p>
              <button
                onClick={() => downloadArtifact('/api/squid/ca-deploy/install-cert.bat', 'install-cert.bat', 'Instalador .bat descargado')}
                className="w-full px-3 py-2 text-white rounded-lg text-sm font-medium bg-blue-700 hover:bg-blue-800 inline-flex items-center justify-center gap-1.5"
              >
                <IconDownload className="w-4 h-4" /> install-cert.bat
              </button>
            </div>

            {/* iOS / macOS */}
            <div className="border border-line rounded-lg p-4 flex flex-col">
              <div className="stat-icon mx-auto mb-2"><IconApple className="w-[18px] h-[18px]" /></div>
              <h3 className="font-medium text-ink mb-1">{traducir("iOS / macOS")}</h3>
              <p className="text-xs text-ink-3 mb-3 flex-1">{traducir("Perfil de configuración para iPhone, iPad y Mac. Se puede instalar por doble clic (Mac) o enviar por MDM.")}</p>
              <button
                onClick={() => downloadArtifact('/api/squid/ca-deploy/cert.mobileconfig', 'squidmanager-ca.mobileconfig', 'Perfil mobileconfig descargado')}
                className="w-full px-3 py-2 text-white rounded-lg text-sm font-medium bg-blue-700 hover:bg-blue-800 inline-flex items-center justify-center gap-1.5"
              >
                <IconDownload className="w-4 h-4" /> cert.mobileconfig
              </button>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-4 text-xs text-amber-800">
            <strong>{traducir("Importante:")}</strong>{traducir("la CA se genera una vez y persiste. Si borras los datos donde vive —los volúmenes en Docker, /etc/squid en una instalación nativa— se generará una CA nueva y tendrás que redesplegar el certificado.")}</div>
        </div>
      )}

      {/* Instrucciones */}
      <div className="card p-6 mb-6">
        <h2 className="font-medium text-ink mb-4">{traducir("Instrucciones de instalación")}</h2>

        <div className="space-y-6">
          {/* Windows / Chrome / Edge */}
          <div>
            <h3 className="font-medium text-ink mb-2 flex items-center gap-2">
              <IconWindows className="w-[17px] h-[17px] text-brand-600" />{traducir("Windows (Chrome / Edge / Brave)")}</h3>
            <ol className="list-decimal list-inside text-sm text-ink-2 space-y-1 ml-4">
              <li>Doble clic en el archivo <code className="bg-line-soft px-1 rounded">squidmanager-ca.crt</code> descargado</li>
              <li>{traducir("Click en \"Instalar certificado...\"")}</li>
              <li>{traducir("Seleccionar \"Equipo local\" (requiere permisos de administrador)")}</li>
              <li>{traducir("Seleccionar \"Colocar todos los certificados en el siguiente almacén\"")}</li>
              <li>Click en "Examinar..." y seleccionar <strong>{traducir("\"Entidades de certificación raíz de confianza\"")}</strong></li>
              <li>{traducir("Click en \"Siguiente\" y luego \"Finalizar\"")}</li>
              <li>{traducir("Reiniciar el navegador")}</li>
            </ol>
          </div>

          {/* Firefox */}
          <div>
            <h3 className="font-medium text-ink mb-2 flex items-center gap-2">
              <IconFirefox className="w-[17px] h-[17px] text-brand-600" />{traducir("Firefox (Windows / Linux / Mac)")}</h3>
            <ol className="list-decimal list-inside text-sm text-ink-2 space-y-1 ml-4">
              <li>Abrir Firefox y escribir <code className="bg-line-soft px-1 rounded">{traducir("about:preferences")}</code>{traducir("en la barra")}</li>
              <li>{traducir("Buscar \"certificados\" y click en \"Ver certificados...\"")}</li>
              <li>{traducir("En la pestaña «Entidades», pulsa «Importar…»")}</li>
              <li>Seleccionar el archivo <code className="bg-line-soft px-1 rounded">squidmanager-ca.crt</code></li>
              <li>{traducir("Marcar \"Confiar en esta CA para identificar sitios web\"")}</li>
              <li>{traducir("Click en \"Aceptar\"")}</li>
            </ol>
          </div>

          {/* Linux */}
          <div>
            <h3 className="font-medium text-ink mb-2 flex items-center gap-2">
              <IconLinux className="w-[17px] h-[17px] text-brand-600" />{traducir("Linux (sistema)")}</h3>
            <div className="rounded-lg p-3 font-mono text-sm text-brand-300" style={{ background: '#0A2C48' }}>
              <p># Ubuntu / Debian</p>
              <p>{traducir("sudo cp squidmanager-ca.crt /usr/local/share/ca-certificates/")}</p>
              <p>{traducir("sudo update-ca-certificates")}</p>
              <p className="mt-2"># CentOS / RHEL</p>
              <p>{traducir("sudo cp squidmanager-ca.crt /etc/pki/ca-trust/source/anchors/")}</p>
              <p>{traducir("sudo update-ca-trust")}</p>
            </div>
          </div>

          {/* Mac */}
          <div>
            <h3 className="font-medium text-ink mb-2 flex items-center gap-2">
              <IconApple className="w-[17px] h-[17px] text-brand-600" />{traducir("macOS")}</h3>
            <ol className="list-decimal list-inside text-sm text-ink-2 space-y-1 ml-4">
              <li>Doble clic en <code className="bg-line-soft px-1 rounded">squidmanager-ca.crt</code></li>
              <li>{traducir("Se abre \"Acceso a Llaveros\" (Keychain Access)")}</li>
              <li>{traducir("Buscar \"SquidManager CA\" y doble clic")}</li>
              <li>{traducir("En la sección «Confianza», elige «Confiar siempre»")}</li>
              <li>{traducir("Cerrar y escribir contraseña de administrador")}</li>
              <li>{traducir("Reiniciar el navegador")}</li>
            </ol>
          </div>
        </div>
      </div>

      {/* Configuración del proxy en el navegador */}
      <div className="bg-blue-50 rounded-xl p-6 border border-blue-100">
        <h2 className="font-medium text-blue-900 mb-3">{traducir("Configurar proxy en el navegador")}</h2>
        <p className="text-sm text-blue-700 mb-3">{traducir("Después de instalar el certificado, configura tu navegador o sistema con estos datos:")}</p>
        <div className="bg-white rounded-lg p-4 border border-blue-100">
          <table className="table-panel">
            <tbody>
              <tr><td className="font-medium text-ink-2 py-1">{traducir("Tipo de proxy:")}</td><td className="text-ink-2">{traducir("HTTP / HTTPS")}</td></tr>
              <tr><td className="font-medium text-ink-2 py-1">{traducir("Dirección:")}</td><td className="text-ink-2 font-mono">{proxyHost}</td></tr>
              <tr><td className="font-medium text-ink-2 py-1">{traducir("Puerto:")}</td><td className="text-ink-2 font-mono">3128</td></tr>
              <tr><td className="font-medium text-ink-2 py-1">{traducir("Usuario:")}</td><td className="text-ink-2 font-mono">{traducir("tu usuario del proxy")}</td></tr>
              <tr><td className="font-medium text-ink-2 py-1">{traducir("Contraseña:")}</td><td className="text-ink-2 font-mono">{traducir("tu contraseña")}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}