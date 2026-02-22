export interface RateLimitEvent {
  actor: string;
  policy: string;
  rejections24h: number;
  rejections7d: number;
  lastRejectedAt: string | null;
  source: 'endpoint' | 'metrics_text';
  resourceType?: string;
  reason?: string;
}

const getRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null;

const normalizeString = (value: unknown): string | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
};

const normalizeNumber = (value: unknown): number | null => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const normalizeTimestamp = (value: unknown): string | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    // Prometheus timestamp is typically milliseconds. Fall back to seconds.
    const epochMs = value > 1_000_000_000_000 ? value : value > 10_000_000_000 ? value : value * 1000;
    const date = new Date(epochMs);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      return normalizeTimestamp(numeric);
    }
    const date = new Date(trimmed);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
  }
  return null;
};

const formatActorFromScope = (scope: string | null, scopeId: string | null): string | null => {
  if (!scope) return null;
  const normalizedScope = scope.toLowerCase();
  if (normalizedScope === 'user') return scopeId ? `User ${scopeId}` : 'User';
  if (normalizedScope === 'role') return scopeId ? `Role ${scopeId}` : 'Role';
  if (normalizedScope === 'org') return scopeId ? `Org ${scopeId}` : 'Org';
  if (normalizedScope === 'global') return 'Global';
  return scopeId ? `${scope} ${scopeId}` : scope;
};

const parseActorFromEntity = (entity: string | null): string | null => {
  if (!entity) return null;
  const [rawScope, rawValue] = entity.split(':', 2);
  const scope = rawScope?.trim();
  const value = rawValue?.trim();
  if (!scope) return entity;
  return formatActorFromScope(scope, value || null) || entity;
};

const parseEndpointActor = (record: Record<string, unknown>): string => {
  const username = normalizeString(record.username);
  const userId = normalizeString(record.user_id) ?? normalizeString(record.userId);
  if (username && userId) return `${username} (${userId})`;
  if (username) return username;
  if (userId) return `User ${userId}`;

  const role = normalizeString(record.role);
  if (role) return `Role ${role}`;

  const entity = parseActorFromEntity(normalizeString(record.entity));
  if (entity) return entity;

  const scopeActor = formatActorFromScope(
    normalizeString(record.scope),
    normalizeString(record.scope_id) ?? normalizeString(record.scopeId)
  );
  return scopeActor ?? 'Unknown';
};

const parsePrometheusLabels = (input: string): Record<string, string> => {
  const labels: Record<string, string> = {};
  const labelPattern = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"/g;
  let match: RegExpExecArray | null = labelPattern.exec(input);
  while (match) {
    const [, key, rawValue] = match;
    labels[key] = rawValue
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
      .replace(/\\n/g, '\n');
    match = labelPattern.exec(input);
  }
  return labels;
};

const parsePrometheusMetricLine = (line: string) => {
  const metricPattern = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([+-]?(?:\d+\.?\d*|\d*\.?\d+)(?:[eE][+-]?\d+)?)\s*(\d+)?$/;
  const match = line.match(metricPattern);
  if (!match) return null;
  const [, name, labelsRaw, valueRaw, timestampRaw] = match;
  const value = Number(valueRaw);
  if (!Number.isFinite(value)) return null;
  return {
    name,
    labels: parsePrometheusLabels(labelsRaw ?? ''),
    value,
    timestamp: normalizeTimestamp(timestampRaw ?? null),
  };
};

const eventSort = (a: RateLimitEvent, b: RateLimitEvent) => {
  if (a.rejections24h !== b.rejections24h) return b.rejections24h - a.rejections24h;
  if (a.rejections7d !== b.rejections7d) return b.rejections7d - a.rejections7d;
  const aTs = a.lastRejectedAt ? new Date(a.lastRejectedAt).getTime() : 0;
  const bTs = b.lastRejectedAt ? new Date(b.lastRejectedAt).getTime() : 0;
  return bTs - aTs;
};

export const normalizeRateLimitEventsPayload = (payload: unknown): RateLimitEvent[] => {
  const record = getRecord(payload);
  const items = Array.isArray(payload)
    ? payload
    : Array.isArray(record?.items)
      ? record.items
      : Array.isArray(record?.events)
        ? record.events
        : [];

  const events: RateLimitEvent[] = [];
  items.forEach((item) => {
    const row = getRecord(item);
    if (!row) return;

    const rejections = normalizeNumber(
      row.rejections_24h
      ?? row.rejection_count
      ?? row.rejections
      ?? row.count
      ?? row.value
      ?? row.hits
    );
    if (!Number.isFinite(rejections ?? NaN)) return;
    const rejections7d = normalizeNumber(
      row.rejections_7d
      ?? row.rejections7d
      ?? row.count_7d
      ?? row.rejections_last_7d
      ?? row.weekly_rejections
      ?? row.rejections_week
      ?? row.hits_7d
      ?? row.hits_week
    );

    const policy = normalizeString(row.policy)
      ?? normalizeString(row.policy_id)
      ?? normalizeString(row.rule)
      ?? normalizeString(row.rule_id)
      ?? 'unknown';
    const lastRejectedAt = normalizeTimestamp(
      row.last_rejection_at
      ?? row.last_rejected_at
      ?? row.last_seen_at
      ?? row.timestamp
    );
    const resourceType = normalizeString(row.resource_type) ?? normalizeString(row.category) ?? undefined;
    const reason = normalizeString(row.reason) ?? undefined;

    events.push({
      actor: parseEndpointActor(row),
      policy,
      rejections24h: Math.max(0, Math.round(rejections ?? 0)),
      rejections7d: Math.max(0, Math.round(rejections7d ?? rejections ?? 0)),
      lastRejectedAt,
      source: 'endpoint',
      resourceType,
      reason,
    });
  });

  return events.sort(eventSort);
};

export const parseRateLimitEventsFromMetricsText = (metricsText: string): RateLimitEvent[] => {
  const aggregate = new Map<string, RateLimitEvent>();
  const lines = metricsText.split('\n');
  lines.forEach((lineRaw) => {
    const line = lineRaw.trim();
    if (!line || line.startsWith('#')) return;
    const metric = parsePrometheusMetricLine(line);
    if (!metric) return;

    if (metric.name !== 'rg_denials_total'
      && metric.name !== 'rg_denials_by_entity_total'
      && metric.name !== 'mcp_rate_limit_hits_total') {
      return;
    }

    const labels = metric.labels;
    const policy = labels.policy_id || (metric.name === 'mcp_rate_limit_hits_total' ? 'mcp.unified' : 'unknown');
    const resourceType = labels.category || undefined;
    const reason = labels.reason || undefined;
    const actor = parseActorFromEntity(labels.entity || null)
      ?? formatActorFromScope(labels.scope || null, labels.scope_id || null)
      ?? (metric.name === 'mcp_rate_limit_hits_total' ? `MCP ${labels.key_type || 'user'}` : 'Unknown');

    const key = `${actor}|${policy}|${resourceType ?? ''}|${reason ?? ''}`;
    const existing = aggregate.get(key);
    const value = Math.max(0, Math.round(metric.value));
    if (!existing) {
      aggregate.set(key, {
        actor,
        policy,
        rejections24h: value,
        rejections7d: value,
        lastRejectedAt: metric.timestamp,
        source: 'metrics_text',
        resourceType,
        reason,
      });
      return;
    }

    existing.rejections24h += value;
    existing.rejections7d += value;
    if (metric.timestamp && (!existing.lastRejectedAt || metric.timestamp > existing.lastRejectedAt)) {
      existing.lastRejectedAt = metric.timestamp;
    }
  });

  return Array.from(aggregate.values()).sort(eventSort);
};
