export type JsonSchema = {
  type?: 'object' | 'array' | 'string' | 'number' | 'integer' | 'boolean' | 'null';
  title?: string;
  description?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
};

export function validateJsonSchema(data: unknown, schema: JsonSchema, path: string = ''): string[] {
  const errors: string[] = [];
  const p = (k: string) => (path ? `${path}.${k}` : k);

  if (!schema) return errors;
  if (schema.type) {
    const ok = typeMatches(data, schema.type);
    if (!ok) errors.push(`${path || 'value'} should be of type ${schema.type}`);
  }

  if (schema.type === 'object' && schema.properties) {
    // required
    (schema.required || []).forEach((key) => {
      if (data == null || typeof data !== 'object' || !(key in data)) {
        errors.push(`${p(key)} is required`);
      }
    });
    // properties
    Object.entries(schema.properties).forEach(([key, subschema]) => {
      if (data && typeof data === 'object' && key in data) {
        errors.push(...validateJsonSchema((data as Record<string, unknown>)[key], subschema, p(key)));
      }
    });
  }

  if (schema.type === 'array' && schema.items && Array.isArray(data)) {
    data.forEach((item: unknown, idx: number) => {
      errors.push(...validateJsonSchema(item, schema.items as JsonSchema, `${path}[${idx}]`));
    });
  }

  if ((schema.type === 'number' || schema.type === 'integer') && typeof data === 'number') {
    if (typeof schema.minimum === 'number' && data < schema.minimum) errors.push(`${path || 'value'} should be >= ${schema.minimum}`);
    if (typeof schema.maximum === 'number' && data > schema.maximum) errors.push(`${path || 'value'} should be <= ${schema.maximum}`);
  }

  if (schema.enum && schema.enum.length > 0) {
    let found = false;
    for (const v of schema.enum) { if (deepEqual(v, data)) { found = true; break; } }
    if (!found) errors.push(`${path || 'value'} should be one of: ${schema.enum.map((v) => JSON.stringify(v)).join(', ')}`);
  }

  return errors;
}

function typeMatches(v: unknown, type: NonNullable<JsonSchema['type']>): boolean {
  if (type === 'null') return v === null;
  if (type === 'integer') return typeof v === 'number' && Number.isInteger(v);
  if (type === 'number') return typeof v === 'number';
  if (type === 'string') return typeof v === 'string';
  if (type === 'boolean') return typeof v === 'boolean';
  if (type === 'object') return v != null && typeof v === 'object' && !Array.isArray(v);
  if (type === 'array') return Array.isArray(v);
  return true;
}

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a && b && typeof a === 'object') {
    if (Array.isArray(a)) {
      if (!Array.isArray(b) || a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) if (!deepEqual(a[i], b[i])) return false;
      return true;
    }
    const objA = a as Record<string, unknown>;
    const objB = b as Record<string, unknown>;
    const ka = Object.keys(objA), kb = Object.keys(objB);
    if (ka.length !== kb.length) return false;
    for (const k of ka) if (!deepEqual(objA[k], objB[k])) return false;
    return true;
  }
  return false;
}

