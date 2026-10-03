import type { Language } from '@/i18n';

const SPEECH_LOCALES: Record<Language, string> = {
  en: 'en-IN', hi: 'hi-IN', kn: 'kn-IN', mr: 'mr-IN', te: 'te-IN', ml: 'ml-IN',
  ta: 'ta-IN', bn: 'bn-IN', gu: 'gu-IN', pa: 'pa-IN',
};

/** Speak only when the browser has a voice for the selected language. */
export function speakInLanguage(text: string, language: Language): boolean {
  if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) return false;
  const locale = SPEECH_LOCALES[language];
  const voices = window.speechSynthesis.getVoices();
  const voice = voices.find(item => item.lang.toLowerCase() === locale.toLowerCase())
    ?? voices.find(item => item.lang.toLowerCase().startsWith(`${language}-`));
  if (!voice) return false;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = voice.lang;
  utterance.voice = voice;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
  return true;
}

export function speechLocale(language: Language): string {
  return SPEECH_LOCALES[language];
}

export function speechUnavailableMessage(language: Language): string {
  const messages: Partial<Record<Language, string>> = {
    mr: 'या डिव्हाइसवर मराठी आवाज उपलब्ध नाही. डिव्हाइसची मराठी भाषा/आवाज सुविधा सुरू करा किंवा मजकूर वाचा.',
    te: 'ఈ పరికరంలో తెలుగు స్వరం అందుబాటులో లేదు. పరికర భాషా సెట్టింగ్‌లలో తెలుగు మాటల సదుపాయాన్ని ప్రారంభించండి లేదా వచనాన్ని చదవండి.',
    ml: 'ഈ ഉപകരണത്തിൽ മലയാള ശബ്ദം ലഭ്യമല്ല. ഉപകരണത്തിന്റെ ഭാഷാ ക്രമീകരണത്തിൽ മലയാളം ശബ്ദം പ്രവർത്തനക്ഷമമാക്കുക, അല്ലെങ്കിൽ എഴുത്ത് വായിക്കുക.',
    hi: 'इस डिवाइस पर हिन्दी आवाज़ उपलब्ध नहीं है। डिवाइस की भाषा सेटिंग में हिन्दी आवाज़ चालू करें या लिखित विवरण पढ़ें।',
    kn: 'ಈ ಸಾಧನದಲ್ಲಿ ಕನ್ನಡ ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ. ಸಾಧನದ ಭಾಷಾ ಸೆಟ್ಟಿಂಗ್‌ಗಳಲ್ಲಿ ಕನ್ನಡ ಧ್ವನಿಯನ್ನು ಸಕ್ರಿಯಗೊಳಿಸಿ ಅಥವಾ ಬರಹವನ್ನು ಓದಿ.',
  };
  return messages[language] ?? 'No voice for this language is available on this device. Enable a matching system voice or read the written explanation.';
}
