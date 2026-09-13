// Helpers de graficos SVG compartidos -antes vivian solo dentro de
// Dashboard.tsx; Tendencias.tsx los necesita igual y una segunda copia se
// podria desincronizar (mismo criterio que utils/format.ts).

/**
 * Curva suave que pasa por los puntos medidos, sin inventarse ninguno.
 *
 * Interpolación cúbica monótona (Fritsch-Carlson). Se usa esta y no una spline
 * normal porque una spline corriente se pasa de largo en las curvas: dibujaría
 * picos por encima del máximo real y caídas por debajo de cero. Esta redondea
 * las esquinas con la garantía de no salirse nunca del rango de los datos.
 */
export function monotonePath(pts: [number, number][]): string {
  const n = pts.length
  if (n === 0) return ''
  if (n === 1) return `M${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`
  if (n === 2) {
    return `M${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)} L${pts[1][0].toFixed(2)},${pts[1][1].toFixed(2)}`
  }

  const dx: number[] = []
  const slope: number[] = []
  for (let i = 0; i < n - 1; i++) {
    dx[i] = pts[i + 1][0] - pts[i][0]
    slope[i] = dx[i] === 0 ? 0 : (pts[i + 1][1] - pts[i][1]) / dx[i]
  }

  // Tangente en cada punto: media de las pendientes vecinas, y cero en los
  // cambios de dirección para que el trazo no rebase el punto.
  const m: number[] = new Array(n)
  m[0] = slope[0]
  m[n - 1] = slope[n - 2]
  for (let i = 1; i < n - 1; i++) {
    m[i] = slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2
  }

  // Limitador de Fritsch-Carlson: es lo que asegura que no haya sobreimpulso.
  for (let i = 0; i < n - 1; i++) {
    if (slope[i] === 0) {
      m[i] = 0
      m[i + 1] = 0
      continue
    }
    const a = m[i] / slope[i]
    const b = m[i + 1] / slope[i]
    const s = a * a + b * b
    if (s > 9) {
      const t = 3 / Math.sqrt(s)
      m[i] = t * a * slope[i]
      m[i + 1] = t * b * slope[i]
    }
  }

  let path = `M${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3
    const c1x = pts[i][0] + h
    const c1y = pts[i][1] + m[i] * h
    const c2x = pts[i + 1][0] - h
    const c2y = pts[i + 1][1] - m[i + 1] * h
    path += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${pts[i + 1][0].toFixed(2)},${pts[i + 1][1].toFixed(2)}`
  }
  return path
}

/**
 * Redondea el tope del eje para una magnitud en bytes.
 *
 * Se redondea a 1, 2, 4 u 8 KB/MB/GB en vez de a 1, 2 o 5: los bytes se
 * muestran en múltiplos de 1024, así que un tope "redondo" en decimal como
 * 5000 acabaría escrito como "4.9 KB/s". Con potencias de dos, además, los
 * cuartos del eje caen en cifras exactas.
 */
export function niceCeilBytes(value: number): number {
  const KB = 1024
  if (!Number.isFinite(value) || value <= KB) return KB
  return Math.pow(2, Math.ceil(Math.log2(value)))
}

/** Igual que niceCeilBytes pero para cantidades simples (peticiones), donde
 * no aplica la logica de potencias de dos -acá un tope redondo en base 10
 * (1, 2, 5, 10...) es lo esperable. */
export function niceCeil(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1
  const magnitud = Math.pow(10, Math.floor(Math.log10(value)))
  const normalizado = value / magnitud
  const paso = normalizado <= 1 ? 1 : normalizado <= 2 ? 2 : normalizado <= 5 ? 5 : 10
  return paso * magnitud
}
