import { createRequire } from 'module';
import { expect } from 'vitest';

const require = createRequire(import.meta.url);

try {
  require('@testing-library/jest-dom/vitest');
} catch {
  // Optional in this workspace; keep tests runnable without matcher extensions.
  expect.extend({
    toBeDisabled(received: unknown) {
      const element = received as Element | null;
      const pass = Boolean(element && 'matches' in element && element.matches(':disabled'));
      return {
        pass,
        message: () =>
          pass
            ? 'expected element not to be disabled'
            : 'expected element to be disabled',
      };
    },
    toBeInTheDocument(received: unknown) {
      const node = received as Node | null;
      const pass = Boolean(node && node.ownerDocument?.contains(node));
      return {
        pass,
        message: () =>
          pass
            ? 'expected node not to be in the document'
            : 'expected node to be in the document',
      };
    },
  });
}
