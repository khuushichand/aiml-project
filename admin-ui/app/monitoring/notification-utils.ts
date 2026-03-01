import type {
  NotificationChannel,
  NotificationSettings,
  NotificationSettingsApi,
  RecentNotification,
} from './types';

export const DEFAULT_NOTIFICATION_SETTINGS: NotificationSettings = {
  channels: [],
  alert_threshold: 'warning',
  digest_enabled: false,
  digest_frequency: 'daily',
};

const normalizeAlertThreshold = (value?: string): NotificationSettings['alert_threshold'] => {
  const normalized = typeof value === 'string' ? value.toLowerCase() : '';
  switch (normalized) {
    case 'info':
    case 'warning':
    case 'error':
    case 'critical':
      return normalized as NotificationSettings['alert_threshold'];
    default:
      return 'warning';
  }
};

const toApiMinSeverity = (value: NotificationSettings['alert_threshold']): string => {
  if (value === 'info' || value === 'warning' || value === 'critical') {
    return value;
  }
  return 'warning';
};

const isNotificationSettingsUi = (value: unknown): value is NotificationSettings =>
  Boolean(value && typeof value === 'object' && Array.isArray((value as NotificationSettings).channels));

const getChannelConfigValue = (channel?: NotificationChannel): string => {
  if (!channel?.config) return '';
  const direct = channel.type === 'email' ? channel.config.address : channel.config.url;
  if (typeof direct === 'string' && direct.trim()) return direct.trim();
  const first = Object.values(channel.config)[0];
  return typeof first === 'string' ? first.trim() : '';
};

export const normalizeNotificationSettings = (value: unknown): NotificationSettings => {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_NOTIFICATION_SETTINGS };
  }

  if (isNotificationSettingsUi(value)) {
    const ui = value as NotificationSettings;
    return {
      id: ui.id,
      channels: Array.isArray(ui.channels) ? ui.channels : [],
      alert_threshold: normalizeAlertThreshold(ui.alert_threshold),
      digest_enabled: ui.digest_enabled ?? DEFAULT_NOTIFICATION_SETTINGS.digest_enabled,
      digest_frequency: ui.digest_frequency ?? DEFAULT_NOTIFICATION_SETTINGS.digest_frequency,
    };
  }

  const apiValue = value as NotificationSettingsApi;
  const enabled = apiValue.enabled ?? true;
  const channels: NotificationChannel[] = [];
  if (apiValue.email_to && String(apiValue.email_to).trim()) {
    channels.push({
      type: 'email',
      enabled,
      config: { address: String(apiValue.email_to).trim() },
    });
  }
  if (apiValue.webhook_url && String(apiValue.webhook_url).trim()) {
    channels.push({
      type: 'webhook',
      enabled,
      config: { url: String(apiValue.webhook_url).trim() },
    });
  }
  return {
    ...DEFAULT_NOTIFICATION_SETTINGS,
    channels,
    alert_threshold: normalizeAlertThreshold(apiValue.min_severity),
  };
};

export const buildNotificationSettingsUpdate = (settings: NotificationSettings): NotificationSettingsApi => {
  const channels = settings.channels ?? [];
  const emailValues = channels
    .filter((channel) => channel.type === 'email')
    .map(getChannelConfigValue)
    .filter((value) => value);
  const webhookChannel = channels.find(
    (channel) => channel.type === 'webhook' || channel.type === 'slack' || channel.type === 'discord'
  );
  const webhookUrl = getChannelConfigValue(webhookChannel);
  return {
    enabled: channels.some((channel) => channel.enabled),
    min_severity: toApiMinSeverity(settings.alert_threshold),
    email_to: emailValues.length ? emailValues.join(',') : '',
    webhook_url: webhookUrl || '',
  };
};

const toRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null;

const pickString = (...values: unknown[]): string | undefined => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
};

const normalizeRecentNotificationStatus = (value: unknown): RecentNotification['status'] => {
  const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
  if (['sent', 'delivered', 'success', 'ok', 'stored', 'partial'].includes(normalized)) {
    return 'sent';
  }
  if (['failed', 'error'].includes(normalized)) {
    return 'failed';
  }
  return 'pending';
};

const extractRecentNotificationError = (entry: Record<string, unknown>): string | undefined => {
  const details = toRecord(entry.details);
  const directError = pickString(entry.error, details?.error);
  if (directError) return directError;

  const deliveries = Array.isArray(details?.deliveries) ? details.deliveries : [];
  for (const deliveryEntry of deliveries) {
    const delivery = toRecord(deliveryEntry);
    if (!delivery) continue;
    const status = pickString(delivery.status)?.toLowerCase();
    if (status === 'failed' || status === 'error') {
      return pickString(delivery.error)
        ?? `Delivery failed for ${pickString(delivery.recipient) ?? 'recipient'}`;
    }
  }
  return undefined;
};

const normalizeRecentNotificationItem = (value: unknown, index: number): RecentNotification => {
  const fallbackTimestamp = new Date().toISOString();
  const entry = toRecord(value);
  if (!entry) {
    return {
      id: `notification-${index}`,
      channel: 'unknown',
      message: typeof value === 'string' && value.trim() ? value.trim() : 'Notification event',
      status: 'pending',
      timestamp: fallbackTimestamp,
    };
  }

  const details = toRecord(entry.details);
  const timestampRaw = pickString(entry.timestamp, entry.created_at, entry.sent_at, entry.time, entry.occurred_at);
  const parsedTimestamp = timestampRaw ? new Date(timestampRaw) : null;
  const timestamp = parsedTimestamp && !Number.isNaN(parsedTimestamp.getTime())
    ? parsedTimestamp.toISOString()
    : fallbackTimestamp;
  const channel = pickString(entry.channel, entry.type, entry.provider) ?? 'unknown';
  const message = pickString(entry.message, entry.text_snippet, entry.subject, details?.subject, entry.raw)
    ?? 'Notification event';
  const severity = pickString(entry.severity, entry.rule_severity);

  return {
    id: pickString(entry.id, entry.notification_id) ?? `${timestamp}-${channel}-${index}`,
    channel,
    message,
    status: normalizeRecentNotificationStatus(entry.status),
    timestamp,
    error: extractRecentNotificationError(entry),
    severity,
  };
};

export const normalizeRecentNotifications = (value: unknown): RecentNotification[] => {
  const payload = toRecord(value);
  const items = Array.isArray(value)
    ? value
    : Array.isArray(payload?.notifications)
      ? payload.notifications
      : Array.isArray(payload?.items)
        ? payload.items
        : [];

  return items.map((item, index) => normalizeRecentNotificationItem(item, index));
};
