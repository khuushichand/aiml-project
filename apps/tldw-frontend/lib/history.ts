export interface RequestHistoryItem {
  id: string;
  method: string;
  url: string;
  baseURL?: string;
  status?: number;
  ok?: boolean;
  duration_ms?: number;
  timestamp: string;
  requestHeaders?: Record<string, string>;
  requestBody?: unknown;
  responseBody?: unknown;
  errorMessage?: string;
}

const KEY = 'tldw-request-history';
const MAX = 200;

export function addRequestHistory(item: RequestHistoryItem) {
  try {
    const raw = localStorage.getItem(KEY);
    const arr: RequestHistoryItem[] = raw ? JSON.parse(raw) : [];
    const next = [item, ...arr].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // ignore
  }
}

export function getRequestHistory(): RequestHistoryItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const arr: RequestHistoryItem[] = JSON.parse(raw);
    return arr;
  } catch {
    return [];
  }
}

export function clearRequestHistory() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // localStorage may be unavailable
  }
}

