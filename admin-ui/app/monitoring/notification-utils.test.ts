import { describe, expect, it } from 'vitest';
import {
  buildNotificationSettingsUpdate,
  DEFAULT_NOTIFICATION_SETTINGS,
  normalizeNotificationSettings,
  normalizeRecentNotifications,
} from './notification-utils';

describe('notification-utils', () => {
  it('normalizes API notification settings payload to UI shape', () => {
    const normalized = normalizeNotificationSettings({
      enabled: false,
      min_severity: 'critical',
      email_to: 'ops@example.com',
      webhook_url: 'https://hooks.example.test/alerts',
    });

    expect(normalized.alert_threshold).toBe('critical');
    expect(normalized.digest_enabled).toBe(DEFAULT_NOTIFICATION_SETTINGS.digest_enabled);
    expect(normalized.digest_frequency).toBe(DEFAULT_NOTIFICATION_SETTINGS.digest_frequency);
    expect(normalized.channels).toEqual([
      {
        type: 'email',
        enabled: false,
        config: { address: 'ops@example.com' },
      },
      {
        type: 'webhook',
        enabled: false,
        config: { url: 'https://hooks.example.test/alerts' },
      },
    ]);
  });

  it('keeps UI settings shape while normalizing threshold casing', () => {
    const normalized = normalizeNotificationSettings({
      channels: [],
      alert_threshold: 'ERROR',
      digest_enabled: true,
      digest_frequency: 'weekly',
    });

    expect(normalized.alert_threshold).toBe('error');
    expect(normalized.digest_enabled).toBe(true);
    expect(normalized.digest_frequency).toBe('weekly');
    expect(normalized.channels).toEqual([]);
  });

  it('builds API payload from UI settings channels', () => {
    const payload = buildNotificationSettingsUpdate({
      channels: [
        {
          type: 'email',
          enabled: true,
          config: { address: 'ops@example.com' },
        },
        {
          type: 'email',
          enabled: false,
          config: { address: 'security@example.com' },
        },
        {
          type: 'discord',
          enabled: true,
          config: { url: 'https://discord.com/api/webhooks/abc' },
        },
      ],
      alert_threshold: 'error',
      digest_enabled: false,
      digest_frequency: 'daily',
    });

    expect(payload).toEqual({
      enabled: true,
      min_severity: 'warning',
      email_to: 'ops@example.com,security@example.com',
      webhook_url: 'https://discord.com/api/webhooks/abc',
    });
  });

  it('normalizes recent notification rows from mixed payloads', () => {
    const normalized = normalizeRecentNotifications({
      notifications: [
        {
          id: 'n1',
          channel: 'email',
          message: 'Sent message',
          status: 'sent',
          timestamp: '2026-02-27T12:00:00Z',
        },
        {
          id: 'n2',
          type: 'webhook',
          details: {
            deliveries: [
              { status: 'failed', recipient: 'primary webhook' },
            ],
          },
          status: 'error',
          created_at: '2026-02-27T13:00:00Z',
        },
      ],
    });

    expect(normalized).toHaveLength(2);
    expect(normalized[0]).toEqual({
      id: 'n1',
      channel: 'email',
      message: 'Sent message',
      status: 'sent',
      timestamp: '2026-02-27T12:00:00.000Z',
      error: undefined,
      severity: undefined,
    });

    expect(normalized[1]).toMatchObject({
      id: 'n2',
      channel: 'webhook',
      status: 'failed',
      timestamp: '2026-02-27T13:00:00.000Z',
      error: 'Delivery failed for primary webhook',
    });
  });
});
