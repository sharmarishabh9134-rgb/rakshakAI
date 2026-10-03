import type { Config } from 'tailwindcss';
const config: Config = { content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'], theme: { extend: { colors: { ink: '#172b4d', mint: '#c8f5df', teal: '#0c806c' } } }, plugins: [] };
export default config;
