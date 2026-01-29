export interface Metric {
  name: string;
  value: string | number;
  unit?: string;
  status?: 'healthy' | 'warning' | 'critical';
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
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  source?: string;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_at?: string;
  acknowledged_by?: string;
}

export interface MetricsHistoryPoint {
  time: string;
  cpu: number;
  memory: number;
}

export type SystemHealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown';
export type SystemStatusKey = 'api' | 'database' | 'llm' | 'rag';

export interface SystemStatusItem {
  key: SystemStatusKey;
  label: string;
  status: SystemHealthStatus;
  detail: string;
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

export interface RecentNotification {
  id: string;
  channel: string;
  message: string;
  status: 'sent' | 'failed' | 'pending';
  timestamp: string;
  error?: string;
}
