/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Page & surface
        surface: '#F4F6FB',
        card:    '#FFFFFF',
        border:  '#E4E9F5',
        // Text
        ink:     '#1A1D2E',
        sub:     '#64748B',
        muted:   '#A0AABF',
        // Primary (indigo)
        primary: { DEFAULT: '#6366F1', light: '#EEF2FF', dark: '#4F46E5' },
        // Stage colors (vivid on white)
        accumulation: { DEFAULT: '#2563EB', bg: '#EFF6FF', text: '#1D4ED8', border: '#BFDBFE' },
        markup:       { DEFAULT: '#16A34A', bg: '#F0FDF4', text: '#15803D', border: '#BBF7D0' },
        distribution: { DEFAULT: '#D97706', bg: '#FFFBEB', text: '#B45309', border: '#FDE68A' },
        markdown:     { DEFAULT: '#DC2626', bg: '#FEF2F2', text: '#B91C1C', border: '#FECACA' },
      },
      boxShadow: {
        card: '0 1px 4px 0 rgba(99,102,241,0.06), 0 4px 16px 0 rgba(99,102,241,0.04)',
        'card-hover': '0 4px 16px 0 rgba(99,102,241,0.12)',
      },
      borderRadius: { xl: '14px', '2xl': '18px' },
    },
  },
  plugins: [],
}
