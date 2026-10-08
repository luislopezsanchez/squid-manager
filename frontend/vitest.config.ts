// Configuración de las pruebas (npm test). Aparte de vite.config.ts a propósito: el build del panel (Docker y nativo)
// no debe depender de vitest.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
