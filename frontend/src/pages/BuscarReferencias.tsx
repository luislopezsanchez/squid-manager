import { traducir } from '../i18n'
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { IconSearch, IconUsers, IconTag, IconRules, IconGauge } from '../components/Icons'
import { LoadingState } from '../components/AsyncState'

interface Resultado {
  acls: { id: number; name: string; type: string; description: string | null; is_category: boolean; source: string }[]
  rules: { id: number; action: string; acl_names: string; order: number; description: string | null; enabled: boolean }[]
  groups: { id: number; name: string; description: string | null; source: string; matched_member: string | null }[]
  delay_pools: { id: number; description: string | null; acl_name: string | null; pool_class: number }[]
}

const VACIO: Resultado = { acls: [], rules: [], groups: [], delay_pools: [] }

export default function BuscarReferencias() {
  const [q, setQ] = useState('')
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [loading, setLoading] = useState(false)
  const [buscado, setBuscado] = useState(false)

  // Debounce de 300ms: sin esto, cada letra tecleada dispara su propio
  // pedido -innecesario, y con conexiones lentas las respuestas podían
  // llegar desordenadas (la de "faceboo" después de la de "facebook").
  useEffect(() => {
    const termino = q.trim()
    if (!termino) { setResultado(null); setBuscado(false); return }
    setLoading(true)
    const t = setTimeout(() => {
      api.searchReferences(termino)
        .then(setResultado)
        .catch(() => setResultado(VACIO))
        .finally(() => { setLoading(false); setBuscado(true) })
    }, 300)
    return () => clearTimeout(t)
  }, [q])

  const totalResultados = resultado
    ? resultado.acls.length + resultado.rules.length + resultado.groups.length + resultado.delay_pools.length
    : 0

  return (
    <div className="p-6 md:p-7">
      <div className="mb-6">
        <h1 className="page-title">{traducir("Buscar referencias")}</h1>
        <p className="page-sub">{traducir("Encontrá dónde se usa un usuario, un dominio, una IP o el nombre de una ACL: en qué reglas, grupos, categorías y límites de ancho de banda aparece.")}</p>
      </div>

      <input
        type="text"
        value={q}
        onChange={e => setQ(e.target.value)}
        placeholder={traducir("ej: jgarcia, facebook, 192.168.1.50…")}
        className="input w-full max-w-lg"
        autoFocus
      />

      {loading && <div className="mt-6"><LoadingState /></div>}

      {!loading && buscado && totalResultados === 0 && (
        <p className="mt-6 text-ink-3">{traducir("Sin resultados para «{q}».", { q })}</p>
      )}

      {!loading && resultado && totalResultados > 0 && (
        <div className="mt-6 space-y-6">
          {resultado.acls.length > 0 && (
            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-2 mb-2">
                <IconTag className="w-4 h-4" />{traducir("ACLs y categorías")} ({resultado.acls.length})
              </h3>
              <div className="card divide-y divide-line-soft">
                {resultado.acls.map(a => (
                  <Link key={a.id} to={a.is_category ? '/categorias' : '/acls'}
                    className="flex items-center justify-between px-4 py-3 hover:bg-brand-50 text-sm">
                    <span className="font-mono text-ink">{a.name}</span>
                    <span className="text-ink-3">{a.is_category ? traducir('Categoría') : a.type}{a.description ? ` · ${a.description}` : ''}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {resultado.rules.length > 0 && (
            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-2 mb-2">
                <IconRules className="w-4 h-4" />{traducir("Reglas de acceso")} ({resultado.rules.length})
              </h3>
              <div className="card divide-y divide-line-soft">
                {resultado.rules.map(r => (
                  <Link key={r.id} to="/rules" className="flex items-center justify-between px-4 py-3 hover:bg-brand-50 text-sm">
                    <span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-bold mr-2 ${r.action === 'allow' ? 'pill-ok' : 'pill-danger'}`}>{r.action}</span>
                      <span className="font-mono text-ink">{r.acl_names}</span>
                    </span>
                    <span className="text-ink-3 text-xs">#{r.order}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {resultado.groups.length > 0 && (
            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-2 mb-2">
                <IconUsers className="w-4 h-4" />{traducir("Grupos")} ({resultado.groups.length})
              </h3>
              <div className="card divide-y divide-line-soft">
                {resultado.groups.map(g => (
                  <Link key={g.id} to="/groups" className="flex items-center justify-between px-4 py-3 hover:bg-brand-50 text-sm">
                    <span className="font-mono text-ink">{g.name}</span>
                    <span className="text-ink-3">
                      {g.matched_member ? traducir('Miembro: {u}', { u: g.matched_member }) : (g.description || '')}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {resultado.delay_pools.length > 0 && (
            <div>
              <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-2 mb-2">
                <IconGauge className="w-4 h-4" />{traducir("Ancho de banda")} ({resultado.delay_pools.length})
              </h3>
              <div className="card divide-y divide-line-soft">
                {resultado.delay_pools.map(p => (
                  <Link key={p.id} to="/delay-pools" className="flex items-center justify-between px-4 py-3 hover:bg-brand-50 text-sm">
                    <span className="text-ink">{p.description || traducir('(sin nombre)')}</span>
                    <span className="text-ink-3 font-mono text-xs">{p.acl_name || traducir('Todo el tráfico')}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!buscado && !loading && (
        <div className="mt-10 text-center text-ink-3">
          <IconSearch className="w-8 h-8 mx-auto mb-2 opacity-40" />
          {traducir("Escribí arriba para empezar a buscar.")}
        </div>
      )}
    </div>
  )
}
