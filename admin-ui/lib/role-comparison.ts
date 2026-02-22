export type ComparisonCellState = 'shared' | 'only-has' | 'only-missing';

export const deriveComparisonCellState = (
  rowValues: boolean[],
  roleIndex: number
): ComparisonCellState => {
  if (rowValues.length <= 1) return 'shared';

  const grantedCount = rowValues.filter(Boolean).length;
  if (grantedCount === 0 || grantedCount === rowValues.length) {
    return 'shared';
  }

  return rowValues[roleIndex] ? 'only-has' : 'only-missing';
};
