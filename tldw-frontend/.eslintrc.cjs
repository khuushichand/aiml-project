// Shim config so Next.js detects the Next plugin during `next build`.
// ESLint uses the flat config in eslint.config.mjs; this file is for Next's detection only.
module.exports = {
  extends: ['next/core-web-vitals'],
};

