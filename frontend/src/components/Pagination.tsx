import { IconChevronLeft, IconChevronRight } from './Icons'
import { traducir } from '../i18n'

/**
 * Controles de "Mostrando X–Y de Z" + Anterior/Siguiente, extraídos del
 * patrón que ya usaba Usuarios (paginado de a 50 filas) para reusarlo tal
 * cual en cualquier lista que crezca: ACLs, Categorías, Reglas, Ancho de
 * banda. Ver el hook usePaginacion (mismo archivo de hooks) para el estado
 * que lo alimenta.
 */
export default function Pagination({ pagina, totalPaginas, total, porPagina, onChange }: {
  pagina: number
  totalPaginas: number
  total: number
  porPagina: number
  onChange: (pagina: number) => void
}) {
  if (total === 0) return null
  return (
    <div className="flex items-center justify-between mt-4 text-sm">
      <span className="text-ink-3">
        {traducir("Mostrando")} {pagina * porPagina + 1}–{Math.min((pagina + 1) * porPagina, total)} {traducir("de")} {total}
      </span>
      {totalPaginas > 1 && (
        <div className="flex gap-2">
          <button onClick={() => onChange(Math.max(0, pagina - 1))} disabled={pagina === 0}
            className="px-3 py-1.5 border border-line rounded-lg disabled:opacity-40 hover:bg-brand-50 inline-flex items-center gap-1.5">
            <IconChevronLeft className="w-3.5 h-3.5" />{traducir("Anterior")}
          </button>
          <span className="text-ink-3 self-center">
            {traducir("Página {n} de {m}", { n: String(pagina + 1), m: String(totalPaginas) })}
          </span>
          <button onClick={() => onChange(Math.min(totalPaginas - 1, pagina + 1))} disabled={pagina >= totalPaginas - 1}
            className="px-3 py-1.5 border border-line rounded-lg disabled:opacity-40 hover:bg-brand-50 inline-flex items-center gap-1.5">
            {traducir("Siguiente")}<IconChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}
