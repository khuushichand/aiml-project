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
  eslint: {
    // Enforce ESLint during builds so lint failures block deployments.
    ignoreDuringBuilds: false,
  },
  webpack: (config) => {
    // Support `@/...` imports (alias to project root)
    config.resolve.alias['@'] = path.resolve(__dirname);
    return config;
  },
};

export default nextConfig;
