import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

/** @type {import('next').NextConfig} */
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const backendEnvPath = path.resolve(__dirname, '../tldw_Server_API/Config_Files/.env');

if (fs.existsSync(backendEnvPath)) {
  const rawEnv = fs.readFileSync(backendEnvPath, 'utf8');
  rawEnv.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      return;
    }
    const delimiterIndex = trimmed.indexOf('=');
    if (delimiterIndex <= 0) {
      return;
    }
    const key = trimmed.slice(0, delimiterIndex).trim();
    let value = trimmed.slice(delimiterIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (key) {
      process.env[key] = value;
    }
  });
}

const nextConfig = {
  reactStrictMode: true,
  experimental: {
    reactCompiler: false,
  },
  eslint: {
    // Skip ESLint during builds - run separately via npm run lint
    ignoreDuringBuilds: true,
  },
  webpack: (config) => {
    // Support `@/...` imports (alias to project root)
    config.resolve.alias['@'] = path.resolve(__dirname);
    return config;
  },
};

export default nextConfig;
