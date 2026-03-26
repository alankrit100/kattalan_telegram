/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'ui-monospace', 'monospace'],
        sans: ['"Inter"', 'ui-sans-serif', 'system-ui'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.7s ease forwards',
        'bar-shimmer': 'shimmer 1.5s infinite',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(34,197,94,0.6)' },
          '50%': { boxShadow: '0 0 20px rgba(34,197,94,1)' },
        },
      },
      boxShadow: {
        'glow-green': '0 0 20px rgba(34,197,94,0.5), 0 0 40px rgba(34,197,94,0.25)',
        'glow-red': '0 0 20px rgba(239,68,68,0.5), 0 0 40px rgba(239,68,68,0.25)',
        'glow-green-sm': '0 0 8px rgba(34,197,94,0.8)',
      },
    },
  },
  plugins: [],
};
