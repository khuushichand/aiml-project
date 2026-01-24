import { describe, expect, it } from 'vitest';
import { isDuplicateWorkspacePath, normalizeWorkspacePath } from '../workspace-paths';

describe('workspace-paths', () => {
  it('normalizes trailing separators for comparison', () => {
    expect(normalizeWorkspacePath('/Users/alice/Project/')).toBe('/Users/alice/Project');
  });

  it('treats Windows paths as duplicate across case and slashes', () => {
    const workspaces = [{ path: 'C:\\Projects\\App' }];

    expect(isDuplicateWorkspacePath('c:/projects/app/', workspaces)).toBe(true);
  });
});
