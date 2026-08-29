/**
 * Traduccion del panel al espanol, ingles y portugues.
 *
 * La clave de cada texto es el propio texto en espanol, no un identificador
 * inventado. Es el mismo enfoque de gettext, y aqui resuelve dos problemas
 * concretos de traducir una aplicacion que ya existe:
 *
 *  - No hay que bautizar cientos de cadenas ni mantener esa nomenclatura.
 *  - Lo que falte por traducir sale en espanol, no como `paginas.acl.titulo`.
 *    Una traduccion incompleta se ve imperfecta, no rota.
 *
 * `t` es una funcion normal, no un hook, a proposito: buena parte del texto de
 * la interfaz vive en constantes de modulo (etiquetas de tipos de ACL, clases
 * de delay pool, columnas de tablas) que se evaluan antes de que exista ningun
 * componente. Con un hook habria que mover todas esas constantes dentro de los
 * componentes; asi funcionan tal cual estan.
 */

import en from './en.json'
import pt from './pt.json'

export type Idioma = 'es' | 'en' | 'pt'

export const IDIOMAS: { codigo: Idioma; nombre: string }[] = [
  { codigo: 'es', nombre: 'Español' },
  { codigo: 'en', nombre: 'English' },
  { codigo: 'pt', nombre: 'Português' },
]

const DICCIONARIOS: Record<string, Record<string, string>> = { en, pt }

const CLAVE_ALMACEN = 'idioma'

function detectar(): Idioma {
  const guardado = localStorage.getItem(CLAVE_ALMACEN)
  if (guardado === 'es' || guardado === 'en' || guardado === 'pt') return guardado

  // Sin eleccion previa se usa el del navegador. 'pt-BR' y 'pt-PT' comparten
  // diccionario: las diferencias no afectan a este vocabulario.
  const navegador = (navigator.language || 'es').slice(0, 2).toLowerCase()
  if (navegador === 'en' || navegador === 'pt') return navegador
  return 'es'
}

let idioma: Idioma = detectar()

export function idiomaActual(): Idioma {
  return idioma
}

/**
 * Cambia el idioma y recarga la pagina.
 *
 * La recarga es deliberada. Con `t` como funcion de modulo, React no tiene
 * forma de saber que hay que volver a pintar, y los textos que ya estan en
 * constantes de modulo no se recalcularian nunca. Recargar deja toda la
 * interfaz coherente de una vez, y en un panel de administracion cambiar de
 * idioma es algo que se hace una vez, no continuamente.
 */
export function cambiarIdioma(nuevo: Idioma): void {
  localStorage.setItem(CLAVE_ALMACEN, nuevo)
  idioma = nuevo
  window.location.reload()
}

/**
 * Traduce un texto al idioma activo.
 *
 * @param texto  El original en espanol, que hace de clave.
 * @param vars   Sustituciones opcionales para los marcadores {nombre}.
 */
export function traducir(texto: string, vars?: Record<string, string | number>): string {
  const diccionario = DICCIONARIOS[idioma]
  let salida = (diccionario && diccionario[texto]) || texto

  if (vars) {
    for (const [clave, valor] of Object.entries(vars)) {
      salida = salida.split(`{${clave}}`).join(String(valor))
    }
  }
  return salida
}

// Alias corto para escribir a mano. El codigo generado usa `traducir` y no
// `t` porque `t` ya es el nombre de variables locales en alguna pagina, y
// la colision rompia la compilacion.
export const t = traducir
