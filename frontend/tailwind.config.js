/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Paleta tomada del logo: azules del cuerpo del calamar,
        // cian de los brillos y verde de los LED del servidor.
        brand: {
          50:  '#EEF9FC',
          100: '#D8F1F8',
          200: '#B4E6F1',
          300: '#7FD0E2',
          400: '#48B3D0',
          500: '#2E93BC',
          600: '#1D6A96',
          700: '#0B497C',
          800: '#10466F',
          900: '#0A2C48',
        },
        // Neutros con sesgo azul: un gris puro desentona con el logo
        ink:   { DEFAULT: '#10222F', 2: '#40596B', 3: '#7A93A5' },
        line:  { DEFAULT: '#DDE8EE', soft: '#EBF2F6' },
        surface: '#FFFFFF',
        ground:  '#F2F7FA',
        ok:     { DEFAULT: '#2F9E75', soft: '#E3F5EE' },
        warn:   { DEFAULT: '#B26A12', soft: '#FCF1E0' },
        danger: { DEFAULT: '#C0392F', soft: '#FBEAE8' },
        // Se conservan por compatibilidad con el código anterior
        primary: {
          50: '#EEF9FC', 100: '#D8F1F8', 200: '#B4E6F1', 300: '#7FD0E2',
          400: '#48B3D0', 500: '#2E93BC', 600: '#0B497C', 700: '#10466F',
          800: '#0A2C48', 900: '#071E33',
        },
        accent: { 400: '#7FD0E2', 500: '#48B3D0', 600: '#2E93BC', 700: '#1D6A96' },
      },
      // Escala tipografica propia, un punto por encima de la de Tailwind:
      // el panel se lee de lejos y con los tamanos por defecto los textos
      // secundarios quedaban justos.
      fontSize: {
        xs:   ['0.8125rem', { lineHeight: '1.125rem' }],   // 13px
        sm:   ['0.9375rem', { lineHeight: '1.375rem' }],   // 15px
        base: ['1.0625rem', { lineHeight: '1.625rem' }],   // 17px
        lg:   ['1.1875rem', { lineHeight: '1.8125rem' }],  // 19px
        xl:   ['1.3125rem', { lineHeight: '1.875rem' }],   // 21px
        '2xl': ['1.625rem', { lineHeight: '2.125rem' }],   // 26px
        '3xl': ['2rem',     { lineHeight: '2.375rem' }],   // 32px
      },
      fontFamily: {
        sans: ['Figtree', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'Menlo', 'monospace'],
      },
      borderRadius: { lg: '11px', xl: '14px', '2xl': '18px' },
      boxShadow: {
        sm: '0 1px 2px rgba(16,34,47,.04)',
        DEFAULT: '0 1px 2px rgba(16,34,47,.04), 0 6px 20px -8px rgba(16,34,47,.14)',
        lg: '0 2px 4px rgba(16,34,47,.05), 0 18px 40px -14px rgba(16,34,47,.24)',
        xl: '0 24px 60px -20px rgba(0,0,0,.35)',
      },
    },
  },
  plugins: [],
}
