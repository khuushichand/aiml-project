import { afterEach, describe, expect, it } from 'vitest';
import { isUnsafeLocalToolsEnabled } from './admin-ui-flags';

const ORIGINAL_UNSAFE_LOCAL_TOOLS = process.env.NEXT_PUBLIC_ADMIN_UI_ENABLE_UNSAFE_LOCAL_TOOLS;

afterEach(() => {
  if (ORIGINAL_UNSAFE_LOCAL_TOOLS === undefined) {
    delete process.env.NEXT_PUBLIC_ADMIN_UI_ENABLE_UNSAFE_LOCAL_TOOLS;
    return;
  }
  process.env.NEXT_PUBLIC_ADMIN_UI_ENABLE_UNSAFE_LOCAL_TOOLS = ORIGINAL_UNSAFE_LOCAL_TOOLS;
});

describe('isUnsafeLocalToolsEnabled', () => {
  it('returns false when the env flag is missing', () => {
    delete process.env.NEXT_PUBLIC_ADMIN_UI_ENABLE_UNSAFE_LOCAL_TOOLS;

    expect(isUnsafeLocalToolsEnabled()).toBe(false);
  });

  it('returns true only when the env flag is explicitly true', () => {
    process.env.NEXT_PUBLIC_ADMIN_UI_ENABLE_UNSAFE_LOCAL_TOOLS = 'true';
    expect(isUnsafeLocalToolsEnabled()).toBe(true);

    process.env.NEXT_PUBLIC_ADMIN_UI_ENABLE_UNSAFE_LOCAL_TOOLS = 'false';
    expect(isUnsafeLocalToolsEnabled()).toBe(false);
  });
});
