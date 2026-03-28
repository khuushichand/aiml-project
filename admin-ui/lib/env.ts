import { z } from 'zod';

const envSchema = z.object({
  NEXT_PUBLIC_API_URL: z
    .string({ required_error: 'NEXT_PUBLIC_API_URL is required' })
    .url('NEXT_PUBLIC_API_URL must be a valid URL'),
  NEXT_PUBLIC_API_VERSION: z.string().default('v1'),
  NEXT_PUBLIC_DEFAULT_AUTH_MODE: z
    .enum(['password', 'apikey'])
    .default('password'),
  NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN: z
    .string()
    .transform((v) => v === 'true')
    .default('false'),
  NEXT_PUBLIC_BILLING_ENABLED: z
    .string()
    .transform((v) => v === 'true')
    .default('false'),
});

export type AppEnv = z.infer<typeof envSchema>;

let cachedEnv: AppEnv | null = null;

export function validateEnv(): AppEnv {
  if (cachedEnv) return cachedEnv;

  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    const errors = result.error.issues
      .map((i) => `  ${i.path.join('.')}: ${i.message}`)
      .join('\n');
    throw new Error(`Environment validation failed:\n${errors}`);
  }

  cachedEnv = result.data;
  return cachedEnv;
}
