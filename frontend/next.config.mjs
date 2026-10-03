/** @type {import('next').NextConfig} */
const apiOrigin = new URL(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').origin;
const development = process.env.NODE_ENV !== 'production';
const nextConfig = {
  distDir: process.env.NEXT_DIST_DIR || '.next',
  reactStrictMode: true,
  async headers() {
    const scriptPolicy = development ? "'self' 'unsafe-inline' 'unsafe-eval'" : "'self' 'unsafe-inline'";
    const connectPolicy = ["'self'", apiOrigin, ...(development ? ['ws://localhost:3000','ws://127.0.0.1:3000'] : [])].join(' ');
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'Referrer-Policy', value: 'no-referrer' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(self), geolocation=()' },
        { key: 'Content-Security-Policy', value: `default-src 'self'; script-src ${scriptPolicy}; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src ${connectPolicy}; object-src 'none'; base-uri 'self'; frame-ancestors 'none'` },
      ],
    }];
  },
};
export default nextConfig;
