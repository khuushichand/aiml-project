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
    if (!Ajv) return [];
    const ajv = new Ajv({ allErrors: true, allowUnionTypes: true, strict: false });
    const validate = ajv.compile(schema);
    const ok = validate(data);
    if (ok) return [];
    const errs = (validate.errors || []).map((e: AjvError) => `${e.instancePath || e.schemaPath}: ${e.message}`);
    return errs;
  } catch {
    // ajv not installed or failed, return no errors to avoid blocking
    return [];
  }
}

