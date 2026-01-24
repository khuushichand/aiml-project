// Type declarations for Vite-specific APIs used in shared packages/ui code
// These allow TypeScript to compile packages/ui code that uses Vite features,
// even though Next.js doesn't provide these at runtime.

interface ImportMetaEnv {
  DEV?: boolean
  MODE?: string
  PROD?: boolean
}

interface ImportMeta {
  readonly env?: ImportMetaEnv
  glob?: <T = unknown>(
    pattern: string,
    options?: {
      query?: string
      import?: string
      eager?: boolean
    }
  ) => Record<string, T>
}
