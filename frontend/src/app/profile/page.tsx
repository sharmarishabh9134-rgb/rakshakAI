'use client';
import { getStoredToken } from '@/lib/session';
import {useEffect,useState} from 'react';
export default function Profile(){const [u,setU]=useState<any>();useEffect(()=>{const t=getStoredToken();if(t)fetch(`${process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'}/api/users/me`,{headers:{Authorization:`Bearer ${t}`}}).then(r=>r.ok?r.json():null).then(setU)},[]);return <><div className="eyebrow">Your account</div><h1>Profile</h1><div className="card">{u?<><p>Name: {u.name}</p><p>Email: {u.email}</p><p>Role: {u.role}</p></>:<p>Sign in to view your profile.</p>}</div></>}
