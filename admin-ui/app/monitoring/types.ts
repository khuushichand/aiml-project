export interface Metric {
  name: string;
  value: string | number;
  unit?: string;
  status?: 'healthy' | 'warning' | 'critical';
}

export type AlertSeverity = 'info' | 'warning' | 'error' | 'critical';

export type AlertRuleMetric =
  | 'cpu'
  | 'memory'
  | 'diskUsage'
  | 'throughput'
  | 'activeConnections'
  | 'queueDepth';

export type AlertRuleOperator = '>' | '<' | '==';

export type AlertRuleDurationMinutes = 1 | 5 | 10 | 15 | 30 | 60 | 240 | 1440;

export type AlertHistoryAction =
  | 'triggered'
  | 'acknowledged'
  | 'dismissed'
  | 'assigned'
  | 'unassigned'
  | 'snoozed'
  | 'escalated';

export type SnoozeDurationOption = '15m' | '1h' | '4h' | '24h';

export interface AlertAssignableUser {
  id: string;
  label: string;
}

export interface AlertRule {
  id: string;
  metric: AlertRuleMetric;
  operator: AlertRuleOperator;
  threshold: number;
  durationMinutes: AlertRuleDurationMinutes;
  severity: AlertSeverity;
  createdAt: string;
}

export interface AlertRuleDraft {
  metric: AlertRuleMetric;
  operator: AlertRuleOperator;
  threshold: string;
  durationMinutes: string;
  severity: AlertSeverity;
}

export interface AlertRuleValidationErrors {
  metric?: string;
  operator?: string;
  threshold?: string;
  durationMinutes?: string;
  severity?: string;
}

export interface AlertHistoryEntry {
  id: string;
  alertId: string;
  timestamp: string;
  action: AlertHistoryAction;
  actor?: string;
  details?: string;
}

export interface Watchlist {
  id: string;
  name: string;
  description?: string;
  target: string;
  type: string;
  threshold?: number;
  status: string;
  last_checked?: string;
  created_at?: string;
}

export interface SystemAlert {
  id: string;
  alert_identity?: string;
  severity: AlertSeverity;
  message: string;
  source?: string;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_at?: string;
  dismissed_at?: string;
  acknowledged_by?: string;
  assigned_to?: string;
  snoozed_until?: string;
  escalated_severity?: AlertSeverity;
  metadata?: Record<string, unknown>;
}

export interface MetricsHistoryPoint {
  timestamp: string;
  label: string;
  cpu: number;
  memory: number;
  diskUsage: number;
  throughput: number;
  activeConnections: number;
  queueDepth: number;
}

export type SystemHealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown';
export type SystemStatusKey =
  | 'api'
  | 'database'
  | 'llm'
  | 'rag'
  | 'tts'
  | 'stt'
  | 'embeddings'
  | 'cache'
  | 'queue';

export interface SystemStatusItem {
  key: SystemStatusKey;
  label: string;
  status: SystemHealthStatus;
  detail: string;
  lastCheckedAt?: string;
  responseTimeMs?: number | null;
  source?: 'endpoint' | 'metrics';
}

export interface WatchlistDraft {
  name: string;
  description: string;
  target: string;
  type: string;
  threshold: number;
}

export interface NotificationChannel {
  type: 'email' | 'webhook' | 'slack' | 'discord';
  enabled: boolean;
  config: Record<string, string>;
  clientId?: string;
}

export interface NotificationSettings {
  id?: string;
  channels: NotificationChannel[];
  alert_threshold: 'info' | 'warning' | 'error' | 'critical';
  digest_enabled: boolean;
  digest_frequency: 'hourly' | 'daily' | 'weekly';
}

export interface NotificationSettingsApi {
  enabled?: boolean;
  min_severity?: string;
  file?: string;
  webhook_url?: string | null;
  email_to?: string | null;
  smtp_host?: string | null;
  smtp_port?: number | null;
  smtp_starttls?: boolean | null;
  smtp_user?: string | null;
  email_from?: string | null;
}

export interface RecentNotification {
  id: string;
  channel: string;
  message: string;
  status: 'sent' | 'failed' | 'pending';
  timestamp: string;
  error?: string;
  severity?: string;
}
