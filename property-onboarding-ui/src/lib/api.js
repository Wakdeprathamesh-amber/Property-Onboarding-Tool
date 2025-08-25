export const API_BASE_URL = (import.meta?.env?.VITE_API_BASE_URL || '').replace(/\/$/, '');

export function apiUrl(path) {
  if (!path) return API_BASE_URL || '';
  const cleanedPath = path.startsWith('/') ? path : `/${path}`;
  return API_BASE_URL ? `${API_BASE_URL}${cleanedPath}` : cleanedPath;
}

export async function fetchJson(input, init) {
  const response = await fetch(input, init);
  const contentType = response.headers.get('content-type') || '';
  let raw = '';
  try {
    raw = await response.text();
  } catch (_) {
    raw = '';
  }
  let data = null;
  if (raw && contentType.includes('application/json')) {
    try { data = JSON.parse(raw); } catch (_) { /* ignore parse error */ }
  }
  if (!response.ok) {
    const message = (data && (data.error || data.message)) || raw || `HTTP ${response.status}`;
    console.error('API error', { url: typeof input === 'string' ? input : '', status: response.status, contentType, raw });
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  // If empty body, return an empty object to avoid JSON parse errors in callers
  return data ?? (raw ? (() => { try { return JSON.parse(raw); } catch { return { raw }; } })() : {});
}
