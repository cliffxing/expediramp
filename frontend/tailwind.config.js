/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ramp: {
          bg: '#FAFAF8',
          surface: '#FFFFFF',
          'surface-alt': '#F5F5F0',
          border: '#E8E8E0',
          'border-strong': '#D4D4C8',
          text: '#1A1A18',
          'text-secondary': '#6B6B63',
          'text-tertiary': '#9C9C91',
          accent: '#1A1A18',
          'accent-hover': '#333330',
          green: '#1B7A4A',
          'green-light': '#E8F5EE',
          red: '#C4362C',
          'red-light': '#FDECEA',
          amber: '#B25E09',
          'amber-light': '#FFF3E0',
          blue: '#2563EB',
          'blue-light': '#EFF6FF',
        },
      },
      fontFamily: {
        sans: ['"Instrument Sans"', '"SF Pro Display"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      borderRadius: {
        'ramp': '10px',
        'ramp-sm': '6px',
        'ramp-lg': '14px',
      },
      boxShadow: {
        'ramp': '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)',
        'ramp-md': '0 4px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)',
        'ramp-lg': '0 8px 30px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04)',
        'ramp-focus': '0 0 0 2px #1A1A18',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.16,1,0.3,1)',
        'pulse-dot': 'pulseDot 1.4s ease-in-out infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        pulseDot: {
          '0%, 80%, 100%': { opacity: '0.3', transform: 'scale(0.8)' },
          '40%': { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};