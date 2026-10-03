import './globals.css';
import './emergency.css';
import type { Metadata } from 'next';
import { SiteShell } from '@/components/SiteShell';
import { I18nProvider } from '@/i18n';
export const metadata: Metadata = { title: 'RakshakAI | Investor Safety', description: 'A privacy-first shield for suspicious financial content.' };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en" dir="ltr"><body><I18nProvider><SiteShell>{children}</SiteShell></I18nProvider></body></html>; }
