/** @type {import('next').NextConfig} */
const development = process.env.NODE_ENV !== 'production';
const requestedApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const requestedApiHost = requestedApiUrl ? new URL(requestedApiUrl).hostname.toLowerCase() : '';
const requestedApiIsLocal = ['localhost', 'localhost.', '127.0.0.1', '0.0.0.0', '[::1]'].includes(requestedApiHost);
const configuredApiUrl = requestedApiUrl && (development || !requestedApiIsLocal)
  ? requestedApiUrl
  : development ? 'http://localhost:8000' : 'https://rakshakai-backend-6c96.getvoroa.com';
const apiBaseUrl = configuredApiUrl.replace(/\/+$/, '').replace(/\/api$/i, '');
const apiOrigin = new URL(apiBaseUrl).origin;
const nextConfig = {
  env: { NEXT_PUBLIC_API_URL: apiBaseUrl },
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
