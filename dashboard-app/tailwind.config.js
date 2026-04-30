/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0B0C0E',
          elev: '#131418',
          card: '#16181D',
          subtle: '#1B1E25',
        },
        line: {
          DEFAULT: 'rgba(255,255,255,0.08)',
          strong: 'rgba(255,255,255,0.14)',
        },
        ink: {
          DEFAULT: '#EAECEF',
          muted: '#9AA0A6',
          dim: '#5F6368',
        },
        accent: {
          DEFAULT: '#00E6CC',     // teal — primary
          strong: '#00C2AD',
          soft: 'rgba(0,230,204,0.12)',
        },
        success: '#34C759',
        warning: '#F5A524',
        danger: '#FF3B30',
        info: '#A8C7FA',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(0,230,204,0.4), 0 8px 32px rgba(0,230,204,0.15)',
        card: '0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px rgba(0,0,0,0.35)',
      },
      borderRadius: {
        xl2: '14px',
      },
      keyframes: {
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        fadein: { '0%': { opacity: 0, transform: 'translateY(4px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
      },
      animation: {
        shimmer: 'shimmer 2s linear infinite',
        fadein: 'fadein .25s ease-out both',
      },
    },
  },
  plugins: [],
}
