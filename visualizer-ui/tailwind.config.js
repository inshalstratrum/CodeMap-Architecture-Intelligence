/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#0b0f17",
        panel: "#141923",
        card: "#1b2232",
        cardHover: "#232c3f",
        cardBorder: "#2a3449",
        accent: {
          blue: "#38bdf8",
          cyan: "#22d3ee",
          green: "#4ade80",
          yellow: "#facc15",
          red: "#f87171",
          purple: "#c084fc",
        }
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}
