/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        surface: '#111827',
        'surface-card': '#1E293B',
        'aegis-cyan': '#06B6D4',
        'aegis-indigo': '#6366F1',
        'aegis-emerald': '#10B981',
        'aegis-amber': '#F59E0B',
        'aegis-rose': '#F43F5E',
      },
      animation: {
        'pulse-fast': 'pulse 1.2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
