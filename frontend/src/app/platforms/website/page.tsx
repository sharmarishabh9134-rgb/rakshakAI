'use client';
import { useState } from 'react';
import { ExternalLink, Globe2, LoaderCircle } from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
type CheckResult = {
  domain_observations?: { url?: string; checks?: { https?: boolean } };
  official_website: string;
  platform_name: string;
  risk_indicators: string[];
  checks_performed: string[];
  disclaimer: string;
};

export default function WebsitePage() {
  const [url, setUrl] = useState('');
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function check() {
    setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch(`${API}/api/platforms/verify-url`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to inspect URL.');
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to inspect URL.');
    } finally { setBusy(false); }
  }

  return <main className="mx-auto max-w-[900px] px-5 py-10 lg:px-8">
    <div className="eyebrow">Website verifier</div>
    <h1 className="mt-2 text-3xl font-extrabold">Verify a Website</h1>
    <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Analyze URL structure and compare against the directory. The system never fetches the submitted website or follows redirects; this prevents server-side request forgery and avoids exposing private networks.</p>
    <section className="surface-card mt-6">
      <label htmlFor="website" className="text-sm font-bold">Website URL</label>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row">
        <input id="website" className="input !my-0 flex-1" value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && url.trim()) void check(); }} placeholder="https://example.com" />
        <button className="btn-primary" onClick={() => void check()} disabled={busy || !url.trim()}>{busy ? <LoaderCircle size={16} className="animate-spin" /> : <Globe2 size={16} />}Check URL</button>
      </div>
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    </section>
    {result && <section className="surface-card mt-5">
      <h2 className="text-xl font-extrabold">Security observations</h2>
      <p className="mt-2 break-all text-sm">URL: {result.domain_observations?.url || url}</p>
      <p className="mt-2 text-sm"><b>HTTPS:</b> {result.domain_observations?.checks?.https ? 'Yes' : 'No'}</p>
      <p className="mt-2 text-sm"><b>Official domain match:</b> {result.official_website ? <a className="text-[var(--accent)] underline" href={result.official_website} target="_blank" rel="noopener noreferrer">{result.platform_name}<ExternalLink size={12} className="ml-1 inline" /></a> : 'No directory match'}</p>
      <h3 className="mt-5 font-bold">Potential impersonation indicators</h3>
      <ul className="list-disc pl-5 text-sm leading-6">{(result.risk_indicators.length ? result.risk_indicators : ['No configured indicators found. This does not verify the site.']).map(x => <li key={x}>{x}</li>)}</ul>
      <h3 className="mt-5 font-bold">Checks performed</h3>
      <ul className="list-disc pl-5 text-sm leading-6">{result.checks_performed.map(x => <li key={x}>{x}</li>)}</ul>
      <p className="mt-4 text-sm text-[var(--muted)]">Checks unavailable: redirects, current site content, domain ownership and live registry data. No request was sent to the entered host.</p>
      <p className="mt-4 text-xs leading-5 text-[var(--muted)]">{result.disclaimer}</p>
    </section>}
  </main>;
}
