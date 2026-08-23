import { useState, useRef } from 'react'
import { IconDownload, IconFile } from '../components/Icons'
import { api, getToken } from '../api/client'
import { useToast } from '../components/Toast'

export default function BackupRestore() {
  const { showToast, ToastContainer } = useToast()
  const [restoreBusy, setRestoreBusy] = useState(false)
  const [importBusy, setImportBusy] = useState(false)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [pwForm, setPwForm] = useState({ current: '', newPass: '', confirm: '' })
  const restoreRef = useRef<HTMLInputElement>(null)
  const importRef = useRef<HTMLInputElement>(null)

  const handleExport = () => {
    const token = getToken()
    fetch(api.exportBackup(), {
      headers: { Authorization: `Bearer ${token}` }
    }).then(r => r.blob()).then(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `squidmanager-backup-${new Date().toISOString().slice(0, 19).replace(/:/g, '')}.json`
      a.click()
      URL.revokeObjectURL(url)
      showToast('Backup descargado correctamente', 'success')
    }).catch(() => showToast('Error al descargar backup', 'error'))
  }

  const handleDownloadConf = () => {
    const token = getToken()
    fetch(api.downloadSquidConf(), {
      headers: { Authorization: `Bearer ${token}` }
    }).then(r => r.text()).then(text => {
      const blob = new Blob([text], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `squid.conf-${new Date().toISOString().slice(0, 10)}`
      a.click()
      URL.revokeObjectURL(url)
      showToast('squid.conf descargado', 'success')
    }).catch(() => showToast('Error al descargar squid.conf', 'error'))
  }

  const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setRestoreBusy(true)
    try {
      const result = await api.restoreBackup(file)
      showToast(`Backup restaurado: ${result.details.acls} ACLs, ${result.details.rules} reglas, ${result.details.users} usuarios`, 'success')
    } catch (err: any) {
      showToast(err.message, 'error')
    } finally {
      setRestoreBusy(false)
      if (restoreRef.current) restoreRef.current.value = ''
    }
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportBusy(true)
    try {
      const result = await api.importSquidConf(file)
      showToast(`Importado: ${result.details.acls} ACLs, ${result.details.rules} reglas, ${result.details.settings} settings`, 'success')
      if (result.details.warnings?.length > 0) {
        setTimeout(() => showToast(result.details.warnings[0], 'warning'), 3000)
      }
    } catch (err: any) {
      showToast(err.message, 'error')
    } finally {
      setImportBusy(false)
      if (importRef.current) importRef.current.value = ''
    }
  }

  const handleChangePassword = async () => {
    if (pwForm.newPass !== pwForm.confirm) {
      showToast('Las contraseñas no coinciden', 'error')
      return
    }
    if (pwForm.newPass.length < 6) {
      showToast('La contraseña debe tener al menos 6 caracteres', 'error')
      return
    }
    try {
      await api.changePassword(pwForm.current, pwForm.newPass)
      showToast('Contraseña cambiada correctamente', 'success')
      setShowPasswordModal(false)
      setPwForm({ current: '', newPass: '', confirm: '' })
    } catch (e: any) {
      showToast(e.message, 'error')
    }
  }

  return (
    <div className="p-6 md:p-7">
      <h1 className="text-2xl font-bold mb-6" style={{ color: '#0A2C48' }}>Backup, Restore y Migración</h1>

      {/* Sección: Cambiar contraseña */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-2">Cambiar contraseña</h3>
        <p className="text-sm text-ink-3 mb-4">Cambia tu propia contraseña del panel. Debes conocer la contraseña actual.</p>
        <button onClick={() => setShowPasswordModal(true)}
          className="px-4 py-2 border border-line rounded-lg text-sm font-medium hover:bg-brand-50">
          Cambiar contraseña
        </button>
      </div>

      {/* Sección: Backup de la plataforma */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-2">Backup de SquidManager</h3>
        <p className="text-sm text-ink-3 mb-4">
          Exporta toda la configuración de SquidManager (ACLs, reglas, usuarios, settings, delay pools, LDAP) a un archivo JSON.
          Este backup solo sirve para restaurar dentro de SquidManager.
        </p>
        <div className="flex gap-3 flex-wrap">
          <button onClick={handleExport}
            className="px-4 py-2 text-white rounded-lg font-medium text-sm" style={{ backgroundColor: '#0B497C' }}>
            <IconDownload /> Descargar backup (JSON)
          </button>
          <div>
            <input ref={restoreRef} type="file" accept=".json" onChange={handleRestore} className="hidden" id="restore-input" />
            <button onClick={() => restoreRef.current?.click()} disabled={restoreBusy}
              className="px-4 py-2 border border-line rounded-lg font-medium text-sm hover:bg-brand-50 disabled:opacity-50">
              {restoreBusy ? 'Restaurando…' : 'Restaurar backup'}
            </button>
          </div>
        </div>
      </div>

      {/* Sección: Exportar squid.conf */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-2">Descargar squid.conf</h3>
        <p className="text-sm text-ink-3 mb-4">
          Descarga el archivo squid.conf que SquidManager ha generado y que Squid está usando actualmente.
        </p>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-800 mb-4">
          <strong>Uso en un Squid tradicional (sin plataforma):</strong>
          <ul className="mt-2 space-y-1 list-disc list-inside">
            <li>El archivo es válido para Squid estándar, pero ajusta las rutas (<code>/var/spool/squid</code>, <code>/var/log/squid</code>) según tu distribución</li>
            <li>Los helpers de autenticación (<code>basic_ncsa_auth</code>, <code>basic_ldap_auth</code>) deben existir en el servidor destino</li>
            <li>El archivo <code>squid_passwd</code> (usuarios) debe copiarse aparte</li>
            <li>Los certificados SSL de la CA deben copiarse aparte</li>
            <li>Si usas SSL Bump, necesitas instalar <code>security_file_certgen</code> y la CA en los clientes</li>
          </ul>
        </div>
        <button onClick={handleDownloadConf}
          className="px-4 py-2 text-white rounded-lg font-medium text-sm" style={{ backgroundColor: '#48B3D0' }}>
          <IconFile /> Descargar squid.conf
        </button>
      </div>

      {/* Sección: Importar squid.conf tradicional */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-2">Importar squid.conf tradicional</h3>
        <p className="text-sm text-ink-3 mb-4">
          Si tienes un Squid configurado a mano y quieres migrar a SquidManager, sube tu squid.conf
          y la plataforma importará las ACLs, reglas, delay pools y settings básicos.
        </p>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-800 mb-4">
          <strong>Limitaciones del importador:</strong>
          <ul className="mt-2 space-y-1 list-disc list-inside">
            <li>Las ACLs simples (dstdomain, src, url_regex, etc.) se importan correctamente</li>
            <li>Las reglas http_access se importan preservando el orden</li>
            <li>Los delay pools se importan si siguen el formato estándar</li>
            <li>Los usuarios (htpasswd) <strong>NO</strong> se importan — debes crearlos manualmente</li>
            <li>Configuraciones muy complejas pueden no importarse perfectamente — revisa antes de aplicar</li>
          </ul>
        </div>
        <div>
          <input ref={importRef} type="file" accept=".conf,text/plain" onChange={handleImport} className="hidden" id="import-input" />
          <button onClick={() => importRef.current?.click()} disabled={importBusy}
            className="px-4 py-2 text-white rounded-lg font-medium text-sm disabled:opacity-50" style={{ backgroundColor: '#0B497C' }}>
            {importBusy ? 'Importando…' : 'Subir squid.conf'}
          </button>
        </div>
      </div>

      {/* Modal cambiar contraseña */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowPasswordModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">Cambiar contraseña</h2>
            <div className="space-y-4">
              <div>
                <label className="field-label block mb-1.5">Contraseña actual</label>
                <input type="password" value={pwForm.current}
                  onChange={e => setPwForm({ ...pwForm, current: e.target.value })}
                  className="input" />
              </div>
              <div>
                <label className="field-label block mb-1.5">Nueva contraseña</label>
                <input type="password" value={pwForm.newPass}
                  onChange={e => setPwForm({ ...pwForm, newPass: e.target.value })}
                  className="input" />
              </div>
              <div>
                <label className="field-label block mb-1.5">Confirmar nueva contraseña</label>
                <input type="password" value={pwForm.confirm}
                  onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })}
                  className="input" />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowPasswordModal(false)} className="flex-1 px-4 py-2 border border-line rounded-lg">Cancelar</button>
              <button onClick={handleChangePassword} className="flex-1 px-4 py-2 text-white rounded-lg" style={{ backgroundColor: '#0B497C' }}>Cambiar</button>
            </div>
          </div>
        </div>
      )}

      <ToastContainer />
    </div>
  )
}