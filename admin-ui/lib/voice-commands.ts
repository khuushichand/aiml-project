export type VoiceCommandParseResult =
  | {
      ok: true;
      phrases: string[];
      actionConfig: unknown;
    }
  | {
      ok: false;
      error: string;
    };

const INVALID_JSON_ERROR = 'Invalid JSON in action config';
const DEFAULT_MATCH_THRESHOLD = 0.6;

export interface VoiceCommandMatchResult {
  matched: boolean;
  confidence: number;
  bestPhrase: string | null;
  threshold: number;
}

const normalizeForMatching = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const tokenize = (value: string): string[] =>
  value
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token.length > 0);

const levenshteinDistance = (source: string, target: string): number => {
  if (source === target) return 0;
  if (source.length === 0) return target.length;
  if (target.length === 0) return source.length;

  const previous = Array.from({ length: target.length + 1 }, (_, index) => index);
  for (let i = 1; i <= source.length; i += 1) {
    let diagonal = previous[0];
    previous[0] = i;
    for (let j = 1; j <= target.length; j += 1) {
      const current = previous[j];
      const cost = source[i - 1] === target[j - 1] ? 0 : 1;
      previous[j] = Math.min(
        previous[j] + 1,
        previous[j - 1] + 1,
        diagonal + cost
      );
      diagonal = current;
    }
  }
  return previous[target.length];
};

const clampScore = (value: number): number => Math.min(1, Math.max(0, value));

export const parseVoiceCommandPhrases = (phrasesInput: string): string[] =>
  phrasesInput
    .split(/[,\n]/)
    .map((phrase) => phrase.trim())
    .filter((phrase) => phrase.length > 0);

export const scoreVoiceCommandPhraseMatch = (sampleText: string, phrase: string): number => {
  const normalizedSample = normalizeForMatching(sampleText);
  const normalizedPhrase = normalizeForMatching(phrase);
  if (!normalizedSample || !normalizedPhrase) return 0;
  if (normalizedSample === normalizedPhrase) return 1;

  const sampleTokens = new Set(tokenize(normalizedSample));
  const phraseTokens = new Set(tokenize(normalizedPhrase));
  const intersectionCount = Array.from(sampleTokens).filter((token) => phraseTokens.has(token)).length;
  const unionCount = new Set([...sampleTokens, ...phraseTokens]).size || 1;
  const overlapScore = intersectionCount / Math.max(1, Math.min(sampleTokens.size, phraseTokens.size));
  const jaccardScore = intersectionCount / unionCount;

  const maxLen = Math.max(normalizedSample.length, normalizedPhrase.length);
  const distance = levenshteinDistance(normalizedSample, normalizedPhrase);
  const editSimilarity = 1 - (distance / maxLen);

  const includesMatch = normalizedSample.includes(normalizedPhrase) || normalizedPhrase.includes(normalizedSample);
  const containsScore = includesMatch
    ? 0.72 + (0.28 * (Math.min(normalizedSample.length, normalizedPhrase.length) / maxLen))
    : 0;

  const compositeScore = (0.45 * editSimilarity) + (0.35 * overlapScore) + (0.20 * jaccardScore);
  return clampScore(Math.max(compositeScore, containsScore));
};

export const testVoiceCommandPhraseMatch = (
  sampleText: string,
  phrases: string[],
  threshold: number = DEFAULT_MATCH_THRESHOLD
): VoiceCommandMatchResult => {
  if (!sampleText.trim() || phrases.length === 0) {
    return {
      matched: false,
      confidence: 0,
      bestPhrase: null,
      threshold,
    };
  }

  let bestPhrase: string | null = null;
  let bestScore = 0;
  phrases.forEach((phrase) => {
    const score = scoreVoiceCommandPhraseMatch(sampleText, phrase);
    if (score > bestScore) {
      bestScore = score;
      bestPhrase = phrase;
    }
  });

  return {
    matched: bestScore >= threshold,
    confidence: clampScore(bestScore),
    bestPhrase,
    threshold,
  };
};

/**
 * Parse voice command form inputs into API-ready values.
 * Phrases accept comma or newline separators. Action config accepts JSON.
 */
export const parseVoiceCommandInputs = (
  phrasesInput: string,
  actionConfigInput?: string
): VoiceCommandParseResult => {
  const phrases = parseVoiceCommandPhrases(phrasesInput);

  if (!actionConfigInput || actionConfigInput.trim().length === 0) {
    return { ok: true, phrases, actionConfig: {} };
  }

  try {
    const parsedConfig = JSON.parse(actionConfigInput);
    return { ok: true, phrases, actionConfig: parsedConfig };
  } catch {
    return { ok: false, error: INVALID_JSON_ERROR };
  }
};
