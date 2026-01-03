import type { JsonSchema } from '@/lib/schema';

interface AjvError {
  instancePath?: string;
  schemaPath?: string;
  message?: string;
}

interface AjvModule {
  default?: new (options: Record<string, unknown>) => AjvInstance;
}

interface AjvInstance {
  compile: (schema: JsonSchema) => AjvValidateFunction;
}

interface AjvValidateFunction {
  (data: unknown): boolean;
  errors?: AjvError[] | null;
}

export async function validateWithAjv(data: unknown, schema?: JsonSchema): Promise<string[]> {
  if (!schema) return [];
  try {
    const mod = await import('ajv') as AjvModule;
    const Ajv = mod.default;
    if (!Ajv) {
      if (typeof console !== 'undefined') {
        console.warn('[validateWithAjv] AJV unavailable – schema validation skipped');
      }
      throw new Error('AJV unavailable: missing default export');
    }
    const ajv = new Ajv({ allErrors: true, allowUnionTypes: true, strict: false });
    const validate = ajv.compile(schema);
    const ok = validate(data);
    if (ok) return [];
    const errs = (validate.errors || []).map((e: AjvError) => `${e.instancePath || e.schemaPath || ''}: ${e.message ?? 'invalid'}`);
    return errs;
  } catch (err) {
    // ajv not installed or failed to initialize; surface to caller
    if (typeof console !== 'undefined') {
      console.warn('[validateWithAjv] AJV unavailable – schema validation skipped');
    }
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(`AJV unavailable: ${message}`);
  }
}
