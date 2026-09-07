import type { ReactNode } from 'react'

// Renderizador de Markdown minimalista para las respuestas del Asistente de
// IA. A propósito NO se usa una librería (react-markdown, remark, etc.): el
// proyecto tiene una regla explícita de no sumar peso/dependencias más allá
// de lo justo necesario, y lo que devuelven los proveedores de chat es
// Markdown simple (encabezados, negrita, listas, tablas, código) — cubrir
// eso a mano es un archivo chico, no un parser completo de CommonMark.

function renderInline(texto: string, keyBase: string): ReactNode[] {
  // Negrita (**texto**), código en línea (`texto`) y saltos de línea en
  // HTML crudo (<br>, <br/>) — el LLM a veces mezcla esto último dentro de
  // celdas de tabla, donde no hay lugar para un salto de línea real en
  // Markdown. En el orden en que aparecen; no soporta anidado (negrita
  // dentro de código, etc.) porque el texto que genera el LLM no lo necesita.
  const partes: ReactNode[] = []
  const regex = /(\*\*(.+?)\*\*|`(.+?)`|<br\s*\/?>)/gi
  let ultimo = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = regex.exec(texto)) !== null) {
    if (m.index > ultimo) partes.push(texto.slice(ultimo, m.index))
    if (m[2] !== undefined) {
      partes.push(<strong key={`${keyBase}-${i++}`}>{m[2]}</strong>)
    } else if (m[3] !== undefined) {
      partes.push(
        <code key={`${keyBase}-${i++}`} className="bg-black/[.06] rounded px-1 py-0.5 text-[0.9em] font-mono">
          {m[3]}
        </code>,
      )
    } else {
      partes.push(<br key={`${keyBase}-${i++}`} />)
    }
    ultimo = regex.lastIndex
  }
  if (ultimo < texto.length) partes.push(texto.slice(ultimo))
  return partes
}

function esFilaTabla(linea: string): boolean {
  return /^\s*\|.*\|\s*$/.test(linea)
}

function esSeparadorTabla(linea: string): boolean {
  return /^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$/.test(linea)
}

function partirFila(linea: string): string[] {
  const t = linea.trim().replace(/^\|/, '').replace(/\|$/, '')
  return t.split('|').map(c => c.trim())
}

export function Markdown({ texto }: { texto: string }) {
  const lineas = texto.split('\n')
  const bloques: ReactNode[] = []
  let i = 0
  let clave = 0

  while (i < lineas.length) {
    const linea = lineas[i]

    // Bloque de código ```...```
    if (/^\s*```/.test(linea)) {
      const codigo: string[] = []
      i++
      while (i < lineas.length && !/^\s*```/.test(lineas[i])) {
        codigo.push(lineas[i])
        i++
      }
      i++ // saltar el cierre
      bloques.push(
        <pre key={clave++} className="bg-black/[.06] rounded-md p-3 overflow-x-auto text-[0.85em] font-mono my-2">
          {codigo.join('\n')}
        </pre>,
      )
      continue
    }

    // Tabla: fila de cabecera + separador (---|---) + filas de datos
    if (esFilaTabla(linea) && i + 1 < lineas.length && esSeparadorTabla(lineas[i + 1])) {
      const cabecera = partirFila(linea)
      i += 2
      const filas: string[][] = []
      while (i < lineas.length && esFilaTabla(lineas[i])) {
        filas.push(partirFila(lineas[i]))
        i++
      }
      bloques.push(
        <div key={clave++} className="overflow-x-auto my-2">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr>
                {cabecera.map((c, j) => (
                  <th key={j} className="text-left border-b border-line px-2 py-1 font-semibold">
                    {renderInline(c, `th-${j}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((fila, fi) => (
                <tr key={fi}>
                  {fila.map((c, j) => (
                    <td key={j} className="border-b border-line-soft px-2 py-1 align-top">
                      {renderInline(c, `td-${fi}-${j}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }

    // Separador horizontal (--- o *** solos en la línea)
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(linea)) {
      bloques.push(<hr key={clave++} className="my-3 border-line" />)
      i++
      continue
    }

    // Encabezados
    const encabezado = linea.match(/^(#{1,4})\s+(.*)$/)
    if (encabezado) {
      const nivel = encabezado[1].length
      const clases = ['text-base font-bold mt-3 mb-1', 'text-base font-bold mt-3 mb-1',
        'text-sm font-bold mt-2 mb-1', 'text-sm font-semibold mt-2 mb-1'][Math.min(nivel, 4) - 1]
      const Tag = (`h${Math.min(nivel + 2, 6)}`) as keyof JSX.IntrinsicElements
      bloques.push(<Tag key={clave++} className={clases}>{renderInline(encabezado[2], `h-${clave}`)}</Tag>)
      i++
      continue
    }

    // Listas (con o sin numerar), agrupando líneas consecutivas
    const esItemLista = /^\s*[-*]\s+/.test(linea)
    const esItemNumerado = /^\s*\d+\.\s+/.test(linea)
    if (esItemLista || esItemNumerado) {
      const items: string[] = []
      while (i < lineas.length && (/^\s*[-*]\s+/.test(lineas[i]) || /^\s*\d+\.\s+/.test(lineas[i]))) {
        items.push(lineas[i].replace(/^\s*([-*]|\d+\.)\s+/, ''))
        i++
      }
      const ListaTag = esItemNumerado ? 'ol' : 'ul'
      bloques.push(
        <ListaTag key={clave++} className={`${esItemNumerado ? 'list-decimal' : 'list-disc'} pl-5 my-1 space-y-0.5`}>
          {items.map((it, j) => <li key={j}>{renderInline(it, `li-${clave}-${j}`)}</li>)}
        </ListaTag>,
      )
      continue
    }

    // Cita (> texto)
    if (/^\s*>\s?/.test(linea)) {
      const cita: string[] = []
      while (i < lineas.length && /^\s*>\s?/.test(lineas[i])) {
        cita.push(lineas[i].replace(/^\s*>\s?/, ''))
        i++
      }
      bloques.push(
        <blockquote key={clave++} className="border-l-2 border-line pl-3 my-2 text-ink-2 italic">
          {cita.join(' ')}
        </blockquote>,
      )
      continue
    }

    // Línea en blanco: separa párrafos, no genera nada por sí sola
    if (linea.trim() === '') {
      i++
      continue
    }

    // Párrafo: junta líneas seguidas sin línea en blanco entre medio
    const parrafo: string[] = [linea]
    i++
    while (i < lineas.length && lineas[i].trim() !== '' && !/^\s*[-*]\s+|^\s*\d+\.\s+|^#{1,4}\s|^\s*```|^\s*>\s?|^\s*(-{3,}|\*{3,})\s*$/.test(lineas[i]) && !esFilaTabla(lineas[i])) {
      parrafo.push(lineas[i])
      i++
    }
    bloques.push(<p key={clave++} className="my-1">{renderInline(parrafo.join(' '), `p-${clave}`)}</p>)
  }

  return <div className="text-sm leading-relaxed">{bloques}</div>
}
