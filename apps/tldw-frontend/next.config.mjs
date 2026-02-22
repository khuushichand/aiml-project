import path from 'path';
import { fileURLToPath } from 'url';

/** @type {import('next').NextConfig} */
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const paTesseractPath = path.resolve(__dirname, 'node_modules/pa-tesseract.js');

const nextConfig = {
  reactStrictMode: true,
  reactCompiler: false,
  async redirects() {
    return [
      {
        source: '/chat/settings',
        destination: '/settings/chat',
        permanent: false,
      },
    ];
  },
  // Emit a standalone server bundle for distribution via Docker or tarball artifacts.
  output: 'standalone',
  // Skip TypeScript errors during build - packages/ui was developed with
  // Vite/WXT type definitions that Next.js doesn't provide.
  // Runtime works correctly; these are type-definition mismatches.
  typescript: {
    ignoreBuildErrors: true,
  },
  turbopack: {
    // Keep Turbopack aliases aligned with shared UI + web shims.
    resolveAlias: {
      '@tldw/ui': '../../packages/ui/src',
      '@': '../../packages/ui/src',
      '~': '../../packages/ui/src',
      '@web': '.',
      'pa-tesseract.js': './node_modules/pa-tesseract.js',
      'react-router-dom': './extension/shims/react-router-dom.tsx',
      '@plasmohq/storage': './extension/shims/plasmo-storage.ts',
      '@plasmohq/storage/hook': './extension/shims/plasmo-storage-hook.tsx',
      'wxt/browser': './extension/shims/wxt-browser.ts',
    },
  },
  // Ensure Next resolves the correct monorepo root when multiple lockfiles exist.
  outputFileTracingRoot: path.resolve(__dirname, '../..'),
  transpilePackages: ['@tldw/ui'],
  webpack: (config) => {
    // Support extension-aligned aliases + shims
    config.resolve.alias['@tldw/ui'] = path.resolve(__dirname, '../../packages/ui/src');
    config.resolve.alias['@'] = path.resolve(__dirname, '../../packages/ui/src');
    config.resolve.alias['~'] = path.resolve(__dirname, '../../packages/ui/src');
    config.resolve.alias['@web'] = path.resolve(__dirname, '.');
    config.resolve.alias['pa-tesseract.js'] = paTesseractPath;
    config.resolve.alias['react-router-dom'] = path.resolve(
      __dirname,
      'extension/shims/react-router-dom.tsx'
    );
    config.resolve.alias['@plasmohq/storage'] = path.resolve(
      __dirname,
      'extension/shims/plasmo-storage.ts'
    );
    config.resolve.alias['@plasmohq/storage/hook'] = path.resolve(
      __dirname,
      'extension/shims/plasmo-storage-hook.tsx'
    );
    config.resolve.alias['wxt/browser'] = path.resolve(
      __dirname,
      'extension/shims/wxt-browser.ts'
    );
    return config;
  },
};

export default nextConfig;
