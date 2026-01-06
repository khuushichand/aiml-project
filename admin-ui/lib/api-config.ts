const API_HOST = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';

export const API_BASE_URL = `${API_HOST.replace(/\/$/, '')}/api/${API_VERSION}`;

export const buildApiUrl = (endpoint: string): string => {
  if (!endpoint) return API_BASE_URL;
  return `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
};
