const API_BASE = '/api'

export function getToken(): string | null {
  return localStorage.getItem('token')
}

export function setToken(token: string) {
  localStorage.setItem('token', token)
}

export function clearToken() {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
  localStorage.removeItem('mustChangePassword')
}

/** Rol del administrador conectado: superadmin, admin o viewer. */
export function getRole(): string {
  return localStorage.getItem('role') || 'admin'
}

/** Un viewer solo consulta: la API rechaza cualquier escritura suya con 403. */
export function canWrite(): boolean {
  return getRole() !== 'viewer'
}

export function isSuperadmin(): boolean {
  return getRole() === 'superadmin'
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> || {}),
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    throw new Error('La sesión ha caducado. Vuelve a iniciar sesión.')
  }

  if (res.status === 403) {
    const error = await res.json().catch(() => ({ detail: null }))
    throw new Error(error.detail || 'Tu cuenta no tiene permiso para esta acción')
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `Error ${res.status}`)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  // Función genérica para requests GET con query params
  request: <T = any>(path: string) => request<T>(path),

  // Auth
  login: (username: string, password: string) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    return fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    }).then(async r => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: null }))
        throw new Error(err.detail || 'Credenciales inválidas')
      }
      return r.json()
    })
  },

  // Proxy Users
  listUsers: () => request<any[]>('/proxy-users/'),
  createUser: (data: any) => request<any>('/proxy-users/', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id: number, data: any) => request<any>(`/proxy-users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteUser: (id: number) => request<void>(`/proxy-users/${id}`, { method: 'DELETE' }),
  toggleUser: (id: number) => request<any>(`/proxy-users/${id}/toggle`, { method: 'PATCH' }),

  // ACLs
  listAcls: () => request<any[]>('/acls/'),
  createAcl: (data: any) => request<any>('/acls/', { method: 'POST', body: JSON.stringify(data) }),
  updateAcl: (id: number, data: any) => request<any>(`/acls/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAcl: (id: number) => request<void>(`/acls/${id}`, { method: 'DELETE' }),

  // Access Rules
  listAccessRules: () => request<any[]>('/access-rules/'),
  createAccessRule: (data: any) => request<any>('/access-rules/', { method: 'POST', body: JSON.stringify(data) }),
  updateAccessRule: (id: number, data: any) => request<any>(`/access-rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAccessRule: (id: number) => request<void>(`/access-rules/${id}`, { method: 'DELETE' }),
  reorderRules: (ruleIds: number[]) => request<any[]>('/access-rules/reorder', { method: 'PUT', body: JSON.stringify({ rule_ids: ruleIds }) }),

  // Squid Config
  getSquidStatus: () => request<any>('/squid/status'),
  previewConfig: () => request<any>('/squid/preview'),
  applyConfig: () => request<any>('/squid/apply', { method: 'POST' }),
  getSettings: () => request<any>('/squid/settings'),
  updateSetting: (key: string, value: string, category: string, description: string) =>
    request<any>('/squid/settings', { method: 'PUT', body: JSON.stringify({ key, value, category, description }) }),

  // LDAP
  getLdapConfig: () => request<any>('/ldap/config'),
  updateLdapConfig: (data: any) => request<any>('/ldap/config', { method: 'PUT', body: JSON.stringify(data) }),
  testLdap: (data: any) => request<any>('/ldap/test', { method: 'POST', body: JSON.stringify(data) }),
  syncLdapUsers: () => request<any>('/ldap/sync', { method: 'POST' }),
  listLdapUsers: () => request<any[]>('/ldap/users'),
  toggleLdapUser: (id: number) => request<any>(`/ldap/users/${id}/toggle`, { method: 'PATCH' }),

  // Grupos de usuarios
  listGroups: () => request<any[]>('/groups/'),
  createGroup: (data: any) => request<any>('/groups/', { method: 'POST', body: JSON.stringify(data) }),
  updateGroup: (id: number, data: any) => request<any>(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteGroup: (id: number) => request<void>(`/groups/${id}`, { method: 'DELETE' }),
  addGroupMember: (id: number, username: string) => request<any>(`/groups/${id}/members`, { method: 'POST', body: JSON.stringify({ username }) }),
  removeGroupMember: (id: number, username: string) => request<any>(`/groups/${id}/members/${username}`, { method: 'DELETE' }),

  // Delay Pools
  listDelayPools: () => request<any[]>('/delay-pools/'),
  createDelayPool: (data: any) => request<any>('/delay-pools/', { method: 'POST', body: JSON.stringify(data) }),
  updateDelayPool: (id: number, data: any) => request<any>(`/delay-pools/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteDelayPool: (id: number) => request<void>(`/delay-pools/${id}`, { method: 'DELETE' }),

  // Audit
  listAudit: (limit = 100, offset = 0) => request<any>(`/audit/?limit=${limit}&offset=${offset}`),
  auditStats: () => request<any>('/audit/stats'),

  // Metrics
  getDashboard: () => request<any>('/metrics/dashboard'),
  getTraffic: (seconds = 60) => request<any>(`/metrics/traffic?seconds=${seconds}`),
  getTimeline: (seconds = 60, interval = 5) => request<any>(`/metrics/timeline?seconds=${seconds}&interval=${interval}`),
  getConnections: (limit = 20) => request<any>(`/metrics/connections?limit=${limit}`),

  // Admins
  listAdmins: () => request<any>('/admins/'),
  createAdmin: (data: any) => request<any>('/admins/', { method: 'POST', body: JSON.stringify(data) }),
  updateAdmin: (id: number, data: any) => request<any>(`/admins/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAdmin: (id: number) => request<any>(`/admins/${id}`, { method: 'DELETE' }),
  changePassword: (current: string, newPass: string) => request<any>('/admins/change-password', { method: 'PUT', body: JSON.stringify({ current_password: current, new_password: newPass }) }),

  // Backup
  exportBackup: () => `${API_BASE}/backup/export`,
  restoreBackup: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<any>('/backup/restore', { method: 'POST', body: formData })
  },
  downloadSquidConf: () => `${API_BASE}/backup/squid-conf`,
  importSquidConf: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<any>('/backup/import-squid-conf', { method: 'POST', body: formData })
  },

  // Logs
  getLogs: (params: { limit?: number; offset?: number; user?: string; status?: number; domain?: string; ip?: string; denied?: boolean } = {}) => {
    const qs = new URLSearchParams()
    if (params.limit) qs.append('limit', String(params.limit))
    if (params.offset) qs.append('offset', String(params.offset))
    if (params.user) qs.append('user', params.user)
    if (params.status) qs.append('status', String(params.status))
    if (params.domain) qs.append('domain', params.domain)
    if (params.ip) qs.append('ip', params.ip)
    if (params.denied) qs.append('denied', 'true')
    const q = qs.toString()
    return request<any>(`/logs/access${q ? '?' + q : ''}`)
  },
  getLogStats: () => request<any>('/logs/stats'),
  exportLogsCsv: (params: { user?: string; status?: number; domain?: string; ip?: string; denied?: boolean } = {}) => {
    const qs = new URLSearchParams()
    if (params.user) qs.append('user', params.user)
    if (params.status) qs.append('status', String(params.status))
    if (params.domain) qs.append('domain', params.domain)
    if (params.ip) qs.append('ip', params.ip)
    if (params.denied) qs.append('denied', 'true')
    const q = qs.toString()
    return `${API_BASE}/logs/export${q ? '?' + q : ''}`
  },

  // Notifications
  getNotificationConfig: () => request<any>('/notifications/config'),
  updateNotificationConfig: (data: any) => request<any>('/notifications/config', { method: 'PUT', body: JSON.stringify(data) }),
  testEmail: (data: any) => request<any>('/notifications/test-email', { method: 'POST', body: JSON.stringify(data) }),
  testTelegram: (data: any) => request<any>('/notifications/test-telegram', { method: 'POST', body: JSON.stringify(data) }),

  // Session management
  purgeCredentials: () => request<any>('/proxy-users/purge-credentials', { method: 'POST' }),
  resetPassword: (id: number) => request<any>(`/proxy-users/${id}/reset-password`, { method: 'POST' }),
  getPending: () => request<{ dirty: boolean }>('/squid/pending'),
}