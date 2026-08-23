import { useState, useEffect } from 'react'
import { IconCheck, IconClose } from '../components/Icons'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

export default function LdapConfig() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResults, setTestResults] = useState<any[]>([])
  const [testUser, setTestUser] = useState({ username: '', password: '' })
  const [ldapUsers, setLdapUsers] = useState<any[]>([])
  const [syncing, setSyncing] = useState(false)
  const { showToast, ToastContainer } = useToast()

  useEffect(() => {
    api.getLdapConfig().then(setConfig).catch(e => showToast('Error al cargar config LDAP', 'error')).finally(() => setLoading(false))
    api.listLdapUsers().then(setLdapUsers).catch(() => {})
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    try {
      const result = await api.syncLdapUsers()
      showToast(`Sincronizados ${result.synced} usuarios del directorio`, 'success')
      api.listLdapUsers().then(setLdapUsers).catch(() => {})
    } catch (e: any) {
      showToast(`Error al sincronizar: ${e.message}`, 'error')
    } finally {
      setSyncing(false)
    }
  }

  const handleToggleLdapUser = async (id: number) => {
    try {
      const result = await api.toggleLdapUser(id)
      api.listLdapUsers().then(setLdapUsers).catch(() => {})
      showToast(`Usuario "${result.username}" ${result.enabled ? 'habilitado' : 'deshabilitado'}`)
    } catch (e: any) { showToast(`Error: ${e.message}`, 'error') }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateLdapConfig(config)
      showToast('Configuración LDAP guardada correctamente')
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
        showToast('Test LDAP exitoso', 'success')
      } else {
        showToast('Test LDAP falló', 'warning')
      }
    } catch (e: any) {
      showToast(`Error en test: ${e.message}`, 'error')
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className="p-8 text-center text-ink-3">Cargando...</div>
  if (!config) return <div className="p-8 text-center text-ink-3">No se pudo cargar la configuración</div>

  return (
    <div className="p-6 md:p-7">
      <ToastContainer />
      <h1 className="page-title mb-2">LDAP / Active Directory</h1>
      <p className="text-sm text-ink-3 mb-6">Configura la autenticación contra un directorio externo</p>

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
            <span className="text-sm text-ink-2">Habilitar</span>
          </label>
        </div>
      </div>

      {/* Configuración */}
      <div className="card p-6 mb-6">
        <h2 className="font-medium text-ink mb-4">Datos del servidor LDAP</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="field-label block mb-1.5">URL del servidor</label>
            <input type="text" value={config.server_url} onChange={e => setConfig({ ...config, server_url: e.target.value })}
              placeholder="ldap://servidor.domain.com:389" className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">Bind DN</label>
            <input type="text" value={config.bind_dn} onChange={e => setConfig({ ...config, bind_dn: e.target.value })}
              placeholder="cn=admin,dc=domain,dc=com" className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">Contraseña Bind</label>
            <input type="password" value={config.bind_password === '***' ? '' : config.bind_password}
              onChange={e => setConfig({ ...config, bind_password: e.target.value })}
              placeholder={config.bind_password === '***' ? '•••••••• (guardada)' : 'Contraseña'}
              className="input" />
          </div>
          <div>
            <label className="field-label block mb-1.5">Search Base</label>
            <input type="text" value={config.search_base} onChange={e => setConfig({ ...config, search_base: e.target.value })}
              placeholder="ou=users,dc=domain,dc=com" className="input font-mono text-sm" />
          </div>
          <div>
            <label className="field-label block mb-1.5">Filtro de usuario</label>
            <input type="text" value={config.user_filter} onChange={e => setConfig({ ...config, user_filter: e.target.value })}
              placeholder="(uid=%s)" className="input font-mono text-sm" />
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
        <h2 className="font-medium text-ink mb-4">Probar conexión LDAP</h2>
        <p className="text-sm text-ink-3 mb-4">Introduce un usuario LDAP y su contraseña para verificar que la autenticación funciona</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="field-label block mb-1.5">Usuario de prueba</label>
            <input type="text" value={testUser.username} onChange={e => setTestUser({ ...testUser, username: e.target.value })}
              placeholder="usuario.ldap" className="input" />
          </div>
          <div>
            <label className="field-label block mb-1.5">Contraseña de prueba</label>
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
            <h3 className="font-medium text-ink">Resultados:</h3>
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

      {/* Gestión de usuarios LDAP */}
      <div className="card p-6 mt-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-medium text-ink">Usuarios LDAP (allow-list)</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 text-xs font-medium">
                {ldapUsers.length} sincronizados
              </span>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${ldapUsers.filter(u => u.enabled).length > 0 ? 'bg-green-50 text-ok' : 'bg-line-soft text-ink-3'}`}>
                {ldapUsers.filter(u => u.enabled).length} habilitados
              </span>
            </div>
          </div>
          <button
            onClick={handleSync}
            disabled={syncing || !config.enabled}
            className="btn btn-primary disabled:opacity-50"
          >
            {syncing ? 'Sincronizando…' : 'Sincronizar con AD'}
          </button>
        </div>

        {/* Aviso de allow-list estricto */}
        <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
          <p className="font-medium">Modo allow-list estricto</p>
          <p className="mt-1">
            Al sincronizar, los usuarios quedan <strong>deshabilitados</strong> y no pueden navegar.
            Pulsa <strong>«Habilitar»</strong> en cada usuario que quieras autorizar.
            Los usuarios no habilitados serán rechazados (se les pedirá credenciales sin éxito).
          </p>
        </div>

        {ldapUsers.length === 0 ? (
          <div className="text-center py-8 text-ink-3 text-sm">
            No hay usuarios sincronizados. Pulsa "Sincronizar con AD" para importarlos del directorio.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-panel">
              <thead>
                <tr>
                  <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Usuario</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Nombre</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-ink-3 uppercase">Email</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-ink-3 uppercase">Navegación</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {ldapUsers.map(u => (
                  <tr key={u.id} className="hover:bg-brand-50">
                    <td className="px-4 py-2.5 font-medium text-ink">{u.username}</td>
                    <td className="px-4 py-2.5 text-sm text-ink-2">{u.display_name || '—'}</td>
                    <td className="px-4 py-2.5 text-sm text-ink-2">{u.email || '—'}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button onClick={() => handleToggleLdapUser(u.id)}
                        className={`text-sm font-medium ${u.enabled ? 'text-danger hover:text-danger' : 'text-ok hover:text-green-800'}`}
                        title={u.enabled ? 'Bloquear navegación' : 'Permitir navegación'}>
                        {u.enabled ? 'Bloquear' : 'Habilitar'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}