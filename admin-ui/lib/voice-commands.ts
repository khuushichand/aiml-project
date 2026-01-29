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

/**
 * Parse voice command form inputs into API-ready values.
 * Phrases accept comma or newline separators. Action config accepts JSON.
 */
export const parseVoiceCommandInputs = (
  phrasesInput: string,
  actionConfigInput?: string
): VoiceCommandParseResult => {
  const phrases = phrasesInput
    .split(/[,\n]/)
    .map((phrase) => phrase.trim())
    .filter((phrase) => phrase.length > 0);

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

