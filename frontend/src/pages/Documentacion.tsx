import { useState } from 'react'
import { traducir, idiomaActual } from '../i18n'
import {
  IconFile, IconEye, IconActivity, IconShield, IconGlobe, IconTool, IconInfo,
} from '../components/Icons'
import { Markdown } from '../components/Markdown'
import { DOC_ACTIVIDAD_RED } from '../content/docsActividadRed'
import { DOC_LATENCIA_ERRORES } from '../content/docsLatenciaErrores'
import { DOC_ESTADO_CACHE } from '../content/docsEstadoCache'
import { DOC_TENDENCIAS } from '../content/docsTendencias'
import { DOC_PANORAMA } from '../content/docsPanorama'
import { DOC_ACLS } from '../content/docsAcls'
import { DOC_REGISTROS } from '../content/docsRegistros'
import { DOC_HISTORICO } from '../content/docsHistorico'
import { DOC_AUDITORIA } from '../content/docsAuditoria'
import { DOC_USUARIOS } from '../content/docsUsuarios'
import { DOC_GRUPOS } from '../content/docsGrupos'
import { DOC_REGLAS_ACCESO } from '../content/docsReglasAcceso'
import { DOC_ANCHO_BANDA } from '../content/docsAnchoBanda'
import { DOC_LDAP } from '../content/docsLdap'
import { DOC_KERBEROS } from '../content/docsKerberos'
import { DOC_SYSLOG } from '../content/docsSyslog'
import { DOC_PROXY_PADRE } from '../content/docsProxyPadre'
import { DOC_NOTIFICACIONES } from '../content/docsNotificaciones'
import { DOC_CERTIFICADO } from '../content/docsCertificado'
import { DOC_CONFIGURACION } from '../content/docsConfiguracion'
import { DOC_BACKUP_MIGRACION } from '../content/docsBackupMigracion'
import { DOC_ADMINISTRADORES } from '../content/docsAdministradores'
import { DOC_SMTP } from '../content/docsSmtp'

type Articulo = { slug: string; titulo: string; listo: boolean; contenido?: Record<'es' | 'en' | 'pt', string> }
type Grupo = { id: string; titulo: string; Icon: (p: { className?: string }) => JSX.Element; articulos: Articulo[] }

// Misma agrupacion que el menu lateral (Layout.tsx), para que encontrar un
// tema en Documentacion sea igual de intuitivo que encontrar la seccion en
// si -sin inventar una taxonomia aparte. `listo` en false hasta que ese
// articulo tenga contenido de verdad escrito en los 3 idiomas.
const GRUPOS: Grupo[] = [
  {
    id: 'vigilancia', titulo: traducir('Vigilancia'), Icon: IconEye,
    articulos: [
      { slug: 'registros', titulo: traducir('Registros'), listo: true, contenido: DOC_REGISTROS },
      { slug: 'historico', titulo: traducir('Histórico'), listo: true, contenido: DOC_HISTORICO },
      { slug: 'auditoria', titulo: traducir('Auditoría'), listo: true, contenido: DOC_AUDITORIA },
    ],
  },
  {
    id: 'analisis', titulo: traducir('Análisis'), Icon: IconActivity,
    articulos: [
      { slug: 'actividad-de-red', titulo: traducir('Actividad de red'), listo: true, contenido: DOC_ACTIVIDAD_RED },
      { slug: 'estadisticas-de-cache', titulo: traducir('Estado del caché'), listo: true, contenido: DOC_ESTADO_CACHE },
      { slug: 'latencia-y-errores', titulo: traducir('Latencia y errores'), listo: true, contenido: DOC_LATENCIA_ERRORES },
      { slug: 'tendencias', titulo: traducir('Tendencias'), listo: true, contenido: DOC_TENDENCIAS },
      { slug: 'panorama', titulo: traducir('Panorama'), listo: true, contenido: DOC_PANORAMA },
    ],
  },
  {
    id: 'gestion', titulo: traducir('Gestión'), Icon: IconShield,
    articulos: [
      { slug: 'usuarios', titulo: traducir('Usuarios'), listo: true, contenido: DOC_USUARIOS },
      { slug: 'grupos', titulo: traducir('Grupos'), listo: true, contenido: DOC_GRUPOS },
      { slug: 'acls', titulo: traducir('ACLs'), listo: true, contenido: DOC_ACLS },
      { slug: 'reglas-de-acceso', titulo: traducir('Reglas de acceso'), listo: true, contenido: DOC_REGLAS_ACCESO },
      { slug: 'ancho-de-banda', titulo: traducir('Ancho de banda'), listo: true, contenido: DOC_ANCHO_BANDA },
    ],
  },
  {
    id: 'integraciones', titulo: traducir('Integraciones'), Icon: IconGlobe,
    articulos: [
      { slug: 'ldap', titulo: 'LDAP', listo: true, contenido: DOC_LDAP },
      { slug: 'kerberos', titulo: 'Kerberos', listo: true, contenido: DOC_KERBEROS },
      { slug: 'syslog-externo', titulo: traducir('Syslog externo'), listo: true, contenido: DOC_SYSLOG },
      { slug: 'proxy-padre', titulo: traducir('Proxy padre'), listo: true, contenido: DOC_PROXY_PADRE },
      { slug: 'notificaciones', titulo: traducir('Notificaciones'), listo: true, contenido: DOC_NOTIFICACIONES },
    ],
  },
  {
    id: 'sistema', titulo: traducir('Sistema'), Icon: IconTool,
    articulos: [
      { slug: 'certificado', titulo: traducir('Certificado'), listo: true, contenido: DOC_CERTIFICADO },
      { slug: 'configuracion', titulo: traducir('Configuración'), listo: true, contenido: DOC_CONFIGURACION },
      { slug: 'smtp', titulo: traducir('SMTP'), listo: true, contenido: DOC_SMTP },
      { slug: 'backup-y-migracion', titulo: traducir('Backup y migración'), listo: true, contenido: DOC_BACKUP_MIGRACION },
      { slug: 'administradores', titulo: traducir('Administradores'), listo: true, contenido: DOC_ADMINISTRADORES },
    ],
  },
]

export default function Documentacion() {
  const [seleccion, setSeleccion] = useState<Articulo | null>(null)

  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-ink mb-1">{traducir("Documentación")}</h1>
      <p className="text-sm text-ink-3 mb-6">
        {traducir("Guías y referencia de SquidManager.")}
      </p>

      <div className="flex gap-6 items-start">
        <nav className="w-72 flex-none card border border-line-soft p-2 space-y-3">
          {GRUPOS.map(grupo => (
            <div key={grupo.id}>
              <div className="flex items-center gap-2 px-2 pb-1.5 border-b border-line-soft text-[11px] font-medium uppercase tracking-[.08em] text-ink-3">
                <grupo.Icon className="w-[14px] h-[14px] flex-none opacity-70" />
                {grupo.titulo}
              </div>
              <div className="flex flex-col gap-0.5 mt-1.5">
                {grupo.articulos.map(art => (
                  <button
                    key={art.slug}
                    onClick={() => setSeleccion(art)}
                    className={`flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-[13.5px] text-left transition
                      ${seleccion?.slug === art.slug ? 'bg-brand-50 text-brand-700 font-medium' : 'text-ink-2 hover:bg-line-soft/60'}`}
                  >
                    <span className="flex items-center gap-2">
                      <IconFile className="w-[15px] h-[15px] flex-none opacity-60" />
                      {art.titulo}
                    </span>
                    {!art.listo && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-warn-soft text-warn font-medium flex-none">
                        {traducir("Pendiente")}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {seleccion?.contenido ? (
          <div className="flex-1 card p-8 border border-line-soft min-h-[420px]">
            <h2 className="text-xl font-bold text-ink mb-4">{seleccion.titulo}</h2>
            <Markdown texto={seleccion.contenido[idiomaActual()] || seleccion.contenido.es} />
          </div>
        ) : (
          <div className="flex-1 card p-8 border border-line-soft min-h-[420px] flex flex-col items-center justify-center text-center gap-3">
            {seleccion ? (
              <>
                <span className="stat-icon"><IconFile /></span>
                <h2 className="font-semibold text-ink">{seleccion.titulo}</h2>
                <p className="text-sm text-ink-3 max-w-md">
                  {traducir("Este artículo todavía no tiene contenido. Se va completando a medida que cada sección queda terminada.")}
                </p>
              </>
            ) : (
              <>
                <span className="stat-icon"><IconInfo /></span>
                <p className="text-ink-2">{traducir("Elige un tema del listado para ver su guía.")}</p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
