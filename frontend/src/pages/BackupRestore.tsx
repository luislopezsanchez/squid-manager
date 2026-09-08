import { traducir } from '../i18n'
import { useState, useRef } from 'react'
import { IconDownload, IconFile } from '../components/Icons'
import { api, getToken, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import RequiereAplicar from '../components/RequiereAplicar'

export default function BackupRestore() {
  const { showToast, ToastContainer } = useToast()
  const [restoreBusy, setRestoreBusy] = useState(false)
  const restoreRef = useRef<HTMLInputElement>(null)

  const [analizando, setAnalizando] = useState(false)
  const [aplicando, setAplicando] = useState(false)
  const [informe, setInforme] = useState<any>(null)
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
      showToast(traducir("Backup descargado correctamente"), 'success')
    }).catch(() => showToast(traducir("Error al descargar backup"), 'error'))
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
      showToast(traducir("squid.conf descargado"), 'success')
    }).catch(() => showToast(traducir("Error al descargar squid.conf"), 'error'))
  }

  const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setRestoreBusy(true)
    try {
      const result = await api.restoreBackup(file)
      notificarCambioPendiente()
      showToast(`Backup restaurado: ${result.details.acls} ACLs, ${result.details.rules} reglas, ${result.details.users} usuarios`, 'success')
    } catch (err: any) {
      showToast(err.message, 'error')
    } finally {
      setRestoreBusy(false)
      if (restoreRef.current) restoreRef.current.value = ''
    }
  }

  const [archivosPendientes, setArchivosPendientes] = useState<File[]>([])

  // El archivo "principal" es el squid.conf en sí: el punto de entrada desde
  // el que se resuelven los `include`. Con un solo archivo no hace falta
  // preguntar; con varios, se asume por convención el que se llama
  // "squid.conf" si está, o el primero si no.
  const elegirPrincipal = (files: File[]): string => {
    const porNombre = files.find(f => f.name.toLowerCase() === 'squid.conf')
    return (porNombre ?? files[0]).name
  }

  const handleSeleccionArchivos = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    setArchivosPendientes(files)
    setInforme(null)
    setAnalizando(true)
    try {
      const principal = elegirPrincipal(files)
      const resultado = await api.analyzeSquidConf(files, principal)
      setInforme(resultado)
    } catch (err: any) {
      showToast(err.message, 'error')
      setArchivosPendientes([])
    } finally {
      setAnalizando(false)
      if (importRef.current) importRef.current.value = ''
    }
  }

  const handleAplicarImport = async () => {
    if (!informe?.token) return
    setAplicando(true)
    try {
      const result = await api.applySquidImport(informe.token)
      notificarCambioPendiente()
      showToast(`Importado: ${result.details.acls} ACLs, ${result.details.reglas} reglas, ${result.details.settings} settings`, 'success')
      if (result.details.avisos?.length > 0) {
        setTimeout(() => showToast(result.details.avisos[0], 'warning'), 3000)
      }
      setInforme(null)
      setArchivosPendientes([])
    } catch (err: any) {
      showToast(err.message, 'error')
    } finally {
      setAplicando(false)
    }
  }

  const cancelarImport = () => {
    setInforme(null)
    setArchivosPendientes([])
  }

  return (
    <div className="p-6 md:p-7">
      <h1 className="text-2xl font-bold mb-6" style={{ color: '#0A2C48' }}>{traducir("Backup, Restore y Migración")}</h1>

      {/* Sección: Backup de la plataforma */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-2">{traducir("Backup de SquidManager")}</h3>
        <p className="text-sm text-ink-3 mb-4">{traducir("Exporta toda la configuración de SquidManager (ACLs, reglas, usuarios, settings, delay pools, LDAP) a un archivo JSON. Este backup solo sirve para restaurar dentro de SquidManager.")}</p>
        <div className="flex gap-3 flex-wrap">
          <button onClick={handleExport}
            className="px-4 py-2 text-white rounded-lg font-medium text-sm inline-flex items-center gap-1.5" style={{ backgroundColor: '#0B497C' }}>
            <IconDownload className="w-4 h-4" />{traducir("Descargar backup (JSON)")}</button>
          <div className="flex items-center gap-3">
            <input ref={restoreRef} type="file" accept=".json" onChange={handleRestore} className="hidden" id="restore-input" />
            <button onClick={() => restoreRef.current?.click()} disabled={restoreBusy}
              className="px-4 py-2 border border-line rounded-lg font-medium text-sm hover:bg-brand-50 disabled:opacity-50">
              {restoreBusy ? 'Restaurando…' : 'Restaurar backup'}
            </button>
            <RequiereAplicar />
          </div>
        </div>
      </div>

      {/* Sección: Exportar squid.conf */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-2">{traducir("Descargar squid.conf")}</h3>
        <p className="text-sm text-ink-3 mb-4">{traducir("Descarga el archivo squid.conf que SquidManager ha generado y que Squid está usando actualmente.")}</p>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-800 mb-4">
          <strong>{traducir("Uso en un Squid tradicional (sin plataforma):")}</strong>
          <ul className="mt-2 space-y-1 list-disc list-inside">
            <li>El archivo es válido para Squid estándar, pero ajusta las rutas (<code>/var/spool/squid</code>, <code>/var/log/squid</code>{traducir(") según tu distribución")}</li>
            <li>Los helpers de autenticación (<code>basic_ncsa_auth</code>, <code>basic_ldap_auth</code>{traducir(") deben existir en el servidor destino")}</li>
            <li>El archivo <code>squid_passwd</code>{traducir("(usuarios) debe copiarse aparte")}</li>
            <li>{traducir("Los certificados SSL de la CA deben copiarse aparte")}</li>
            <li>Si usas SSL Bump, necesitas instalar <code>security_file_certgen</code>{traducir("y la CA en los clientes")}</li>
          </ul>
        </div>
        <button onClick={handleDownloadConf}
          className="px-4 py-2 text-white rounded-lg font-medium text-sm inline-flex items-center gap-1.5" style={{ backgroundColor: '#48B3D0' }}>
          <IconFile className="w-4 h-4" />{traducir("Descargar squid.conf")}</button>
      </div>

      {/* Sección: Importar squid.conf tradicional */}
      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-2">{traducir("Importar squid.conf tradicional")}</h3>
        <p className="text-sm text-ink-3 mb-4">{traducir("Si tienes un Squid configurado a mano y quieres migrar a SquidManager, sube tu squid.conf (y los archivos que incluya con «include», si los usa) para ver primero un informe de qué se puede importar — nada se aplica todavía en este paso.")}</p>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-800 mb-4">
          <strong>{traducir("Qué se importa y qué no:")}</strong>
          <ul className="mt-2 space-y-1 list-disc list-inside">
            <li>{traducir("ACLs autocontenidas (src, dstdomain, url_regex, time, port...) y las reglas http_access que solo las usan a ellas")}</li>
            <li>{traducir("Delay pools con el formato estándar, y un proxy padre (cache_peer) simple — se importa DESACTIVADO, para probarlo antes de activarlo")}</li>
            <li>Los usuarios (htpasswd) <strong>NO</strong>{traducir("se importan — créalos manualmente")}</li>
            <li>{traducir("NTLM/AD, grupos externos, squidGuard y otras directivas sin equivalente en el panel se listan en el informe, no se importan en silencio")}</li>
          </ul>
        </div>
        {!informe ? (
          <div className="flex items-center gap-3">
            <input ref={importRef} type="file" accept=".conf,text/plain" multiple onChange={handleSeleccionArchivos} className="hidden" id="import-input" />
            <button onClick={() => importRef.current?.click()} disabled={analizando}
              className="px-4 py-2 text-white rounded-lg font-medium text-sm disabled:opacity-50" style={{ backgroundColor: '#0B497C' }}>
              {analizando ? 'Analizando…' : 'Elegir archivo(s) y analizar'}
            </button>
          </div>
        ) : (
          <InformeImport
            informe={informe}
            archivos={archivosPendientes}
            aplicando={aplicando}
            onAplicar={handleAplicarImport}
            onCancelar={cancelarImport}
          />
        )}
      </div>

      <ToastContainer />
    </div>
  )
}

function InformeImport({ informe, archivos, aplicando, onAplicar, onCancelar }: {
  informe: any
  archivos: File[]
  aplicando: boolean
  onAplicar: () => void
  onCancelar: () => void
}) {
  const r = informe.resumen
  const nadaImportable = r.acls_a_importar === 0 && r.reglas_a_importar === 0 &&
    r.settings_a_importar === 0 && r.delay_pools_a_importar === 0 && !r.parent_proxy

  return (
    <div>
      <p className="text-xs text-ink-3 mb-3">
        {traducir("Archivos analizados")}: {archivos.map(f => f.name).join(', ')}
      </p>

      {informe.includes_faltantes?.length > 0 && (
        <div className="bg-danger-soft text-danger text-[13px] p-3 rounded-lg mb-3">
          <strong>{traducir("Archivos incluidos que no se subieron (su contenido no se analizó):")}</strong>{' '}
          {informe.includes_faltantes.join(', ')}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <ResumenCasillero label={traducir("ACLs a importar")} valor={r.acls_a_importar} tono="success" />
        <ResumenCasillero label={traducir("Reglas a importar")} valor={r.reglas_a_importar} tono="success" />
        <ResumenCasillero label={traducir("No soportadas")} valor={r.directivas_no_soportadas} tono="warning" />
        <ResumenCasillero label={traducir("No reconocidas")} valor={r.directivas_desconocidas} tono="warning" />
      </div>

      {r.parent_proxy && (
        <div className={`text-[13px] p-2.5 rounded-lg mb-3 ${r.parent_proxy === 'importar' ? 'bg-success-soft text-success' : 'bg-amber-50 text-amber-800'}`}>
          {traducir("Proxy padre detectado")}: {informe.parent_proxy?.host}:{informe.parent_proxy?.port}
          {r.parent_proxy === 'importar'
            ? ` — ${traducir('se importará DESACTIVADO, pruébalo antes de activarlo')}`
            : ` — ${traducir('no se importa')}: ${informe.parent_proxy?.motivo}`}
        </div>
      )}

      {(r.acls_ignoradas > 0 || r.reglas_ignoradas > 0) && (
        <details className="mb-3 text-xs">
          <summary className="cursor-pointer text-ink-3">{traducir("Ver ACLs y reglas ignoradas")} ({r.acls_ignoradas + r.reglas_ignoradas})</summary>
          <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
            {informe.acls.filter((a: any) => a.estado !== 'importar').map((a: any, i: number) => (
              <div key={`a${i}`} className="font-mono">{a.name} ({a.type}): <span className="text-ink-3">{a.motivo}</span></div>
            ))}
            {informe.reglas.filter((rr: any) => rr.estado !== 'importar').map((rr: any, i: number) => (
              <div key={`r${i}`} className="font-mono">{rr.action} {rr.acl_names}: <span className="text-ink-3">{rr.motivo}</span></div>
            ))}
          </div>
        </details>
      )}

      {(informe.no_soportadas.length > 0 || informe.desconocidas.length > 0) && (
        <details className="mb-4 text-xs" open>
          <summary className="cursor-pointer text-ink-3 font-medium">{traducir("Directivas no importadas")} ({informe.no_soportadas.length + informe.desconocidas.length})</summary>
          <div className="mt-2 space-y-1 max-h-64 overflow-y-auto">
            {informe.no_soportadas.map((h: any, i: number) => (
              <div key={`ns${i}`} className="font-mono">
                <span className="text-amber-700">{h.directiva}</span> ({h.archivo}:{h.linea}): <span className="text-ink-3">{h.motivo}</span>
              </div>
            ))}
            {informe.desconocidas.map((h: any, i: number) => (
              <div key={`dc${i}`} className="font-mono">
                <span className="text-ink-3">{h.directiva}</span> ({h.archivo}:{h.linea}): {traducir("no reconocida")}
              </div>
            ))}
          </div>
        </details>
      )}

      {nadaImportable && (
        <p className="text-sm text-ink-3 mb-3">{traducir("No hay nada importable en estos archivos.")}</p>
      )}

      <div className="flex items-center gap-3">
        <button onClick={onAplicar} disabled={aplicando || nadaImportable}
          className="px-4 py-2 text-white rounded-lg font-medium text-sm disabled:opacity-50" style={{ backgroundColor: '#0B497C' }}>
          {aplicando ? 'Aplicando…' : 'Confirmar e importar'}
        </button>
        <button onClick={onCancelar} disabled={aplicando}
          className="px-4 py-2 border border-line rounded-lg font-medium text-sm hover:bg-brand-50 disabled:opacity-50">
          {traducir("Cancelar")}
        </button>
        <RequiereAplicar />
      </div>
    </div>
  )
}

function ResumenCasillero({ label, valor, tono }: { label: string; valor: number; tono: 'success' | 'warning' }) {
  return (
    <div className={`rounded-lg p-3 text-center ${tono === 'success' ? 'bg-success-soft text-success' : 'bg-amber-50 text-amber-800'}`}>
      <div className="text-xl font-bold">{valor}</div>
      <div className="text-[11px]">{label}</div>
    </div>
  )
}