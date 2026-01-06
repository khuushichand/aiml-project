type ListContainer = Record<string, unknown>;

export const normalizeListResponse = <T>(
  data: unknown,
  keys: string[] = ['items', 'entries', 'users', 'codes']
): T[] => {
  if (Array.isArray(data)) {
    return data as T[];
  }
  if (!data || typeof data !== 'object') {
    return [];
  }
  const record = data as ListContainer;
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) {
      return value as T[];
    }
  }
  return [];
};

export const normalizePagedResponse = <T>(
  data: unknown,
  keys?: string[]
): { items: T[]; total: number; limit?: number; offset?: number } => {
  const items = normalizeListResponse<T>(data, keys);
  const record = data && typeof data === 'object' ? (data as ListContainer) : {};
  const total = typeof record.total === 'number' ? Number(record.total) : items.length;
  const limit = typeof record.limit === 'number' ? Number(record.limit) : undefined;
  const offset = typeof record.offset === 'number' ? Number(record.offset) : undefined;
  return { items, total, limit, offset };
};
