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

  it('returns empty string for whitespace input', () => {
    expect(normalizeWorkspacePath('   ')).toBe('');
  });

  it('preserves root paths', () => {
    expect(normalizeWorkspacePath('/')).toBe('/');
    expect(normalizeWorkspacePath('C:\\')).toBe('c:/');
  });

  it('normalizes UNC paths', () => {
    expect(normalizeWorkspacePath('\\\\server\\share')).toBe('//server/share');
  });

  it('returns false for empty candidate path', () => {
    const workspaces = [{ path: '/some/path' }];

    expect(isDuplicateWorkspacePath('', workspaces)).toBe(false);
  });

  it('returns false for whitespace candidate path', () => {
    const workspaces = [{ path: '/some/path' }];

    expect(isDuplicateWorkspacePath('   ', workspaces)).toBe(false);
  });
});
