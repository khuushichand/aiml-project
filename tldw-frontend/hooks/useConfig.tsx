import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import api, { getApiBaseUrl } from '@/lib/api';

type Theme = 'light' | 'dark' | 'system';

interface AppConfig {
  apiBaseHost: string; // e.g., http://127.0.0.1:8000
  apiVersion: string; // e.g., v1
  xApiKey?: string;
  apiBearer?: string;
  theme: Theme;
  csrfToken?: string | null;
}

interface ConfigContextType {
  config: AppConfig;
  setApiBaseHost: (host: string) => void;
  setApiVersion: (version: string) => void;
  setXApiKey: (key: string) => void;
  setApiBearer: (bearer: string) => void;
  setTheme: (theme: Theme) => void;
  reloadBootstrapConfig: () => Promise<void>;
}

const DEFAULT_HOST = (typeof window !== 'undefined' && window.location?.origin) || (process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000');

const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

function computeBaseURL(host: string, version: string) {
  const cleanHost = host.replace(/\/$/, '');
  return `${cleanHost}/api/${version || 'v1'}`;
}

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.classList.remove('theme-light', 'theme-dark');
  if (theme === 'light') root.classList.add('theme-light');
  if (theme === 'dark') root.classList.add('theme-dark');
}

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(() => {
    if (typeof window === 'undefined') {
      return {
        apiBaseHost: DEFAULT_HOST,
        apiVersion: process.env.NEXT_PUBLIC_API_VERSION || 'v1',
        xApiKey: process.env.NEXT_PUBLIC_X_API_KEY,
        apiBearer: process.env.NEXT_PUBLIC_API_BEARER,
        theme: 'system',
        csrfToken: null,
      };
    }
    const storedHost = localStorage.getItem('tldw-api-host') || DEFAULT_HOST;
    const storedVersion = localStorage.getItem('tldw-api-version') || (process.env.NEXT_PUBLIC_API_VERSION || 'v1');
    const storedKey = localStorage.getItem('x_api_key') || process.env.NEXT_PUBLIC_X_API_KEY || '';
    const storedBearer = localStorage.getItem('tldw-api-bearer') || process.env.NEXT_PUBLIC_API_BEARER || '';
    const storedTheme = (localStorage.getItem('tldw-theme') as Theme) || 'system';
    return { apiBaseHost: storedHost, apiVersion: storedVersion, xApiKey: storedKey || undefined, apiBearer: storedBearer || undefined, theme: storedTheme, csrfToken: null };
  });

  // Initialize axios baseURL and theme on mount
  useEffect(() => {
    const current = computeBaseURL(config.apiBaseHost, config.apiVersion);
    if (getApiBaseUrl() !== current) {
      api.defaults.baseURL = current;
    }
    applyTheme(config.theme);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist config changes and update axios baseURL
  useEffect(() => {
    if (typeof window === 'undefined') return;
    // Persist
    try {
      localStorage.setItem('tldw-api-host', config.apiBaseHost);
      localStorage.setItem('tldw-api-version', config.apiVersion);
      if (config.xApiKey) localStorage.setItem('x_api_key', config.xApiKey); else localStorage.removeItem('x_api_key');
      if (config.apiBearer) localStorage.setItem('tldw-api-bearer', config.apiBearer); else localStorage.removeItem('tldw-api-bearer');
      localStorage.setItem('tldw-theme', config.theme);
    } catch {}
    // Apply axios base URL
    const nextBase = computeBaseURL(config.apiBaseHost, config.apiVersion);
    api.defaults.baseURL = nextBase;
    // Apply theme
    applyTheme(config.theme);
  }, [config]);

  const setApiBaseHost = (host: string) => setConfig((c) => ({ ...c, apiBaseHost: host }));
  const setApiVersion = (ver: string) => setConfig((c) => ({ ...c, apiVersion: ver || 'v1' }));
  const setXApiKey = (key: string) => setConfig((c) => ({ ...c, xApiKey: key || undefined }));
  const setApiBearer = (bearer: string) => setConfig((c) => ({ ...c, apiBearer: bearer || undefined }));
  const setTheme = (t: Theme) => setConfig((c) => ({ ...c, theme: t }));

  const reloadBootstrapConfig = async () => {
    if (typeof window === 'undefined') return;
    try {
      const resp = await fetch('/webui/config.json', { credentials: 'include' });
      if (!resp.ok) return;
      const json = await resp.json();
      const host = json?.base_url || json?.api_base_url || config.apiBaseHost;
      const version = json?.api_version || config.apiVersion || 'v1';
      const key = json?.x_api_key || config.xApiKey;
      const bearer = json?.api_bearer || config.apiBearer;
      setConfig((c) => ({ ...c, apiBaseHost: host, apiVersion: version, xApiKey: key, apiBearer: bearer }));
    } catch {
      // ignore
    }
  };

  const value = useMemo(
    () => ({
      config,
      setApiBaseHost,
      setApiVersion,
      setXApiKey,
      setApiBearer,
      setTheme,
      reloadBootstrapConfig,
    }),
    [config]
  );

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useConfig() {
  const ctx = useContext(ConfigContext);
  if (!ctx) throw new Error('useConfig must be used within ConfigProvider');
  return ctx;
}
