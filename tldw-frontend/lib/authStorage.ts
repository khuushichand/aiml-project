let runtimeApiKey: string | null = null;
let runtimeApiBearer: string | null = null;

const normalizeValue = (value?: string | null): string | null => {
  const raw = (value ?? '').trim();
  return raw ? raw : null;
};

export const setRuntimeApiKey = (value?: string | null): void => {
  runtimeApiKey = normalizeValue(value);
};

export const setRuntimeApiBearer = (value?: string | null): void => {
  runtimeApiBearer = normalizeValue(value);
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
