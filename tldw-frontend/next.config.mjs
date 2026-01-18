import path from 'path';
import { fileURLToPath } from 'url';

/** @type {import('next').NextConfig} */
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const nextConfig = {
  reactStrictMode: true,
  experimental: {
    reactCompiler: false,
  },
  // Ensure Next resolves the correct monorepo root when multiple lockfiles exist.
  outputFileTracingRoot: path.resolve(__dirname, '..'),
  eslint: {
    // Enforce ESLint during builds so lint failures block deployments.
    ignoreDuringBuilds: false,
  },
  webpack: (config) => {
    // Support extension-aligned aliases + shims
    config.resolve.alias['@'] = path.resolve(__dirname, 'extension');
    config.resolve.alias['~'] = path.resolve(__dirname, 'extension');
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
