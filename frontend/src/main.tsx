import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ProxyUsers from './pages/ProxyUsers'
import ACLs from './pages/ACLs'
import AccessRules from './pages/AccessRules'
import Settings from './pages/Settings'
import LdapConfig from './pages/LdapConfig'
import DelayPools from './pages/DelayPools'
import AuditLog from './pages/AuditLog'
import CertificadoCA from './pages/CertificadoCA'
import BackupRestore from './pages/BackupRestore'
import Admins from './pages/Admins'
import LogsViewer from './pages/LogsViewer'
import Notifications from './pages/Notifications'
import SyslogConfig from './pages/SyslogConfig'
import Groups from './pages/Groups'
import ChangePassword from './pages/ChangePassword'
import Layout from './components/Layout'
import { getToken, isSuperadmin } from './api/client'

function App() {
  const token = getToken()
  // Con el cambio de contraseña pendiente no se entra al panel: la única
  // pantalla accesible es la de definir una contraseña propia.
  const mustChangePassword = localStorage.getItem('mustChangePassword') === '1'

  if (token && mustChangePassword) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/cambiar-contrasena" element={<ChangePassword />} />
          <Route path="*" element={<Navigate to="/cambiar-contrasena" />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/" /> : <Login />} />
        <Route path="/cambiar-contrasena" element={token ? <ChangePassword /> : <Navigate to="/login" />} />
        <Route path="/" element={token ? <Layout /> : <Navigate to="/login" />}>
          <Route index element={<Dashboard />} />
          <Route path="users" element={<ProxyUsers />} />
          <Route path="acls" element={<ACLs />} />
          <Route path="rules" element={<AccessRules />} />
          <Route path="delay-pools" element={<DelayPools />} />
          <Route path="ldap" element={<LdapConfig />} />
          <Route path="settings" element={<Settings />} />
          <Route path="certificate" element={<CertificadoCA />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="backup" element={<BackupRestore />} />
          <Route path="logs" element={<LogsViewer />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="syslog" element={<SyslogConfig />} />
          <Route path="groups" element={<Groups />} />
          <Route path="admins" element={isSuperadmin() ? <Admins /> : <Navigate to="/" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)