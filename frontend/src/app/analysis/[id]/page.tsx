'use client';
import { getStoredToken } from '@/lib/session';
import {useParams} from 'next/navigation';
import {useEffect,useState} from 'react';
export default function AnalysisDetails(){const {id}=useParams<{id:string}>();const [row,setRow]=useState<any>();useEffect(()=>{const t=getStoredToken();if(t)fetch(`${process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'}/api/analysis/${id}`,{headers:{Authorization:`Bearer ${t}`}}).then(r=>r.ok?r.json():null).then(setRow)},[id]);return <><div className="eyebrow">Analysis record</div><h1>Analysis details</h1><div className="card">{row?<><span className={`risk ${row.risk}`}>{row.risk}</span><p>{row.summary}</p><p className="muted">{new Date(row.created_at).toLocaleString()}</p></>:<p>Sign in to view this record. It may also have been deleted.</p>}</div></>}
