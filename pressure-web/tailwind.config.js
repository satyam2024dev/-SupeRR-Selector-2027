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
        page: '#0B0D12',
        card: {
          DEFAULT: '#12151C',
          hover: '#181C26',
        },
        border: {
          DEFAULT: '#232834',
          subtle: '#1C212B',
          highlight: '#2F3646',
        },
        content: {
          primary: '#E8EAF0',
          muted: '#8B93A5',
          faint: '#5A6275',
        },
        pink: {
          DEFAULT: '#E6007E',
          hover: '#CC006F',
          muted: 'rgba(230, 0, 126, 0.15)',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
