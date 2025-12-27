import '@testing-library/jest-dom/vitest';
import { afterEach as vitestAfterEach } from 'vitest';
import { cleanup as rtlCleanup } from '@testing-library/react';

vitestAfterEach(() => {
  rtlCleanup();
});
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
