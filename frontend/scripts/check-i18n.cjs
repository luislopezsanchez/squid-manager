#!/usr/bin/env node
/**
 * Verifica que toda clave de traducir("...") usada en el código exista en
 * en.json y pt.json.
 *
 * La clave de cada texto es el propio texto en español (ver
 * src/i18n/index.ts): sin este chequeo, un texto nuevo que alguien olvida
 * agregar a en.json/pt.json no rompe nada visible en español -recién se
 * nota en inglés o portugués, y a mano se van encontrando de a uno (así
 * aparecieron "Aplicar ahora", "n/d", "Redir.", "errores", "Otros" y otros
 * más en la sesión del 2026-09-24). Este script corta eso de raíz: falla
 * el build si falta una clave, en vez de descubrirlo en producción en el
 * idioma equivocado.
 *
 * Limitación conocida y aceptada: solo puede verificar el primer argumento
 * de traducir(...) cuando es un string literal simple/doble comillas. Una
 * plantilla con interpolación (traducir(`Conectado — ${n} modelos`)) no
 * tiene una clave fija -no se puede, ni tendría sentido, verificar contra
 * el diccionario- así que esos casos se listan aparte, informativamente,
 * sin hacer fallar el chequeo.
 */

const fs = require('fs')
const path = require('path')

const SRC_DIR = path.join(__dirname, '..', 'src')
const EN_PATH = path.join(SRC_DIR, 'i18n', 'en.json')
const PT_PATH = path.join(SRC_DIR, 'i18n', 'pt.json')

function listSourceFiles(dir) {
  const out = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...listSourceFiles(full))
    } else if (/\.(tsx?|jsx?)$/.test(entry.name)) {
      out.push(full)
    }
  }
  return out
}

// Convierte las secuencias de escape de un string de JS/TS (\" \' \\ \n etc.)
// a su caracter literal, para comparar contra la clave real del JSON.
//
// Antes esto delegaba en JSON.parse('"' + raw + '"'), que ANDA MAL apenas
// `raw` viene de un string con comilla simple que contiene una comilla doble
// sin escapar (traducir('Nuevo · reemplaza a "Usuarios con más bloqueos"')
// es JS valido, pero al envolverlo en comillas dobles para el JSON.parse
// revienta por la comilla doble suelta de adentro) -el catch silenciaba el
// error y la clave se perdia del todo, sin figurar ni siquiera como
// "faltante": el chequeo pasaba en verde con una traduccion realmente
// faltante. Bug real, encontrado en vivo (2026-09-25) mientras se agregaba
// justo un texto asi -y habia otro caso identico, ya en produccion, en
// Categorias.tsx, que este chequeo nunca detecto por lo mismo.
function unescapeJsString(raw) {
  return raw.replace(/\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)/gs, (entero, esc) => {
    if (esc[0] === 'u' || esc[0] === 'x') {
      try {
        return JSON.parse('"\\' + esc + '"')
      } catch {
        return entero
      }
    }
    const mapa = { n: '\n', t: '\t', r: '\r', b: '\b', f: '\f', '0': '\0' }
    return esc in mapa ? mapa[esc] : esc
  })
}

// Busca traducir(...) y, si el primer argumento es un string literal
// simple ('...' o "..."), devuelve la clave; si es un template literal
// (`...`) lo reporta aparte como "dinámico" sin poder verificarlo.
function extraerLlamadas(contenido) {
  const claves = []
  const dinamicas = []
  const regex = /\btraducir\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g
  let m
  while ((m = regex.exec(contenido)) !== null) {
    const [, quote, raw] = m
    if (quote === '`') {
      if (raw.includes('${')) {
        dinamicas.push(raw)
        continue
      }
      // Template literal sin interpolación: se comporta como un string fijo.
      claves.push(raw)
      continue
    }
    claves.push(unescapeJsString(raw))
  }
  return { claves, dinamicas }
}

function main() {
  const en = JSON.parse(fs.readFileSync(EN_PATH, 'utf8'))
  const pt = JSON.parse(fs.readFileSync(PT_PATH, 'utf8'))
  const archivos = listSourceFiles(SRC_DIR)

  const faltantesEn = new Map() // clave -> [archivos]
  const faltantesPt = new Map()
  let totalClaves = 0
  let totalDinamicas = 0

  for (const archivo of archivos) {
    const contenido = fs.readFileSync(archivo, 'utf8')
    const { claves, dinamicas } = extraerLlamadas(contenido)
    const rel = path.relative(process.cwd(), archivo)
    totalDinamicas += dinamicas.length
    for (const clave of claves) {
      totalClaves++
      if (!(clave in en)) {
        if (!faltantesEn.has(clave)) faltantesEn.set(clave, [])
        faltantesEn.get(clave).push(rel)
      }
      if (!(clave in pt)) {
        if (!faltantesPt.has(clave)) faltantesPt.set(clave, [])
        faltantesPt.get(clave).push(rel)
      }
    }
  }

  const totalFaltantes = faltantesEn.size + faltantesPt.size

  if (totalFaltantes === 0) {
    console.log(`i18n: ${totalClaves} claves verificadas en ${archivos.length} archivos, todas presentes en en.json y pt.json.`)
    if (totalDinamicas > 0) {
      console.log(`i18n: ${totalDinamicas} llamada(s) con interpolación en el texto (template literal) no se pueden verificar -no tienen una clave fija.`)
    }
    process.exit(0)
  }

  console.error(`i18n: faltan ${totalFaltantes} clave(s) de traducción.\n`)
  for (const [clave, archivos] of faltantesEn) {
    console.error(`  [en.json] falta: "${clave}"`)
    console.error(`    usado en: ${archivos.join(', ')}`)
  }
  for (const [clave, archivos] of faltantesPt) {
    console.error(`  [pt.json] falta: "${clave}"`)
    console.error(`    usado en: ${archivos.join(', ')}`)
  }
  process.exit(1)
}

main()
