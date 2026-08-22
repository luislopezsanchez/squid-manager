import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useNavigate } from 'react-router-dom'

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.getSquidStatus().then(setStatus).catch(console.error).finally(() => setLoading(false))
  }, [])

  const cards = [
    { title: 'Estado del Proxy', value: loading ? '...' : status?.running ? 'Activo' : 'Detenido',
      sub: status?.state ? `Estado: ${status.state}` : 'Sin datos',
      color: loading ? 'gray' : status?.running ? 'green' : 'red' },
    { title: 'Puerto del Proxy', value: '3128', sub: 'HTTP Proxy', color: 'blue' },
    { title: 'Versión', value: '0.3.0', sub: 'SquidManager', color: 'purple' },
  ]

  const actions = [
    { icon: '👥', title: 'Gestionar Usuarios', desc: 'Crear, editar y eliminar usuarios del proxy', path: '/users' },
    { icon: '🏷️', title: 'Configurar ACLs', desc: 'Listas de control de acceso por dominio, IP, horario', path: '/acls' },
    { icon: '📋', title: 'Reglas de Acceso', desc: 'Permitir o denegar tráfico con reglas ordenadas', path: '/rules' },
    { icon: '🐌', title: 'Ancho de Banda', desc: 'Delay pools para limitar velocidad por usuario', path: '/delay-pools' },
    { icon: '🔗', title: 'LDAP / Active Directory', desc: 'Autenticación contra directorio externo', path: '/ldap' },
    { icon: '⚙️', title: 'Configuración', desc: 'Puertos, caché, logging y parámetros generales', path: '/settings' },
    { icon: '📝', title: 'Auditoría', desc: 'Log de todos los cambios realizados', path: '/audit' },
  ]

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {cards.map((card, i) => (
          <div key={i} className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500 mb-4">{card.title}</h3>
            <div className="flex items-center gap-3">
              <span className={`inline-flex h-3 w-3 rounded-full bg-${card.color}-400 ring-4 ring-${card.color}-100`} />
              <p className="text-2xl font-bold text-gray-900">{card.value}</p>
            </div>
            <p className="text-sm text-gray-500 mt-1">{card.sub}</p>
          </div>
        ))}
      </div>

      <h2 className="text-lg font-bold text-gray-900 mb-4">Gestión</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {actions.map((action, i) => (
          <button
            key={i}
            onClick={() => navigate(action.path)}
            className="bg-white rounded-xl shadow-sm p-5 border border-gray-100 hover:border-primary-300 hover:shadow-md transition text-left"
          >
            <div className="flex items-start gap-4">
              <span className="text-3xl">{action.icon}</span>
              <div>
                <p className="font-medium text-gray-900">{action.title}</p>
                <p className="text-sm text-gray-500">{action.desc}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}