import { buildApiUrl } from '@/lib/api-config';
import { buildAuthHeaders } from '@/lib/http';

export type DownloadExportOptions = {
  endpoint: string;
  params?: Record<string, string>;
  fallbackFilename: string;
  timeoutMs?: number;
  defaultError?: string;
};

const splitDispositionParts = (value: string) => {
  const parts: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < value.length; i += 1) {
    const char = value[i];
    if (char === '"' && (i === 0 || value[i - 1] !== '\\')) {
      inQuotes = !inQuotes;
    }
    if (char === ';' && !inQuotes) {
      const trimmed = current.trim();
      if (trimmed) {
        parts.push(trimmed);
      }
      current = '';
      continue;
    }
    current += char;
  }
  const trimmed = current.trim();
  if (trimmed) {
    parts.push(trimmed);
  }
  return parts;
};

const unquoteHeaderValue = (value: string) => {
  if (value.startsWith('"') && value.endsWith('"')) {
    return value.slice(1, -1).replace(/\\(.)/g, '$1');
  }
  return value;
};

const decode5987Value = (value: string) => {
  const raw = unquoteHeaderValue(value);
  const match = raw.match(/^([^']*)'[^']*'(.*)$/);
  const encoded = match ? match[2] : raw;
  try {
    return decodeURIComponent(encoded);
  } catch {
    return encoded;
  }
};

export const getFilenameFromDisposition = (disposition: string | null): string | null => {
  if (!disposition) return null;

  const parts = splitDispositionParts(disposition);
  const params: Record<string, string> = {};
  for (const part of parts.slice(1)) {
    const eqIndex = part.indexOf('=');
    if (eqIndex === -1) continue;
    const key = part.slice(0, eqIndex).trim().toLowerCase();
    if (!key) continue;
    const rawValue = part.slice(eqIndex + 1).trim();
    if (!rawValue) continue;
    params[key] = unquoteHeaderValue(rawValue);
  }

  if (params['filename*']) {
    const decoded = decode5987Value(params['filename*']);
    if (decoded) return decoded;
  }

  return params.filename || null;
};

export const triggerBlobDownload = (blob: Blob, filename: string): void => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const downloadExportFile = async ({
  endpoint,
  params = {},
  fallbackFilename,
  timeoutMs,
  defaultError = 'Failed to download export',
}: DownloadExportOptions): Promise<void> => {
  const controller = timeoutMs ? new AbortController() : null;
  const timeoutId = timeoutMs
    ? window.setTimeout(() => controller?.abort(), timeoutMs)
    : undefined;

  const query = new URLSearchParams(params).toString();

  try {
    const response = await fetch(buildApiUrl(`${endpoint}${query ? `?${query}` : ''}`), {
      headers: buildAuthHeaders('GET'),
      credentials: 'include',
      signal: controller?.signal,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || defaultError);
    }

    const blob = await response.blob();
    const filename = getFilenameFromDisposition(response.headers.get('content-disposition')) || fallbackFilename;
    triggerBlobDownload(blob, filename);
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Download aborted: timeout');
    }
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Download aborted: timeout');
    }
    throw err;
  } finally {
    if (timeoutId !== undefined) {
      window.clearTimeout(timeoutId);
    }
  }
};
