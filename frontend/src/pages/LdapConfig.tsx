import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { IconCheck, IconClose } from '../components/Icons'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

/**
 * Valores de partida por tipo de directorio. Son un punto de partida, no una
 * restricción: los campos quedan como texto libre, así que un esquema
 * personalizado (p. ej. otro atributo de login) se puede escribir a mano.
 */
const DIRECTORY_PRESETS: Record<string, { user_filter: string; sync_filter: string }> = {
  ad: {
    user_filter: '(sAMAccountName=%s)',
    sync_filter: '(&(objectCategory=person)(objectClass=user))',
  },
  openldap: {
    user_filter: '(uid=%s)',
    sync_filter: '(objectClass=posixAccount)',
  },
  inetorg: {
    user_filter: '(uid=%s)',
    sync_filter: '(objectClass=inetOrgPerson)',
  },
}

export default function LdapConfig() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResults, setTestResults] = useState<any[]>([])
  const [testUser, setTestUser] = useState({ username: '', password: '' })
  const [ldapUserCount, setLdapUserCount] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    api.getLdapConfig().then(setConfig).catch(e => showToast(traducir("Error al cargar config LDAP"), 'error')).finally(() => setLoading(false))
    api.listLdapUsers().then(u => setLdapUserCount(u.length)).catch(() => {})
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    try {
      const result = await api.syncLdapUsers()
      showToast(`Sincronizados ${result.synced} usuarios del directorio. Gestiónalos en Usuarios.`, 'success')
      api.listLdapUsers().then(u => setLdapUserCount(u.length)).catch(() => {})
    } catch (e: any) {
      showToast(`Error al sincronizar: ${e.message}`, 'error')
    } finally {
      setSyncing(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateLdapConfig(config)
      showToast(traducir("Configuración LDAP guardada correctamente"))
    } catch (e: any) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResults([])
    try {
      const result = await api.testLdap({
        ...config,
        username: testUser.username,
        password: testUser.password,
      })
      setTestResults(result.results || [])
      if (result.success) {
        showToast(traducir("Test LDAP exitoso"), 'success')
      } else {
        showToast(traducir("Test LDAP falló"), 'warning')
      }
    } catch (e: any) {
      showToast(`Error en test: ${e.message}`, 'error')
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-ink-3">{traducir("Cargando...")}</div>
  if (!config) return <div className="p-8 text-center text-ink-3">{traducir("No se pudo cargar la configuración")}</div>

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">{traducir("LDAP / Active Directory")}</h1>
      <p className="text-sm text-ink-3 mb-6">{traducir("Configura la autenticación contra un directorio externo")}</p>

      {/* Estado */}
      <div className={`rounded-xl p-4 mb-6 border ${config.enabled ? 'bg-green-50 border-green-200' : 'bg-brand-50 border-line'}`}>
        <div className="flex items-center gap-3">
          <span className={`inline-flex h-3 w-3 rounded-full ${config.enabled ? 'bg-ok' : 'bg-ink-3'}`} />
          <span className="font-medium text-ink">
            {config.enabled ? 'LDAP activado' : 'LDAP desactivado'}
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
        <h2 className="font-medium text-ink mb-1">{traducir("Datos del servidor LDAP")}</h2>
        <p className="text-sm text-ink-3 mb-4">{traducir("Esta configuración sirve para cualquier directorio LDAPv3 (Active Directory, OpenLDAP, FreeIPA…), no solo Active Directory — lo único que cambia entre uno y otro son los filtros de búsqueda de abajo.")}</p>

        {/* Preset: solo rellena los filtros con un valor de partida conocido
            para el tipo de directorio elegido — no se guarda como tal, y los
            campos se pueden seguir editando a mano después. */}
        <div className="mb-4">
          <label className="field-label block mb-1.5">{traducir("Tipo de directorio")}</label>
          <select
            className="input md:w-80"
            defaultValue=""
            onChange={e => {
              const preset = DIRECTORY_PRESETS[e.target.value]
              if (preset) setConfig({ ...config, user_filter: preset.user_filter, sync_filter: preset.sync_filter })
            }}
          >
            <option value="">{traducir("Elegir para rellenar los filtros…")}</option>
            <option value="ad">{traducir("Active Directory")}</option>
            <option value="openldap">{traducir("OpenLDAP (posixAccount)")}</option>
            <option value="inetorg">{traducir("LDAP genérico (inetOrgPerson)")}</option>
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="field-label block mb-1.5">{traducir("URL del servidor")}</label>
            <input type="text" value={config.server_url} onChange={e => setConfig({ ...config, server_url: e.target.value })}
              placeholder={traducir("ldap://servidor.domain.com:389")} className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("Bind DN")}</label>
            <input type="text" value={config.bind_dn} onChange={e => setConfig({ ...config, bind_dn: e.target.value })}
              placeholder="cn=admin,dc=domain,dc=com" className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("Contraseña Bind")}</label>
            <input type="password" value={config.bind_password === '***' ? '' : config.bind_password}
              onChange={e => setConfig({ ...config, bind_password: e.target.value })}
              placeholder={config.bind_password === '***' ? '•••••••• (guardada)' : 'Contraseña'}
              className="input" />
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("Search Base")}</label>
            <input type="text" value={config.search_base} onChange={e => setConfig({ ...config, search_base: e.target.value })}
              placeholder="ou=users,dc=domain,dc=com" className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("Filtro de usuario (login)")}</label>
            <input type="text" value={config.user_filter} onChange={e => setConfig({ ...config, user_filter: e.target.value })}
              placeholder="(uid=%s)" className="input font-mono text-sm" />
            <p className="text-xs text-ink-3 mt-1">{traducir("Busca a UN usuario por su nombre al iniciar sesión.")}</p>
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("Filtro de sincronización")}</label>
            <input type="text" value={config.sync_filter} onChange={e => setConfig({ ...config, sync_filter: e.target.value })}
              placeholder="(objectClass=person)" className="input font-mono text-sm" />
            <p className="text-xs text-ink-3 mt-1">{traducir("Busca a TODOS los usuarios al pulsar \"Sincronizar con AD\". Antes estaba fijo a Active Directory: contra otro directorio no encontraba a nadie, sin avisar.")}</p>
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="mt-4 btn btn-primary disabled:opacity-50"
        >
          {saving ? 'Guardando...' : 'Guardar Configuración'}
        </button>
      </div>

      {/* Test de conexión */}
      <div className="card p-6">
        <h2 className="font-medium text-ink mb-4">{traducir("Probar conexión LDAP")}</h2>
        <p className="text-sm text-ink-3 mb-4">{traducir("Introduce un usuario LDAP y su contraseña para verificar que la autenticación funciona")}</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="field-label block mb-1.5">{traducir("Usuario de prueba")}</label>
            <input type="text" value={testUser.username} onChange={e => setTestUser({ ...testUser, username: e.target.value })}
              placeholder="usuario.ldap" className="input" />
          </div>
          <div>
            <label className="field-label block mb-1.5">{traducir("Contraseña de prueba")}</label>
            <input type="password" value={testUser.password} onChange={e => setTestUser({ ...testUser, password: e.target.value })}
              placeholder="••••••••" className="input" />
          </div>
        </div>
        <button
          onClick={handleTest}
          disabled={testing || !testUser.username || !testUser.password}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {testing ? 'Probando...' : 'Probar Conexión'}
        </button>

        {/* Resultados del test */}
        {testResults.length > 0 && (
          <div className="mt-6 space-y-2">
            <h3 className="font-medium text-ink">{traducir("Resultados:")}</h3>
            {testResults.map((r, i) => (
              <div key={i} className={`p-3 rounded-lg flex items-start gap-3 ${
                r.status === 'ok' ? 'bg-green-50 border border-green-100' : 'bg-red-50 border border-red-100'
              }`}>
                <span className={`stat-icon flex-none ${r.status === 'ok' ? 'stat-icon-ok' : 'stat-icon-danger'}`}>
                      {r.status === 'ok' ? <IconCheck /> : <IconClose />}
                    </span>
                <div>
                  <p className="font-medium text-ink text-sm">{r.step}</p>
                  <p className="text-sm text-ink-2">{r.detail}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Usuarios importados del directorio: la lista y el habilitar/deshabilitar
          viven en Usuarios, junto con los usuarios locales — antes estaban
          separados y esa tabla no aparecía ahí, así que era fácil no verla. */}
      <div className="card p-6 mt-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-medium text-ink">{traducir("Usuarios del directorio")}</h2>
            <p className="text-sm text-ink-3 mt-1">
              {ldapUserCount} sincronizados · gestionar quién puede navegar se hace en{' '}
              <button onClick={() => navigate('/users')} className="text-brand-700 font-medium hover:underline">{traducir("Usuarios")}</button>
            </p>
          </div>
          <button
            onClick={handleSync}
            disabled={syncing || !config.enabled}
            className="btn btn-primary disabled:opacity-50"
          >
            {syncing ? 'Sincronizando…' : 'Sincronizar con AD'}
          </button>
        </div>

        {/* Ya no es allow-list estricto: un usuario nuevo importado del
            directorio puede navegar de inmediato. Se deshabilita a mano a
            quien no deba tener acceso. */}
        <div className="mt-4 p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800">
          Al sincronizar, los usuarios nuevos quedan <strong>habilitados</strong>{traducir("para navegar de inmediato. Si alguien no debe tener acceso, deshabilítalo manualmente desde la sección Usuarios.")}</div>
      </div>
    </div>
  )
}