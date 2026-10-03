export function getStoredToken() {
  return localStorage.getItem('rakshakai_token') || sessionStorage.getItem('rakshakai_token');
}

export function storeSessionToken(token: string, remember = true) {
  localStorage.removeItem('rakshakai_token');
  sessionStorage.removeItem('rakshakai_token');
  (remember ? localStorage : sessionStorage).setItem('rakshakai_token', token);
  window.dispatchEvent(new Event('rakshakai-session-change'));
}

export function clearStoredToken() {
  localStorage.removeItem('rakshakai_token');
  sessionStorage.removeItem('rakshakai_token');
  window.dispatchEvent(new Event('rakshakai-session-change'));
}

export function clearExpiredAnalysisSession(data: { session_valid?: boolean }) {
  if (data.session_valid === false && getStoredToken()) clearStoredToken();
}
