import { describe, it, expect } from 'vitest';
import {
  RATE_LIMIT_MINIMUM_ERROR,
  RATE_LIMIT_REQUIRED_ERROR,
  deriveLimitPerMinute,
  getDerivedLimitPerMin,
  normalizeRateLimitValue,
  validateRateLimitInputs,
} from './rate-limits';

describe('rate limit helpers', () => {
  describe('normalizeRateLimitValue', () => {
    it('returns null for null or non-positive values', () => {
      expect(normalizeRateLimitValue(null)).toBeNull();
      expect(normalizeRateLimitValue(0)).toBeNull();
      expect(normalizeRateLimitValue(-5)).toBeNull();
    });

    it('returns the value for positive inputs', () => {
      expect(normalizeRateLimitValue(1)).toBe(1);
      expect(normalizeRateLimitValue(120)).toBe(120);
    });
  });

  describe('deriveLimitPerMinute', () => {
    it('returns null when input is null or below one per minute', () => {
      expect(deriveLimitPerMinute(null, 60)).toBeNull();
      expect(deriveLimitPerMinute(30, 60)).toBeNull();
    });

    it('returns a floored per-minute value for valid inputs', () => {
      expect(deriveLimitPerMinute(60, 60)).toBe(1);
      expect(deriveLimitPerMinute(119, 60)).toBe(1);
      expect(deriveLimitPerMinute(120, 60)).toBe(2);
    });
  });

  describe('getDerivedLimitPerMin', () => {
    it('prefers rpm when provided', () => {
      expect(getDerivedLimitPerMin(5, 120, 1440)).toBe(5);
    });

    it('falls back to derived hourly or daily limits', () => {
      expect(getDerivedLimitPerMin(null, 120, null)).toBe(2);
      expect(getDerivedLimitPerMin(null, null, 2880)).toBe(2);
    });

    it('returns null when hourly/daily values are below one per minute', () => {
      expect(getDerivedLimitPerMin(null, 30, null)).toBeNull();
      expect(getDerivedLimitPerMin(null, null, 1000)).toBeNull();
    });
  });

  describe('validateRateLimitInputs', () => {
    it('requires at least one value', () => {
      const result = validateRateLimitInputs(null, null, null);
      expect(result.error).toBe(RATE_LIMIT_REQUIRED_ERROR);
      expect(result.derivedLimitPerMin).toBeNull();
    });

    it('rejects hourly/daily inputs that cannot be converted', () => {
      const result = validateRateLimitInputs(null, 30, null);
      expect(result.error).toBe(RATE_LIMIT_MINIMUM_ERROR);
      expect(result.derivedLimitPerMin).toBeNull();
    });

    it('accepts valid inputs and returns derived per-minute limit', () => {
      const result = validateRateLimitInputs(null, 120, null);
      expect(result.error).toBeNull();
      expect(result.derivedLimitPerMin).toBe(2);
    });
  });
});
