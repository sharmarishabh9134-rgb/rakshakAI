'use client';
import { getStoredToken } from '@/lib/session';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import en from '../../locales/en.json';
import hi from '../../locales/hi.json';
import kn from '../../locales/kn.json';
import mr from '../../locales/mr.json';
import te from '../../locales/te.json';
import ml from '../../locales/ml.json';

export const LANGUAGES = {
  en: { nativeName: 'English', dir: 'ltr' }, hi: { nativeName: 'हिन्दी', dir: 'ltr' }, kn: { nativeName: 'ಕನ್ನಡ', dir: 'ltr' },
  ta: { nativeName: 'தமிழ்', dir: 'ltr' }, te: { nativeName: 'తెలుగు', dir: 'ltr' }, mr: { nativeName: 'मराठी', dir: 'ltr' },
  bn: { nativeName: 'বাংলা', dir: 'ltr' }, ml: { nativeName: 'മലയാളം', dir: 'ltr' }, gu: { nativeName: 'ગુજરાતી', dir: 'ltr' }, pa: { nativeName: 'ਪੰਜਾਬੀ', dir: 'ltr' },
} as const;
export const ACTIVE_LANGUAGES = ['en', 'hi', 'kn', 'mr', 'te', 'ml'] as const;
export type Language = keyof typeof LANGUAGES;
export type TranslationKey = keyof typeof en;
type Key = TranslationKey;
const catalogs: Partial<Record<Language, Record<string, string>>> = { en, hi, kn, mr, te, ml };
const Context = createContext<{language: Language; setLanguage: (language: Language) => void; t: (key: Key) => string}>({language:'en',setLanguage:()=>{},t:(key)=>en[key]});
const STORAGE_KEY = 'rakshakai_language';
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function I18nProvider({children}:{children:React.ReactNode}) {
  const [language,setLanguageState] = useState<Language>('en');
  useEffect(() => {
    let initial: Language = 'en';
    try {
      const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('language');
      if (saved && Object.prototype.hasOwnProperty.call(LANGUAGES,saved) && Object.prototype.hasOwnProperty.call(catalogs,saved)) initial = saved as Language;
      const token = getStoredToken();
      if (token) fetch(`${API}/api/users/me`, {headers:{Authorization:`Bearer ${token}`}}).then(async response => {
        if (response.ok) { const user = await response.json(); if (user.preferred_language && Object.prototype.hasOwnProperty.call(catalogs,user.preferred_language)) applyLanguage(user.preferred_language); }
      }).catch(()=>{});
    } catch { /* Storage may be disabled; keep the in-memory default. */ }
    applyLanguage(initial);
  }, []);
  const applyLanguage = useCallback((next: Language) => {
    setLanguageState(next);
    document.documentElement.lang = next;
    document.documentElement.dir = LANGUAGES[next].dir;
    try { localStorage.setItem(STORAGE_KEY,next); localStorage.setItem('language',next); } catch { /* Keep current session preference. */ }
  }, []);
  const setLanguage = useCallback((next: Language) => {
    applyLanguage(next);
    try {
      const token = getStoredToken();
      if (token) fetch(`${API}/api/users/me/language`, {method:'PATCH',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({language:next})}).catch(()=>{});
    } catch { /* Local selection remains available while signed out. */ }
  }, [applyLanguage]);
  const value = useMemo(() => ({language,setLanguage,t:(key:Key) => catalogs[language]?.[key] ?? en[key]}),[language,setLanguage]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useI18n() { return useContext(Context); }
