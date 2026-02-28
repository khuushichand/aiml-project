import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const TARGET_FILES = [
  'app/users/page.tsx',
  'app/organizations/page.tsx',
  'app/teams/page.tsx',
  'app/api-keys/page.tsx',
  'app/jobs/page.tsx',
  'app/incidents/page.tsx',
  'app/logs/page.tsx',
  'app/voice-commands/page.tsx',
  'app/flags/page.tsx',
  'app/budgets/page.tsx',
  'app/roles/compare/page.tsx',
] as const;

describe('empty-state audit for core list pages', () => {
  it('uses the shared EmptyState component on all audited pages', () => {
    TARGET_FILES.forEach((relativePath) => {
      const absolutePath = join(process.cwd(), relativePath);
      const source = readFileSync(absolutePath, 'utf8');
      expect(source.includes('EmptyState')).toBe(true);
      expect(source.includes('<EmptyState')).toBe(true);
    });
  });
});
