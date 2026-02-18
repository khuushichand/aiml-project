import { describe, expect, it } from 'vitest';
import { DEPRECATED_MODEL_NOTICES, getDeprecatedModelNotice, isModelDeprecated } from './deprecated-models';

describe('deprecated model notices', () => {
  it('matches snapshot', () => {
    expect(DEPRECATED_MODEL_NOTICES).toMatchSnapshot();
  });

  it('matches exact and prefix model names', () => {
    expect(isModelDeprecated('text-davinci-003')).toBe(true);
    expect(isModelDeprecated('claude-2')).toBe(true);
    expect(isModelDeprecated('gpt-3.5-turbo-0125')).toBe(true);
    expect(isModelDeprecated('gpt-4.1')).toBe(false);
  });

  it('returns replacement guidance for deprecated models', () => {
    expect(getDeprecatedModelNotice('gpt-3.5-turbo')?.replacement).toBe('gpt-4.1-mini');
    expect(getDeprecatedModelNotice('claude-2.1')?.replacement).toBe('claude-sonnet-4-20250514');
  });
});
