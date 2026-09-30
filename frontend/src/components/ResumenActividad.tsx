import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api, type RangoFechas } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'
import { DonaReparto, GraficoTiempo, TarjetaGrafico, MARCA, SERIE } from './charts'

export type TipoActividad = 'usuarios' | 'dominios' | 'bloqueados-dominio' | 'bloqueados-usuario' | 'ips-compartidas'

type Puntos = { granularidad: 'minuto' | 'hora' | 'dia'; puntos: Record<string, number>[] }

// Cada pestaña cuenta algo propio a lo largo del tiempo (antes todas repetían el mismo
// gráfico de tráfico): qué medir, cómo titularlo y con qué color.
const CONFIG: Record<TipoActividad, { key: string; titulo: string; sub: string; label: string; color: string; formato: (n: number) => string }> = {
  usuarios: { key: 'bytes', titulo: traducir("Tráfico en la ventana"), sub: traducir("Datos transferidos a lo largo del tiempo"), label: traducir('Tráfico'), color: MARCA, formato: formatBytes },
  dominios: { key: 'sitios', titulo: traducir("Sitios distintos visitados"), sub: traducir("Cuántos sitios diferentes se visitaron en cada periodo"), label: traducir('Sitios'), color: SERIE[0], formato: formatNumber },
  'bloqueados-dominio': { key: 'bloqueadas', titulo: traducir("Peticiones bloqueadas en el tiempo"), sub: traducir("Cuándo chocó más tráfico contra las reglas de denegación"), label: traducir('Bloqueadas'), color: '#C0392B', formato: formatNumber },
  'bloqueados-usuario': { key: 'usuarios', titulo: traducir("Usuarios con bloqueos en el tiempo"), sub: traducir("Cuántos usuarios distintos fueron bloqueados en cada periodo"), label: traducir('Usuarios'), color: '#C0392B', formato: formatNumber },
  'ips-compartidas': { key: 'ips', titulo: traducir("IPs compartidas detectadas"), sub: traducir("Cuántas IPs tuvieron más de una cuenta en cada periodo"), label: traducir('IPs'), color: '#E0A036', formato: formatNumber },
}

/** Resumen visual de Actividad de red: cuánto pesa cada uno de los primeros
 * del ranking sobre el total y cómo evolucionó, en el tiempo, lo que mide la pestaña. */
export function ResumenActividad({ tipo, ventana, rango, porDatos, filas, total, formato, tituloReparto }: {
  tipo: TipoActividad
  ventana: string
  rango?: RangoFechas
  porDatos: boolean
  filas: { etiqueta: string; valor: number }[]
  total: number
  formato: (n: number) => string
  tituloReparto: string
}) {
  const [serie, setSerie] = useState<Puntos | null>(null)
  const ventanaValida = ['1h', '24h', '7d', '30d'].includes(ventana) || !!rango
  // Las series propias salen de los agregados por hora: para 1 h no hay suficiente detalle.
  const necesita24 = tipo !== 'usuarios' && ventana === '1h' && !rango

  useEffect(() => {
    if (!ventanaValida || necesita24) { setSerie(null); return }
    if (tipo === 'usuarios' && !rango) {
      api.getVolumenPorPeriodo(ventana).then(setSerie as any).catch(() => setSerie(null))
    } else {
      api.getActividadSerie(tipo, rango ? undefined : ventana, rango).then(setSerie).catch(() => setSerie(null))
    }
  }, [tipo, ventana, ventanaValida, necesita24, rango?.desde, rango?.hasta])

  const c = CONFIG[tipo]
  // En la pestaña de usuarios el toggle Datos/Peticiones también decide qué se dibuja.
  const cfg = tipo === 'usuarios' && !porDatos
    ? { ...c, key: 'requests', titulo: traducir("Peticiones en la ventana"), sub: traducir("Peticiones a lo largo del tiempo"), label: traducir('Peticiones'), formato: formatNumber }
    : c

  const top = filas.slice(0, 3)
  const sumaTop = top.reduce((a, f) => a + f.valor, 0)
  const items = [
    ...top.map((f, i) => ({ nombre: f.etiqueta, valor: f.valor, color: SERIE[i] })),
    { nombre: traducir('Resto'), valor: Math.max(total - sumaTop, 0), color: '#b8c8d3' },
  ]

  return (
    <div className="grid grid-cols-1 xl:grid-cols-5 gap-4 mb-6">
      <TarjetaGrafico titulo={tituloReparto} subtitulo={traducir("Peso de los tres primeros sobre el total de la ventana")} className="xl:col-span-2">
        {total > 0 ? (
          <DonaReparto items={items} formato={formato} altura={170} centro={{ titulo: traducir('total'), valor: formato(total) }} />
        ) : <p className="text-sm text-ink-3 py-6">{traducir("Sin datos todavía.")}</p>}
      </TarjetaGrafico>
      <TarjetaGrafico titulo={cfg.titulo} subtitulo={cfg.sub} className="xl:col-span-3">
        {serie && serie.puntos.length > 0 ? (
          <GraficoTiempo datos={serie.puntos as any} granularidad={serie.granularidad} altura={190} formatoEje={cfg.formato}
            series={[{ key: cfg.key, label: cfg.label, color: cfg.color, formato: cfg.formato }]} />
        ) : (
          <p className="text-sm text-ink-3 py-6">
            {necesita24 ? traducir("Esta gráfica necesita una ventana de 24 h o más.")
              : ventanaValida ? traducir("Sin datos todavía.") : traducir("Elige una ventana de 1 h, 24 h, 7 d o 30 d para ver la evolución.")}
          </p>
        )}
      </TarjetaGrafico>
    </div>
  )
}
export { formatNumber }
