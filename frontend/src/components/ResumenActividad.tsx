import { useEffect, useState } from 'react'
import { traducir } from '../i18n'
import { api } from '../api/client'
import { formatBytes, formatNumber } from '../utils/format'
import { DonaReparto, GraficoTiempo, TarjetaGrafico, MARCA, SERIE } from './charts'

/** Resumen visual de Actividad de red: cuánto pesa cada uno de los primeros
 * del ranking sobre el total y cómo evolucionó el tráfico en la ventana. */
export function ResumenActividad({ ventana, filas, total, formato, tituloReparto }: {
  ventana: string
  filas: { etiqueta: string; valor: number }[]
  total: number
  formato: (n: number) => string
  tituloReparto: string
}) {
  const [serie, setSerie] = useState<{ granularidad: 'minuto' | 'hora' | 'dia'; puntos: { timestamp: number; bytes: number; requests: number }[] } | null>(null)
  const ventanaValida = ['1h', '24h', '7d', '30d'].includes(ventana)

  useEffect(() => {
    if (!ventanaValida) { setSerie(null); return }
    api.getVolumenPorPeriodo(ventana).then(setSerie).catch(() => setSerie(null))
  }, [ventana, ventanaValida])

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
      <TarjetaGrafico titulo={traducir("Tráfico en la ventana")} subtitulo={traducir("Datos transferidos a lo largo del tiempo")} className="xl:col-span-3">
        {serie && serie.puntos.length > 0 ? (
          <GraficoTiempo datos={serie.puntos} granularidad={serie.granularidad} altura={190} formatoEje={formatBytes}
            series={[{ key: 'bytes', label: traducir('Tráfico'), color: MARCA, formato: formatBytes }]} />
        ) : (
          <p className="text-sm text-ink-3 py-6">
            {ventanaValida ? traducir("Sin datos todavía.") : traducir("Elige una ventana de 1 h, 24 h, 7 d o 30 d para ver la evolución.")}
          </p>
        )}
      </TarjetaGrafico>
    </div>
  )
}
export { formatNumber }
