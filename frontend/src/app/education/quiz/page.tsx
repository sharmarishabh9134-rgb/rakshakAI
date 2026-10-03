'use client';
import Link from 'next/link';
import {useEffect,useState} from 'react';
import {ArrowRight,BookOpen} from 'lucide-react';
const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000';
export default function Quiz(){const [lessons,setLessons]=useState<any[]>([]);useEffect(()=>{fetch(`${API}/api/education`).then(r=>r.json()).then(setLessons).catch(()=>{})},[]);return <main className="mx-auto max-w-3xl px-5 py-10 lg:py-14"><div className="eyebrow">Knowledge checks</div><h1 className="mt-2 text-3xl font-extrabold">Choose a lesson quiz</h1><p className="mt-3 text-sm leading-6 text-[var(--muted)]">Each quiz has three questions and saves your score when signed in.</p><div className="mt-6 grid gap-3">{lessons.map(x=><Link className="feature-card flex items-center justify-between" key={x.slug} href={`/education/lesson/${x.slug}`}><span className="flex items-center gap-3"><BookOpen className="text-[var(--accent)]" size={18}/><b>{x.title}</b></span><ArrowRight className="text-[var(--accent)]" size={16}/></Link>)}</div></main>}
