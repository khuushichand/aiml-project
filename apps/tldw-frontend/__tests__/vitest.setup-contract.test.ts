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
});
