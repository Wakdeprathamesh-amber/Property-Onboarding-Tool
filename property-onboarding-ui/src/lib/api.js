export const API_BASE_URL = (import.meta?.env?.VITE_API_BASE_URL || '').replace(/\/$/, '');

export function apiUrl(path) {
  if (!path) return API_BASE_URL || '';
  const cleanedPath = path.startsWith('/') ? path : `/${path}`;
  return API_BASE_URL ? `${API_BASE_URL}${cleanedPath}` : cleanedPath;
}
