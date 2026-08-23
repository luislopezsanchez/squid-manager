import React from 'react'

/**
 * Marco de las pantallas sin sesión (acceso y cambio de contraseña).
 *
 * Fondo azul profundo con la trama de circuito del logo, y la marca presidiendo
 * la tarjeta: es lo primero que ve quien entra.
 */
export default function AuthShell({
  titulo,
  subtitulo,
  children,
  pie,
}: {
  titulo: string
  subtitulo?: string
  children: React.ReactNode
  pie?: React.ReactNode
}) {
  return (
    <div
      className="min-h-screen grid place-items-center px-4 py-10 relative overflow-hidden"
      style={{ background: 'radial-gradient(circle at 18% 8%, #12507C 0%, #0A2C48 48%, #071E33 100%)' }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(127,208,226,.4) 1px, transparent 1px),' +
            'linear-gradient(to bottom, rgba(127,208,226,.4) 1px, transparent 1px)',
          backgroundSize: '42px 42px',
          maskImage: 'radial-gradient(ellipse at 50% 30%, #000 0%, transparent 70%)',
          WebkitMaskImage: 'radial-gradient(ellipse at 50% 30%, #000 0%, transparent 70%)',
        }}
      />

      <div className="relative w-full max-w-[368px] animate-fade-up">
        <div className="bg-surface rounded-2xl p-8 shadow-xl">
          <div className="grid place-items-center mb-1">
            <img
              src="/brand/logo-256.png"
              alt="SquidManager"
              width={78}
              height={75}
              className="w-[78px] h-auto"
            />
          </div>
          <h1 className="text-center text-[21px] font-extrabold text-ink">{titulo}</h1>
          {subtitulo && <p className="text-center text-[13px] text-ink-3 mt-1 mb-6">{subtitulo}</p>}
          {!subtitulo && <div className="mb-6" />}
          {children}
        </div>
        {pie && <div className="text-center text-[11.5px] text-brand-300/70 mt-4">{pie}</div>}
      </div>
    </div>
  )
}
