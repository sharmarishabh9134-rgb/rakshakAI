'use client';
import { FormEvent, useEffect, useState } from 'react';
import { Bot, LoaderCircle, Send, Sparkles } from 'lucide-react';
import { getStoredToken } from '@/lib/session';
import { useI18n, type Language } from '@/i18n';

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000';
const languages:{code:Language;label:string}[]=[
  {code:'en',label:'English'},{code:'hi',label:'हिन्दी'},{code:'kn',label:'ಕನ್ನಡ'},
  {code:'mr',label:'मराठी'},{code:'te',label:'తెలుగు'},{code:'ml',label:'മലയാളം'},
  {code:'ta',label:'தமிழ்'},{code:'bn',label:'বাংলা'},{code:'gu',label:'ગુજરાતી'},{code:'pa',label:'ਪੰਜਾਬੀ'},
];
type Turn={role:'user'|'assistant';content:string};

export default function EnquiryAssistant(){
  const {language}=useI18n();
  const [replyLanguage,setReplyLanguage]=useState<Language>(language);
  const [question,setQuestion]=useState('');
  const [turns,setTurns]=useState<Turn[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>setReplyLanguage(language),[language]);

  async function send(event:FormEvent){
    event.preventDefault();const message=question.trim();if(!message||busy)return;
    setQuestion('');setError('');setBusy(true);setTurns(previous=>[...previous,{role:'user',content:message}]);
    try{
      const token=getStoredToken();
      const response=await fetch(`${API}/api/assistant/chat`,{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify({message,language:replyLanguage,history:turns.slice(-10)})});
      const data=await response.json();
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'The assistant could not answer. Please try again.');
      setTurns(previous=>[...previous,{role:'assistant',content:data.answer}]);
    }catch(e){setError(e instanceof Error?e.message:'The assistant could not answer. Please try again.');}
    finally{setBusy(false);}
  }

  return <section className="surface-card mt-8" aria-labelledby="assistant-title">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="eyebrow flex items-center gap-2"><Sparkles size={14}/> RakshakAI assistant</div><h2 id="assistant-title" className="mt-2 text-xl font-extrabold">Ask an enquiry in your language</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--muted)]">Ask about suspicious messages, verification steps, investor rights, or how to use RakshakAI. Replies follow your selected language.</p></div><label className="grid gap-1 text-xs font-bold">Reply language<select aria-label="Assistant reply language" className="input !my-0 min-w-40" value={replyLanguage} onChange={e=>setReplyLanguage(e.target.value as Language)}>{languages.map(x=><option key={x.code} value={x.code}>{x.label}</option>)}</select></label></div>
    <div aria-live="polite" aria-relevant="additions" className="mt-5 max-h-[420px] space-y-3 overflow-y-auto rounded-xl bg-[var(--bg)] p-4">
      {turns.length===0?<div className="flex gap-3 text-sm leading-6 text-[var(--muted)]"><Bot className="mt-1 shrink-0 text-[var(--accent)]" size={18}/><p>Namaste! Ask a question to get started. Don’t share OTPs, PINs, passwords, or bank account details.</p></div>:turns.map((turn,index)=><div key={`${index}-${turn.role}`} className={`flex ${turn.role==='user'?'justify-end':'justify-start'}`}><p className={`max-w-[90%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${turn.role==='user'?'bg-[var(--accent)] text-white':'border border-[var(--line)] bg-[var(--surface)]'}`}>{turn.content}</p></div>)}
      {busy&&<div role="status" className="flex items-center gap-2 text-xs text-[var(--muted)]"><LoaderCircle size={14} className="animate-spin"/>Thinking…</div>}
    </div>
    {error&&<p role="alert" className="mt-3 rounded-lg bg-[#fff0ee] p-3 text-sm text-[#a23e35]">{error}</p>}
    <form onSubmit={send} className="mt-4 flex flex-col gap-3 sm:flex-row"><label className="sr-only" htmlFor="assistant-question">Your question</label><textarea id="assistant-question" className="input !my-0 min-h-14 flex-1 resize-y" value={question} onChange={e=>setQuestion(e.target.value)} maxLength={2000} rows={2} placeholder="What would you like help with?"/><button className="btn-primary self-end sm:self-stretch" type="submit" disabled={busy||!question.trim()}>{busy?<LoaderCircle size={16} className="animate-spin"/>:<Send size={16}/>}Ask</button></form>
    <p className="mt-3 text-[11px] leading-5 text-[var(--muted)]">Gemini AI answers are general information, not personalized financial, legal, or tax advice. Conversation is sent to Google Gemini to generate replies and is not saved to RakshakAI history. Never include sensitive credentials.</p>
  </section>;
}
