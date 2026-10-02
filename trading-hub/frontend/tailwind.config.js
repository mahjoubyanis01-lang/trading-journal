/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0b0f17',
        panel: '#121824',
        panel2: '#0e1420',
        edge: '#1f2a3a',
        // state colors
        op: '#22c55e',       // green  = operational
        attn: '#f59e0b',     // orange = attention
        err: '#ef4444',      // red    = error
        idle: '#64748b',     // gray   = inactive/disconnected
        info: '#3b82f6',     // blue   = pending/info
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
    },
  },
  plugins: [],
}
