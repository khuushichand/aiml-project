import axe from 'axe-core';

export const AXE_SMOKE_OPTIONS: axe.RunOptions = {
  runOnly: {
    type: 'tag',
    values: ['wcag2a', 'wcag2aa'],
  },
  rules: {
    // jsdom does not compute layout/paint with browser accuracy; color contrast is
    // enforced separately via token-level contrast tests.
    'color-contrast': { enabled: false },
  },
};

export type AxeViolation = axe.Result;

export async function getCriticalAndSeriousAxeViolations(
  context: Element | Document = document,
  options?: axe.RunOptions,
): Promise<AxeViolation[]> {
  const results = await axe.run(context, { ...AXE_SMOKE_OPTIONS, ...(options || {}) });
  return results.violations.filter((violation) => (
    violation.impact === 'critical' || violation.impact === 'serious'
  ));
}

export function formatAxeViolations(violations: AxeViolation[]): string {
  if (violations.length === 0) return 'No critical/serious axe violations.';
  return violations
    .map((violation) => {
      const nodes = violation.nodes
        .map((node) => node.target.join(' '))
        .join('; ');
      return `[${violation.impact}] ${violation.id}: ${violation.help} (${nodes})`;
    })
    .join('\n');
}
