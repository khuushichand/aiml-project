let runtimeApiKey: string | null = null;
let runtimeApiBearer: string | null = null;

const normalizeValue = (value?: string | null): string | null => {
  const raw = (value ?? '').trim();
  return raw ? raw : null;
};

const normalizeApiKeyValue = (value?: string | null): string | null => {
  const normalized = normalizeValue(value);
  if (!normalized) return null;
  if (/\s/.test(normalized)) {
    console.warn('Runtime API key contains whitespace; ignoring value.');
    return null;
  }
  return normalized;
};

const normalizeBearerValue = (value?: string | null): string | null => {
  const normalized = normalizeValue(value);
  if (!normalized) return null;
  const stripped = normalized.replace(/^Bearer\s+/i, '').trim();
  if (!stripped) return null;
  if (/\s/.test(stripped)) {
    console.warn('Runtime API bearer contains whitespace; ignoring value.');
    return null;
  }
  return stripped;
};

export const setRuntimeApiKey = (value?: string | null): void => {
  runtimeApiKey = normalizeApiKeyValue(value);
};

export const setRuntimeApiBearer = (value?: string | null): void => {
  runtimeApiBearer = normalizeBearerValue(value);
};

export const getRuntimeApiKey = (): string | null => runtimeApiKey;
export const getRuntimeApiBearer = (): string | null => runtimeApiBearer;

export const getApiKey = (): string | null => {
  return runtimeApiKey || process.env.NEXT_PUBLIC_X_API_KEY || null;
};

export const getApiBearer = (): string | null => {
  return runtimeApiBearer || process.env.NEXT_PUBLIC_API_BEARER || null;
};

export const clearRuntimeAuth = (): void => {
  runtimeApiKey = null;
  runtimeApiBearer = null;
};
