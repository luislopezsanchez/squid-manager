/**
 * Iconos de línea del panel.
 *
 * Sustituyen a los emojis del menú: a tamaño pequeño los emojis se ven
 * distintos en cada sistema operativo y desentonan con el logo.
 */
type Props = { className?: string }

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  viewBox: '0 0 24 24',
}

export const IconDashboard = ({ className }: Props) => (
  <svg {...base} className={className}><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></svg>
)

export const IconUsers = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
  </svg>
)

export const IconTag = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M12 2 2 7l10 5 10-5-10-5Z" /><path d="m2 17 10 5 10-5" /><path d="m2 12 10 5 10-5" />
  </svg>
)

export const IconRules = ({ className }: Props) => (
  <svg {...base} className={className}>
    <rect x="3" y="4" width="18" height="6" rx="2" /><rect x="3" y="14" width="18" height="6" rx="2" />
    <path d="M7 7h.01M7 17h.01" />
  </svg>
)

export const IconGauge = ({ className }: Props) => (
  <svg {...base} className={className}><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>
)

export const IconLink = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
)

export const IconGroups = ({ className }: Props) => (
  <svg {...base} className={className}>
    <circle cx="9" cy="7" r="3" /><circle cx="17" cy="9" r="2.5" />
    <path d="M3 20v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1" /><path d="M17 14a4 4 0 0 1 4 4v2" />
  </svg>
)

export const IconSettings = ({ className }: Props) => (
  <svg {...base} className={className}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
  </svg>
)

export const IconLock = ({ className }: Props) => (
  <svg {...base} className={className}>
    <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
)

export const IconAudit = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </svg>
)

export const IconBackup = ({ className }: Props) => (
  <svg {...base} className={className}>
    <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3" />
  </svg>
)

export const IconLogs = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
    <path d="M14 2v6h6" /><path d="M8 13h8M8 17h5" />
  </svg>
)

export const IconBell = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
  </svg>
)

export const IconShield = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-4" />
  </svg>
)

export const IconBolt = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.2}><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z" /></svg>
)

export const IconKey = ({ className }: Props) => (
  <svg {...base} className={className}>
    <circle cx="7.5" cy="15.5" r="4.5" /><path d="m21 2-9.6 9.6" /><path d="m15.5 7.5 3 3L22 7l-3-3" />
  </svg>
)

export const IconLogout = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" />
  </svg>
)

export const IconPlus = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.4}><path d="M12 5v14M5 12h14" /></svg>
)

export const IconCheck = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.4}><path d="M20 6 9 17l-5-5" /></svg>
)

export const IconAlert = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.2}>
    <path d="M12 9v4M12 17h.01" />
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
  </svg>
)

export const IconClose = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.4}><path d="M18 6 6 18M6 6l12 12" /></svg>
)

export const IconEye = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
  </svg>
)

export const IconSpinner = ({ className }: Props) => (
  <svg className={className} viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
  </svg>
)

/* ---------- Acciones ---------- */

export const IconDownload = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" /><path d="M12 15V3" />
  </svg>
)

export const IconUpload = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m17 8-5-5-5 5" /><path d="M12 3v12" />
  </svg>
)

export const IconRefresh = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15 6.7L3 16" /><path d="M3 21v-5h5" />
  </svg>
)

export const IconFile = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" />
  </svg>
)

export const IconStop = ({ className }: Props) => (
  <svg {...base} className={className}><circle cx="12" cy="12" r="10" /><path d="M4.9 4.9 19.1 19.1" /></svg>
)

export const IconBan = ({ className }: Props) => (
  <svg {...base} className={className}><circle cx="12" cy="12" r="10" /><path d="m4.9 4.9 14.2 14.2" /></svg>
)

export const IconGlobe = ({ className }: Props) => (
  <svg {...base} className={className}>
    <circle cx="12" cy="12" r="10" /><path d="M2 12h20" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10Z" />
  </svg>
)

export const IconActivity = ({ className }: Props) => (
  <svg {...base} className={className}><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
)

export const IconMail = ({ className }: Props) => (
  <svg {...base} className={className}>
    <rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-10 6L2 7" />
  </svg>
)

export const IconSend = ({ className }: Props) => (
  <svg {...base} className={className}><path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4Z" /></svg>
)

export const IconInfo = ({ className }: Props) => (
  <svg {...base} className={className}>
    <circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" />
  </svg>
)

export const IconTool = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76Z" />
  </svg>
)

export const IconRocket = ({ className }: Props) => (
  <svg {...base} className={className}>
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09Z" />
    <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2Z" />
    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
  </svg>
)

/* ---------- Flechas ---------- */

export const IconArrowDown = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.5}><path d="M12 5v14M19 12l-7 7-7-7" /></svg>
)

export const IconArrowUp = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.5}><path d="M12 19V5M5 12l7-7 7 7" /></svg>
)

export const IconChevronUp = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.5}><path d="m18 15-6-6-6 6" /></svg>
)

export const IconChevronDown = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.5}><path d="m6 9 6 6 6-6" /></svg>
)

export const IconChevronLeft = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.5}><path d="m15 18-6-6 6-6" /></svg>
)

export const IconChevronRight = ({ className }: Props) => (
  <svg {...base} className={className} strokeWidth={2.5}><path d="m9 18 6-6-6-6" /></svg>
)

/* ---------- Plataformas ----------
   Siluetas simplificadas: identifican el sistema de un vistazo sin recurrir a
   emojis, que se dibujan distinto en cada sistema operativo. */

export const IconWindows = ({ className }: Props) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M3 5.5 10.5 4.4v7.1H3V5.5Zm0 13 7.5 1.1v-7H3v5.9Zm8.6 1.2L21 21V12.5h-9.4v7.2Zm0-15.4v7.2H21V3l-9.4 1.3Z" />
  </svg>
)

export const IconApple = ({ className }: Props) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M16.4 12.7c0-2.5 2-3.7 2.1-3.8-1.2-1.7-3-1.9-3.6-2-1.5-.2-3 .9-3.8.9-.8 0-2-.9-3.3-.86-1.7.02-3.3 1-4.2 2.5-1.8 3.1-.5 7.7 1.3 10.2.9 1.2 1.9 2.6 3.2 2.5 1.3-.05 1.8-.83 3.4-.83 1.6 0 2 .83 3.4.8 1.4-.02 2.3-1.25 3.2-2.46.7-.95 1-1.9 1-1.95-.02-.01-2.7-1.05-2.7-4.06ZM14 5.3c.7-.85 1.2-2.03 1-3.2-1 .04-2.2.67-2.9 1.5-.65.75-1.2 1.95-1.05 3.1 1.1.08 2.25-.56 2.95-1.4Z" />
  </svg>
)

export const IconLinux = ({ className }: Props) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12 2c-2.2 0-3.5 1.7-3.5 4 0 1.3.2 2.2.2 3.2 0 1-.7 1.8-1.5 3-.9 1.3-1.7 2.6-1.7 4.1 0 .6.1 1.1.4 1.5-.5.3-.9.7-.9 1.3 0 1.2 1.7 1.9 4 2.2 1.4.2 2.4.7 3 .7s1.6-.5 3-.7c2.3-.3 4-1 4-2.2 0-.6-.4-1-.9-1.3.3-.4.4-.9.4-1.5 0-1.5-.8-2.8-1.7-4.1-.8-1.2-1.5-2-1.5-3 0-1 .2-1.9.2-3.2 0-2.3-1.3-4-3.5-4Zm-1.4 4.2c.4 0 .7.4.7 1s-.3 1-.7 1-.7-.5-.7-1 .3-1 .7-1Zm2.8 0c.4 0 .7.4.7 1s-.3 1-.7 1-.7-.5-.7-1 .3-1 .7-1ZM12 9.2c.9 0 1.9.5 1.9 1 0 .3-.4.5-.8.8-.4.2-.8.5-1.1.5s-.7-.3-1.1-.5c-.4-.3-.8-.5-.8-.8 0-.5 1-1 1.9-1Z" />
  </svg>
)

export const IconFirefox = ({ className }: Props) => (
  <svg {...base} className={className}>
    <circle cx="12" cy="12" r="9.5" />
    <path d="M6 9c1.5-2.5 4-3.5 6.5-3 1 .2 1.8.8 2.3 1.6" />
    <path d="M18.5 8.5c1 2.2.6 5-1.3 6.8-2.3 2.2-6 2.2-8.3 0-1-1-1.5-2.3-1.5-3.6" />
  </svg>
)
