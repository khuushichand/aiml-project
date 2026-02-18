export type DeprecatedModelMatcher =
  | { type: 'exact'; value: string }
  | { type: 'prefix'; value: string };

export interface DeprecatedModelNotice {
  id: string;
  matcher: DeprecatedModelMatcher;
  replacement: string;
  note?: string;
}

const normalizeModelName = (value: string) => value.trim().toLowerCase();

const matchesDeprecatedModel = (modelName: string, matcher: DeprecatedModelMatcher) => {
  const normalizedModel = normalizeModelName(modelName);
  const normalizedValue = normalizeModelName(matcher.value);
  if (!normalizedModel || !normalizedValue) return false;
  if (matcher.type === 'exact') return normalizedModel === normalizedValue;
  return normalizedModel.startsWith(normalizedValue);
};

export const DEPRECATED_MODEL_NOTICES: readonly DeprecatedModelNotice[] = Object.freeze([
  {
    id: 'openai-gpt-3-5-turbo',
    matcher: { type: 'prefix', value: 'gpt-3.5-turbo' },
    replacement: 'gpt-4.1-mini',
    note: 'GPT-3.5 family should be migrated to GPT-4.1 or newer.',
  },
  {
    id: 'openai-text-davinci-003',
    matcher: { type: 'exact', value: 'text-davinci-003' },
    replacement: 'gpt-4.1-mini',
    note: 'Legacy completion models should migrate to chat-capable models.',
  },
  {
    id: 'anthropic-claude-2',
    matcher: { type: 'prefix', value: 'claude-2' },
    replacement: 'claude-sonnet-4-20250514',
    note: 'Claude 2 family is superseded by Claude 3.5/4 models.',
  },
  {
    id: 'anthropic-claude-instant-1',
    matcher: { type: 'prefix', value: 'claude-instant-1' },
    replacement: 'claude-haiku-4-20250514',
    note: 'Claude Instant models should move to Haiku for low-latency workloads.',
  },
]);

export const getDeprecatedModelNotice = (modelName: string): DeprecatedModelNotice | null => {
  for (const notice of DEPRECATED_MODEL_NOTICES) {
    if (matchesDeprecatedModel(modelName, notice.matcher)) {
      return notice;
    }
  }
  return null;
};

export const isModelDeprecated = (modelName: string) => getDeprecatedModelNotice(modelName) !== null;
