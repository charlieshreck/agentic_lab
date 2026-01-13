import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'kernow-blue': '#0066cc',
        'kernow-dark': '#1a1a2e',
      },
    },
  },
  plugins: [],
};

export default config;
