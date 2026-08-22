/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f4f8',
          100: '#d9e6f2',
          200: '#b3cce6',
          300: '#80a8d2',
          400: '#4a7fb5',
          500: '#299ac2',
          600: '#0b497c',
          700: '#093d66',
          800: '#083151',
          900: '#061f35',
        },
        accent: {
          400: '#4ab8d8',
          500: '#299ac2',
          600: '#1a7a9a',
          700: '#155a70',
        },
      },
    },
  },
  plugins: [],
}