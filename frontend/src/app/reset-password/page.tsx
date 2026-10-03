import Link from 'next/link';
import {LockKeyhole} from 'lucide-react';
import {AuthFrame} from '@/components/AuthFrame';
export default function ResetPassword(){return <AuthFrame eyebrow="Account recovery" title="A reset link is required" subtitle="For account security, a password change needs a valid, expiring reset token."><div className="mt-8 rounded-xl border border-[var(--line)] bg-[var(--surface)] p-5"><LockKeyhole className="text-[var(--accent)]" size={22}/><p className="mt-4 text-sm leading-6 text-[var(--muted)]">Password reset delivery and token verification are not configured in this demo. No password has been changed.</p><Link className="btn-primary mt-5" href="/login">Return to sign in</Link></div></AuthFrame>}
