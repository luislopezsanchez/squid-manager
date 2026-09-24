// build-lineage: 6b800719-eeeb-43f8-8e6e-92ffbbbb4455
import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import Login from './pages/Login'
import { LoadingState } from './components/AsyncState'
import Layout from './components/Layout'
import { getToken, isSuperadmin } from './api/client'

// Carga perezosa por ruta: antes las ~30 páginas del panel viajaban todas en
// el mismo archivo .js inicial (823 KB) sin importar cuál se fuera a mirar
// primero -Vite ya avisaba de esto en cada build ("chunks larger than
// 500 kB"). Con lazy(), cada página se descarga recién cuando se navega a
// ella, así que el primer arranque del panel (login -> dashboard) solo baja
// el código que hace falta para eso. Login se deja fuera a propósito: es la
// primera pantalla que ve cualquiera sin sesión, no tiene sentido demorarla
// con una carga aparte.
const ChangePassword = lazy(() => import('./pages/ChangePassword'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const ProxyUsers = lazy(() => import('./pages/ProxyUsers'))
const ACLs = lazy(() => import('./pages/ACLs'))
const Categorias = lazy(() => import('./pages/Categorias'))
const AccessRules = lazy(() => import('./pages/AccessRules'))
const Settings = lazy(() => import('./pages/Settings'))
const LdapConfig = lazy(() => import('./pages/LdapConfig'))
const Kerberos = lazy(() => import('./pages/Kerberos'))
const DelayPools = lazy(() => import('./pages/DelayPools'))
const AuditLog = lazy(() => import('./pages/AuditLog'))
const CertificadoCA = lazy(() => import('./pages/CertificadoCA'))
const BackupRestore = lazy(() => import('./pages/BackupRestore'))
const Admins = lazy(() => import('./pages/Admins'))
const LogsViewer = lazy(() => import('./pages/LogsViewer'))
const HistoricalLogs = lazy(() => import('./pages/HistoricalLogs'))
const Notifications = lazy(() => import('./pages/Notifications'))
const Smtp = lazy(() => import('./pages/Smtp'))
const SyslogConfig = lazy(() => import('./pages/SyslogConfig'))
const ParentProxy = lazy(() => import('./pages/ParentProxy'))
const Groups = lazy(() => import('./pages/Groups'))
const Asistente = lazy(() => import('./pages/Asistente'))
const Documentacion = lazy(() => import('./pages/Documentacion'))
const Contacto = lazy(() => import('./pages/Contacto'))
const Actualizaciones = lazy(() => import('./pages/Actualizaciones'))
const CacheStats = lazy(() => import('./pages/CacheStats'))
const ActividadRed = lazy(() => import('./pages/ActividadRed'))
const RendimientoErrores = lazy(() => import('./pages/RendimientoErrores'))
const Tendencias = lazy(() => import('./pages/Tendencias'))
const Panorama = lazy(() => import('./pages/Panorama'))
const PanelCentral = lazy(() => import('./pages/PanelCentral'))

function App() {
  const token = getToken()
  // Con el cambio de contraseña pendiente no se entra al panel: la única
  // pantalla accesible es la de definir una contraseña propia.
  const mustChangePassword = localStorage.getItem('mustChangePassword') === '1'

  if (token && mustChangePassword) {
    return (
      <BrowserRouter>
        <Suspense fallback={<LoadingState />}>
          <Routes>
            <Route path="/cambiar-contrasena" element={<ChangePassword />} />
            <Route path="*" element={<Navigate to="/cambiar-contrasena" />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingState />}>
        <Routes>
          <Route path="/login" element={token ? <Navigate to="/" /> : <Login />} />
          <Route path="/cambiar-contrasena" element={token ? <ChangePassword /> : <Navigate to="/login" />} />
          <Route path="/" element={token ? <Layout /> : <Navigate to="/login" />}>
            <Route index element={<Dashboard />} />
            <Route path="users" element={<ProxyUsers />} />
            <Route path="acls" element={<ACLs />} />
            <Route path="categorias" element={<Categorias />} />
            <Route path="rules" element={<AccessRules />} />
            <Route path="delay-pools" element={<DelayPools />} />
            <Route path="ldap" element={<LdapConfig />} />
            <Route path="kerberos" element={<Kerberos />} />
            <Route path="asistente" element={<Asistente />} />
            <Route path="documentacion" element={<Documentacion />} />
            <Route path="contacto" element={<Contacto />} />
            <Route path="settings" element={<Settings />} />
            <Route path="certificate" element={<CertificadoCA />} />
            <Route path="audit" element={<AuditLog />} />
            <Route path="backup" element={<BackupRestore />} />
            <Route path="logs" element={<LogsViewer />} />
            <Route path="logs-historico" element={<HistoricalLogs />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="smtp" element={<Smtp />} />
            <Route path="syslog" element={<SyslogConfig />} />
            <Route path="parent-proxy" element={<ParentProxy />} />
            <Route path="groups" element={<Groups />} />
            <Route path="admins" element={isSuperadmin() ? <Admins /> : <Navigate to="/" />} />
            <Route path="actualizaciones" element={<Actualizaciones />} />
            <Route path="reportes/cache" element={<CacheStats />} />
            <Route path="reportes/actividad" element={<ActividadRed />} />
            <Route path="reportes/rendimiento" element={<RendimientoErrores />} />
            <Route path="reportes/tendencias" element={<Tendencias />} />
            <Route path="reportes/panorama" element={<Panorama />} />
            <Route path="panel-central" element={<PanelCentral />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
