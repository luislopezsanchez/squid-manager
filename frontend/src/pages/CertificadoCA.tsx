import { useState, useEffect } from 'react'
import { api, getToken } from '../api/client'
import { useToast } from '../components/Toast'

export default function CertificadoCA() {
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
    const token = getToken()
    fetch('/api/squid/ca-cert', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'squidmanager-ca.crt'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
        showToast('Certificado CA descargado correctamente')
      })
      .catch(e => showToast(`Error: ${e.message}`, 'error'))
  }

  if (loading) return <div className="p-8 text-center text-gray-500">Cargando...</div>

  return (
    <div className="p-8">
      <ToastContainer />
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Certificado CA de Squid</h1>
      <p className="text-sm text-gray-500 mb-6">
        Para que los navegadores confíen en el proxy SSL Bump, debes instalar este certificado en cada equipo cliente
      </p>

      {/* Estado */}
      <div className={`rounded-xl p-4 mb-6 border ${caInfo?.available ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
        <div className="flex items-center gap-3">
          <span className={`inline-flex h-3 w-3 rounded-full ${caInfo?.available ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="font-medium text-gray-900">
            {caInfo?.available ? 'Certificado CA disponible' : 'Certificado CA no disponible'}
          </span>
        </div>
      </div>

      {/* Descargar */}
      {caInfo?.available && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
          <h2 className="font-medium text-gray-900 mb-4">Descargar certificado</h2>
          <button
            onClick={handleDownload}
            className="bg-primary-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-primary-700 flex items-center gap-2"
          >
            <span className="text-xl">📥</span> Descargar squidmanager-ca.crt
          </button>
        </div>
      )}

      {/* Instrucciones */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h2 className="font-medium text-gray-900 mb-4">📋 Instrucciones de instalación</h2>

        <div className="space-y-6">
          {/* Windows / Chrome / Edge */}
          <div>
            <h3 className="font-medium text-gray-800 mb-2 flex items-center gap-2">
              <span>🪟</span> Windows (Chrome / Edge / Brave)
            </h3>
            <ol className="list-decimal list-inside text-sm text-gray-600 space-y-1 ml-4">
              <li>Doble clic en el archivo <code className="bg-gray-100 px-1 rounded">squidmanager-ca.crt</code> descargado</li>
              <li>Click en "Instalar certificado..."</li>
              <li>Seleccionar "Equipo local" (requiere permisos de administrador)</li>
              <li>Seleccionar "Colocar todos los certificados en el siguiente almacén"</li>
              <li>Click en "Examinar..." y seleccionar <strong>"Entidades de certificación raíz de confianza"</strong></li>
              <li>Click en "Siguiente" y luego "Finalizar"</li>
              <li>Reiniciar el navegador</li>
            </ol>
          </div>

          {/* Firefox */}
          <div>
            <h3 className="font-medium text-gray-800 mb-2 flex items-center gap-2">
              <span>🦊</span> Firefox (Windows / Linux / Mac)
            </h3>
            <ol className="list-decimal list-inside text-sm text-gray-600 space-y-1 ml-4">
              <li>Abrir Firefox y escribir <code className="bg-gray-100 px-1 rounded">about:preferences</code> en la barra</li>
              <li>Buscar "certificados" y click en "Ver certificados..."</li>
              <li>Pestaña "Entidades" → Click en "Importar..."</li>
              <li>Seleccionar el archivo <code className="bg-gray-100 px-1 rounded">squidmanager-ca.crt</code></li>
              <li>Marcar "Confiar en esta CA para identificar sitios web"</li>
              <li>Click en "Aceptar"</li>
            </ol>
          </div>

          {/* Linux */}
          <div>
            <h3 className="font-medium text-gray-800 mb-2 flex items-center gap-2">
              <span>🐧</span> Linux (sistema)
            </h3>
            <div className="bg-gray-900 rounded-lg p-3 text-green-400 font-mono text-sm">
              <p># Ubuntu / Debian</p>
              <p>sudo cp squidmanager-ca.crt /usr/local/share/ca-certificates/</p>
              <p>sudo update-ca-certificates</p>
              <p className="mt-2"># CentOS / RHEL</p>
              <p>sudo cp squidmanager-ca.crt /etc/pki/ca-trust/source/anchors/</p>
              <p>sudo update-ca-trust</p>
            </div>
          </div>

          {/* Mac */}
          <div>
            <h3 className="font-medium text-gray-800 mb-2 flex items-center gap-2">
              <span>🍎</span> macOS
            </h3>
            <ol className="list-decimal list-inside text-sm text-gray-600 space-y-1 ml-4">
              <li>Doble clic en <code className="bg-gray-100 px-1 rounded">squidmanager-ca.crt</code></li>
              <li>Se abre "Acceso a Llaveros" (Keychain Access)</li>
              <li>Buscar "SquidManager CA" y doble clic</li>
              <li>Sección "Confianza" → Cambiar a "Confiar siempre"</li>
              <li>Cerrar y escribir contraseña de administrador</li>
              <li>Reiniciar el navegador</li>
            </ol>
          </div>
        </div>
      </div>

      {/* Configuración del proxy en el navegador */}
      <div className="bg-blue-50 rounded-xl p-6 border border-blue-100">
        <h2 className="font-medium text-blue-900 mb-3">🔧 Configurar proxy en el navegador</h2>
        <p className="text-sm text-blue-700 mb-3">
          Después de instalar el certificado, configura tu navegador o sistema con estos datos:
        </p>
        <div className="bg-white rounded-lg p-4 border border-blue-100">
          <table className="w-full text-sm">
            <tbody>
              <tr><td className="font-medium text-gray-700 py-1">Tipo de proxy:</td><td className="text-gray-600">HTTP / HTTPS</td></tr>
              <tr><td className="font-medium text-gray-700 py-1">Dirección:</td><td className="text-gray-600 font-mono">192.168.145.136</td></tr>
              <tr><td className="font-medium text-gray-700 py-1">Puerto:</td><td className="text-gray-600 font-mono">3128</td></tr>
              <tr><td className="font-medium text-gray-700 py-1">Usuario:</td><td className="text-gray-600 font-mono">testuser (o tu usuario)</td></tr>
              <tr><td className="font-medium text-gray-700 py-1">Contraseña:</td><td className="text-gray-600 font-mono">tu contraseña</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}