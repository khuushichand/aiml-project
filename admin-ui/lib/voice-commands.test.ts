import { describe, expect, it } from 'vitest';
import {
  parseVoiceCommandInputs,
  parseVoiceCommandPhrases,
  scoreVoiceCommandPhraseMatch,
  testVoiceCommandPhraseMatch,
} from './voice-commands';

describe('voice-commands', () => {
  it('parses trigger phrases from comma and newline separated input', () => {
    expect(parseVoiceCommandPhrases('search for, find\nlook up')).toEqual([
      'search for',
      'find',
      'look up',
    ]);
  });

  it('returns parse error for invalid action config json', () => {
    const result = parseVoiceCommandInputs('search', '{bad-json');
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBe('Invalid JSON in action config');
    }
  });

  it('scores exact phrase matches at full confidence', () => {
    const score = scoreVoiceCommandPhraseMatch('search for recent invoices', 'search for recent invoices');
    expect(score).toBe(1);
  });

  it('matches minor typo variations with high confidence', () => {
    const result = testVoiceCommandPhraseMatch(
      'serch for invoices',
      ['search for invoices', 'list users']
    );
    expect(result.matched).toBe(true);
    expect(result.bestPhrase).toBe('search for invoices');
    expect(result.confidence).toBeGreaterThan(0.7);
  });

  it('does not match unrelated text', () => {
    const result = testVoiceCommandPhraseMatch(
      'restart the cluster immediately',
      ['search for invoices', 'list users']
    );
    expect(result.matched).toBe(false);
    expect(result.confidence).toBeLessThan(0.6);
  });
});

