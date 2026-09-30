import { Link } from 'react-router-dom'
import { traducir } from '../i18n'
import { isSuperadmin } from '../api/client'
import { useModulos, type ModuloClave } from '../utils/modules'
import { LoadingState } from './AsyncState'
import { IconLock } from './Icons'

/** Envuelve una página de un módulo opcional: si el módulo está apagado en
 * Sistema → Módulos, en vez de la página se explica cómo activarlo. */
export default function ModuloRequerido({ modulo, nombre, children }: { modulo: ModuloClave; nombre: string; children: React.ReactNode }) {
  const { modulos, cargado } = useModulos()
  if (!cargado) return <LoadingState />
  if (modulos[modulo]) return <>{children}</>
  return (
    <div className="p-6 md:p-8">
      <div className="card p-10 max-w-xl mx-auto text-center">
        <span className="stat-icon mx-auto mb-4"><IconLock /></span>
        <h1 className="text-xl font-bold text-ink mb-2">{traducir("Módulo desactivado")}</h1>
        <p className="text-sm text-ink-2 mb-5">
          {traducir("«{n}» está apagado en este servidor. Se activa desde Sistema → Módulos.", { n: nombre })}
        </p>
        {isSuperadmin()
          ? <Link to="/modulos" className="btn btn-primary">{traducir("Ir a Módulos")}</Link>
          : <p className="text-[12.5px] text-ink-3">{traducir("Pídele a un superadministrador que lo active.")}</p>}
      </div>
    </div>
  )
}
