const API_BASE = '/api'

export function getToken(): string | null {
  return localStorage.getItem('token')
}

export function setToken(token: string) {
  localStorage.setItem('token', token)
}

export function clearToken() {
  localStorage.removeItem('token')
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
    throw new Error('No autorizado')
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
    }).then(r => {
      if (!r.ok) throw new Error('Credenciales inválidas')
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

  // Delay Pools
  listDelayPools: () => request<any[]>('/delay-pools/'),
  createDelayPool: (data: any) => request<any>('/delay-pools/', { method: 'POST', body: JSON.stringify(data) }),
  updateDelayPool: (id: number, data: any) => request<any>(`/delay-pools/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteDelayPool: (id: number) => request<void>(`/delay-pools/${id}`, { method: 'DELETE' }),

  // Audit
  listAudit: (limit = 100, offset = 0) => request<any>(`/audit/?limit=${limit}&offset=${offset}`),
  auditStats: () => request<any>('/audit/stats'),
}