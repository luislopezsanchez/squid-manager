import { traducir } from '../i18n'
import { useState, useEffect, useRef } from 'react'
import { api, notificarCambioPendiente, getToken } from '../api/client'
import { useToast } from '../components/Toast'
import RequiereAplicar from '../components/RequiereAplicar'

export default function Kerberos() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [downloadingScript, setDownloadingScript] = useState(false)
  const keytabRef = useRef<HTMLInputElement>(null)
  const { showToast, ToastContainer } = useToast()

  const cargar = () => api.getKerberosConfig().then(setConfig).catch(() => showToast(traducir("Error al cargar la configuración de Kerberos"), 'error'))

  useEffect(() => {
    cargar().finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateKerberosConfig({
        enabled: config.enabled,
        realm: config.realm,
        proxy_fqdn: config.proxy_fqdn,
      })
      notificarCambioPendiente()
      showToast(traducir("Configuración de Kerberos guardada correctamente"), 'success')
      cargar()
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const result = await api.uploadKeytab(file)
      notificarCambioPendiente()
      showToast(result.message || traducir("Keytab subido correctamente"), 'success')
      cargar()
    } catch (err: any) {
      showToast(err.message, 'error')
    } finally {
      setUploading(false)
      if (keytabRef.current) keytabRef.current.value = ''
    }
  }

  const handleDeleteKeytab = async () => {
    setDeleting(true)
    try {
      await api.deleteKeytab()
      notificarCambioPendiente()
      showToast(traducir("Keytab eliminado"), 'success')
      cargar()
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setDeleting(false)
    }
  }

  const handleDownloadScript = async () => {
    setDownloadingScript(true)
    try {
      const res = await fetch(api.kerberosAdSetupScriptUrl(), {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail || `HTTP ${res.status}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'kerberos-ad-setup.zip'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      showToast(traducir("Script descargado. Revisalo antes de correrlo: se ejecuta con permisos de administrador de dominio."), 'success')
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setDownloadingScript(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>
  if (!config) return <div className="p-8 text-center text-ink-3">{traducir("No se pudo cargar la configuración")}</div>

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("Kerberos / Negotiate")}</h1>
      <p className="text-sm text-ink-3 mb-6">{traducir("Inicio de sesión único: los usuarios de dominio navegan sin que el navegador pida usuario y contraseña, usando el ticket Kerberos de su sesión de Windows.")}</p>

      {/* Estado */}
      <div className={`rounded-xl p-4 mb-6 border ${config.enabled ? 'bg-green-50 border-green-200' : 'bg-brand-50 border-line'}`}>
        <div className="flex items-center gap-3">
          <span className={`inline-flex h-3 w-3 rounded-full ${config.enabled ? 'bg-ok' : 'bg-ink-3'}`} />
          <span className="font-medium text-ink">
            {config.enabled ? traducir('Kerberos activado') : traducir('Kerberos desactivado')}
          </span>
          <label className="ml-auto flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={e => setConfig({ ...config, enabled: e.target.checked })}
              className="w-5 h-5 rounded text-primary-600"
            />
            <span className="text-sm text-ink-2">{traducir("Habilitar")}</span>
          </label>
        </div>
      </div>

      {/* Configuración */}
      <div className="card p-6 mb-6">
        <h2 className="font-medium text-ink mb-1">{traducir("Datos del dominio")}</h2>
        <p className="text-sm text-ink-3 mb-4">{traducir("Kerberos coexiste con la autenticación Basic (usuario/contraseña): activarlo no la reemplaza, solo ofrece Negotiate además. Hace falta un registro DNS que resuelva el FQDN del proxy y un keytab generado por el administrador del dominio (ver abajo).")}</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="field-label block mb-1.5">{traducir("Realm")}</label>
            <input type="text" value={config.realm} onChange={e => setConfig({ ...config, realm: e.target.value })}
              disabled={!config.enabled}
              placeholder="EMPRESA.COM" className="input font-mono text-sm disabled:opacity-50 disabled:bg-brand-50" />
            <p className="text-xs text-ink-3 mt-1">{traducir("El dominio Kerberos, normalmente el dominio de Active Directory en mayúsculas.")}</p>
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("FQDN del proxy")}</label>
            <input type="text" value={config.proxy_fqdn} onChange={e => setConfig({ ...config, proxy_fqdn: e.target.value })}
              disabled={!config.enabled}
              placeholder="proxy.empresa.com" className="input font-mono text-sm disabled:opacity-50 disabled:bg-brand-50" />
            <p className="text-xs text-ink-3 mt-1">{traducir("Debe resolver por DNS a este proxy y coincidir con el SPN del keytab (HTTP/fqdn).")}</p>
          </div>
        </div>
        {!config.enabled && (
          <p className="text-xs text-ink-3 mt-3">{traducir("Activa «Habilitar Kerberos» arriba para editar estos campos.")}</p>
        )}
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn btn-primary disabled:opacity-50"
          >
            {saving ? traducir('Guardando...') : traducir('Guardar Configuración')}
          </button>
          <RequiereAplicar />
        </div>
      </div>

      {/* Script para el Active Directory */}
      <div className="card p-6 mb-6">
        <h2 className="font-medium text-ink mb-1">{traducir("Preparar el Active Directory")}</h2>
        <p className="text-sm text-ink-3 mb-4">
          {traducir("Script de PowerShell para correr en el Active Directory: crea la cuenta de servicio (si no existe) y genera el keytab con ktpass -crypto All, con el Realm y el FQDN de abajo ya completados — evita el error más común del setup manual, que es copiar el script de la documentación y olvidarse de cambiar esos dos valores por los propios.")}
        </p>
        <button
          onClick={handleDownloadScript}
          disabled={downloadingScript || !config.realm || !config.proxy_fqdn}
          className="btn btn-primary disabled:opacity-50"
          title={!config.realm || !config.proxy_fqdn ? traducir("Completa y guarda Realm y FQDN del proxy primero") : undefined}
        >
          {downloadingScript ? traducir('Generando…') : traducir('Descargar script de configuración (Windows Server) (.zip)')}
        </button>
        {(!config.realm || !config.proxy_fqdn) && (
          <p className="text-xs text-ink-3 mt-2">{traducir("Completa y guarda Realm y FQDN del proxy arriba para poder generarlo.")}</p>
        )}
        <p className="text-xs text-ink-3 mt-2">
          {traducir("Trae dos archivos: kerberos-ad-setup.ps1 (revisalo antes de correrlo, como cualquier script que corre con permisos de administrador de dominio) y Ejecutar.cmd, un lanzador para el primero. Windows bloquea por defecto cualquier .ps1 sin firma digital, y el .cmd evita ese error sin tocar la política de ejecución del sistema — hacé doble clic en Ejecutar.cmd, no en el .ps1 directamente. No incluye ninguna contraseña: la pide por consola al ejecutarse y no la guarda en ningún lado. Requiere el módulo ActiveDirectory (RSAT) y ktpass en la máquina donde se corra.")}
        </p>
      </div>

      {/* Keytab */}
      <div className="card p-6">
        <h2 className="font-medium text-ink mb-1">{traducir("Archivo keytab")}</h2>
        <p className="text-sm text-ink-3 mb-4">{traducir("El keytab lo genera el administrador del Active Directory (por ejemplo con ktpass), no SquidManager. Debe corresponder a la cuenta de servicio con el SPN HTTP/<FQDN del proxy> y cubrir todos los tipos de cifrado (-crypto All), porque el tipo de cifrado real que use el KDC no se puede predecir de antemano.")}</p>

        {config.keytab_uploaded ? (
          <div className="rounded-lg border border-line bg-brand-50 p-4 mb-4 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="font-medium text-ink text-sm">{config.keytab_filename}</p>
              {config.keytab_uploaded_at && (
                <p className="text-xs text-ink-3 mt-0.5">
                  {traducir("Subido el")} {new Date(config.keytab_uploaded_at).toLocaleString()}
                </p>
              )}
            </div>
            <button
              onClick={handleDeleteKeytab}
              disabled={deleting}
              className="px-4 py-2 border border-line rounded-lg font-medium text-sm hover:bg-red-50 hover:text-red-700 hover:border-red-200 disabled:opacity-50"
            >
              {deleting ? traducir('Eliminando…') : traducir('Eliminar keytab')}
            </button>
          </div>
        ) : (
          <div className="rounded-lg border border-line bg-brand-50 p-4 mb-4 text-sm text-ink-3">
            {traducir("Todavía no se subió ningún keytab. Sin él, Kerberos no se ofrecerá aunque esté activado arriba.")}
          </div>
        )}

        <input ref={keytabRef} type="file" accept=".keytab" onChange={handleUpload} className="hidden" id="keytab-input" />
        <button
          onClick={() => keytabRef.current?.click()}
          disabled={uploading}
          className="btn btn-primary disabled:opacity-50"
        >
          {uploading ? traducir('Subiendo…') : (config.keytab_uploaded ? traducir('Reemplazar keytab') : traducir('Subir keytab'))}
        </button>
        <p className="text-xs text-ink-3 mt-3">
          {traducir("Después de subir o eliminar el keytab, pulsa \"Aplicar cambios\" para que Squid empiece a usarlo.")}
        </p>
      </div>
    </div>
  )
}
