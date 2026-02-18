import { describe, expect, it } from 'vitest';
import { deriveComparisonCellState } from './role-comparison';

describe('deriveComparisonCellState', () => {
  it('returns shared when all selected roles have the same permission state', () => {
    expect(deriveComparisonCellState([true, true], 0)).toBe('shared');
    expect(deriveComparisonCellState([false, false, false], 2)).toBe('shared');
  });

  it('returns only-has when the selected role uniquely has a permission', () => {
    expect(deriveComparisonCellState([true, false], 0)).toBe('only-has');
    expect(deriveComparisonCellState([false, true, false], 1)).toBe('only-has');
  });

  it('returns only-missing when the selected role uniquely lacks a permission', () => {
    expect(deriveComparisonCellState([true, false], 1)).toBe('only-missing');
    expect(deriveComparisonCellState([false, true, true], 0)).toBe('only-missing');
  });
});
