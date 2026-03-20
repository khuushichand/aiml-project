import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

describe('Vitest setup contract', () => {
  it('imports the shared UI setup baseline', () => {
    const setupPath = path.resolve(__dirname, '..', 'vitest.setup.ts');
    const source = fs.readFileSync(setupPath, 'utf8');

    expect(source).toContain("import '../packages/ui/vitest.setup';");
  });

  it('provides browser APIs required by the characters harness', () => {
    expect(typeof window.matchMedia).toBe('function');
    expect(typeof (window as any).ResizeObserver).toBe('function');
    expect(typeof Blob.prototype.text).toBe('function');
    expect(typeof File.prototype.text).toBe('function');
  });

  it('keeps the setup UI on the bundle-first audio flow', () => {
    const setupUiPath = path.resolve(
      __dirname,
      '..',
      '..',
      '..',
      'tldw_Server_API',
      'app',
      'static',
      'setup',
      'js',
      'setup.js',
    );
    const source = fs.readFileSync(setupUiPath, 'utf8');

    expect(source).toContain('/audio/recommendations');
    expect(source).toContain('/audio/provision');
    expect(source).toContain('/audio/verify');
    expect(source).toContain('Recommended audio bundle');
    expect(source).toContain('Recommended profile');
    expect(source).toContain('Light');
    expect(source).toContain('Balanced');
    expect(source).toContain('Performance');
    expect(source).toContain('Provision recommended bundle');
    expect(source).toContain('Run verification');
    expect(source).toContain('Safe rerun');
  });
});
