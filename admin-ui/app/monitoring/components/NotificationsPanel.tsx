import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Bell, Mail, Webhook, Send, X, AlertCircle, MessageSquare, ToggleLeft, ToggleRight } from 'lucide-react';
import type { NotificationSettings, NotificationChannel, RecentNotification } from '../types';

type NotificationsPanelProps = {
  settings: NotificationSettings | null;
  recentNotifications: RecentNotification[];
  loading: boolean;
  saving: boolean;
  onSave: (settings: NotificationSettings) => void;
  onTest: () => void;
};

const CHANNEL_TYPES = [
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'webhook', label: 'Webhook', icon: Webhook },
  { value: 'slack', label: 'Slack', icon: MessageSquare },
  { value: 'discord', label: 'Discord', icon: MessageSquare },
] as const;

const ALERT_THRESHOLDS = [
  { value: 'info', label: 'Info (All)' },
  { value: 'warning', label: 'Warning+' },
  { value: 'error', label: 'Error+' },
  { value: 'critical', label: 'Critical Only' },
] as const;

const DIGEST_FREQUENCIES = [
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
] as const;

type NotificationsPanelShellProps = {
  children: ReactNode;
  enabledChannels: number;
  loading: boolean;
  saving: boolean;
  onTest: () => void;
};

const NotificationsPanelShell = ({
  children,
  enabledChannels,
  loading,
  saving,
  onTest,
}: NotificationsPanelShellProps) => (
  <Card>
    <CardHeader>
      <div className="flex items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notifications
          </CardTitle>
          <CardDescription>
            Configure alert notification channels
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onTest}
          disabled={loading || saving || enabledChannels === 0}
        >
          <Send className="mr-2 h-4 w-4" />
          Test
        </Button>
      </div>
    </CardHeader>
    <CardContent className="space-y-6">
      {children}
    </CardContent>
  </Card>
);

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return '-';
  return new Date(timestamp).toLocaleString();
};

const getChannelIcon = (type: string) => {
  const channel = CHANNEL_TYPES.find((c) => c.value === type);
  if (channel) {
    const Icon = channel.icon;
    return <Icon className="h-4 w-4" />;
  }
  return <Bell className="h-4 w-4" />;
};

const createClientId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `channel-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const withChannelClientIds = (settings: NotificationSettings): NotificationSettings => ({
  ...settings,
  channels: settings.channels.map((channel) =>
    channel.clientId ? channel : { ...channel, clientId: createClientId() }
  ),
});

const stripChannelClientIds = (settings: NotificationSettings): NotificationSettings => ({
  ...settings,
  channels: settings.channels.map(({ clientId: _clientId, ...channel }) => channel),
});

type NotificationsPanelFormProps = Omit<NotificationsPanelProps, 'settings'> & {
  settings: NotificationSettings;
};

const NotificationsPanelForm = ({
  settings,
  recentNotifications,
  loading,
  saving,
  onSave,
  onTest,
}: NotificationsPanelFormProps) => {
  const [editSettings, setEditSettings] = useState<NotificationSettings>(() =>
    withChannelClientIds(settings)
  );
  const [isDirty, setIsDirty] = useState(false);
  const [showAddChannel, setShowAddChannel] = useState(false);
  const [newChannelType, setNewChannelType] = useState<NotificationChannel['type']>('email');
  const [newChannelConfig, setNewChannelConfig] = useState('');
  const settingsId = settings.id ?? 'notification-settings';
  const previousSettingsIdRef = useRef<string | null>(null);
  const previousSettingsRef = useRef(settings);
  const settingsChangedWhileSavingRef = useRef(false);
  const wasSavingRef = useRef(saving);

  useEffect(() => {
    if (previousSettingsRef.current !== settings && saving) {
      settingsChangedWhileSavingRef.current = true;
    }
    previousSettingsRef.current = settings;
  }, [settings, saving]);

  useEffect(() => {
    const hasNewSettingsId = previousSettingsIdRef.current !== settingsId;
    previousSettingsIdRef.current = settingsId;

    if (hasNewSettingsId) {
      setEditSettings(withChannelClientIds(settings));
      setIsDirty(false);
      return;
    }

    if (!isDirty) {
      setEditSettings(withChannelClientIds(settings));
    }
  }, [settings, settingsId, isDirty]);

  useEffect(() => {
    const justFinishedSaving = wasSavingRef.current && !saving;
    wasSavingRef.current = saving;

    if (justFinishedSaving && settingsChangedWhileSavingRef.current) {
      settingsChangedWhileSavingRef.current = false;
      previousSettingsIdRef.current = settingsId;
      if (!isDirty) {
        setEditSettings(withChannelClientIds(settings));
        setIsDirty(false);
      }
    }
  }, [saving, settings, settingsId, isDirty]);

  const updateEditSettings = (
    next: NotificationSettings | ((prev: NotificationSettings) => NotificationSettings),
  ) => {
    setIsDirty(true);
    setEditSettings(next);
  };

  const handleAddChannel = () => {
    if (!newChannelConfig.trim()) return;

    const newChannel: NotificationChannel = {
      type: newChannelType,
      enabled: true,
      config: {
        [newChannelType === 'email' ? 'address' : 'url']: newChannelConfig.trim(),
      },
      clientId: createClientId(),
    };

    updateEditSettings((prev) => ({
      ...prev,
      channels: [...prev.channels, newChannel],
    }));
    setShowAddChannel(false);
    setNewChannelConfig('');
  };

  const handleRemoveChannel = (index: number) => {
    updateEditSettings((prev) => ({
      ...prev,
      channels: prev.channels.filter((_, i) => i !== index),
    }));
  };

  const handleToggleChannel = (index: number) => {
    updateEditSettings((prev) => {
      const channels = [...prev.channels];
      channels[index] = { ...channels[index], enabled: !channels[index].enabled };
      return { ...prev, channels };
    });
  };

  const handleSave = () => {
    onSave(stripChannelClientIds(editSettings));
  };

  const enabledChannels = editSettings.channels.filter((c) => c.enabled).length;

  return (
    <NotificationsPanelShell
      enabledChannels={enabledChannels}
      loading={loading}
      saving={saving}
      onTest={onTest}
    >
      <>
            {/* Channels List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Notification Channels</Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAddChannel(true)}
                >
                  Add Channel
                </Button>
              </div>

              {showAddChannel && (
                <div className="p-3 border rounded-lg space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="channel-type">Type</Label>
                      <Select
                        id="channel-type"
                        value={newChannelType}
                        onChange={(e) => setNewChannelType(e.target.value as NotificationChannel['type'])}
                      >
                        {CHANNEL_TYPES.map((type) => (
                          <option key={type.value} value={type.value}>
                            {type.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="channel-config">
                        {newChannelType === 'email' ? 'Email Address' : 'Webhook URL'}
                      </Label>
                      <Input
                        id="channel-config"
                        placeholder={newChannelType === 'email' ? 'alerts@example.com' : 'https://...'}
                        value={newChannelConfig}
                        onChange={(e) => setNewChannelConfig(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleAddChannel} disabled={!newChannelConfig.trim()}>
                      Add
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setShowAddChannel(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {editSettings.channels.length === 0 ? (
                <div className="text-sm text-muted-foreground text-center py-4 border rounded-lg">
                  No notification channels configured
                </div>
              ) : (
                <div className="space-y-2">
                  {editSettings.channels.map((channel, index) => (
                    <div
                      key={channel.clientId ?? `channel-${index}`}
                      className={`flex items-center justify-between p-3 rounded-lg border ${
                        channel.enabled ? 'bg-background' : 'bg-muted/30 opacity-60'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        {getChannelIcon(channel.type)}
                        <div>
                          <div className="font-medium capitalize">{channel.type}</div>
                          <div className="text-xs text-muted-foreground font-mono">
                            {Object.values(channel.config)[0] || 'No config'}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={channel.enabled ? 'default' : 'secondary'}>
                          {channel.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleChannel(index)}
                          aria-label={channel.enabled ? 'Disable channel' : 'Enable channel'}
                          title={channel.enabled ? 'Disable' : 'Enable'}
                        >
                          {channel.enabled ? <ToggleRight className="h-4 w-4" /> : <ToggleLeft className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveChannel(index)}
                          aria-label="Remove channel"
                          title="Remove"
                        >
                          <X className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Settings */}
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="alert-threshold">Alert Threshold</Label>
                <Select
                  id="alert-threshold"
                  value={editSettings.alert_threshold}
                  onChange={(e) =>
                    updateEditSettings((prev) => ({
                      ...prev,
                      alert_threshold: e.target.value as NotificationSettings['alert_threshold'],
                    }))
                  }
                >
                  {ALERT_THRESHOLDS.map((threshold) => (
                    <option key={threshold.value} value={threshold.value}>
                      {threshold.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="digest-frequency">Digest Frequency</Label>
                <Select
                  id="digest-frequency"
                  value={editSettings.digest_frequency}
                  onChange={(e) =>
                    updateEditSettings((prev) => ({
                      ...prev,
                      digest_frequency: e.target.value as NotificationSettings['digest_frequency'],
                    }))
                  }
                  disabled={!editSettings.digest_enabled}
                >
                  {DIGEST_FREQUENCIES.map((freq) => (
                    <option key={freq.value} value={freq.value}>
                      {freq.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex items-end">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="digest-enabled"
                    checked={editSettings.digest_enabled}
                    onCheckedChange={(checked) =>
                      updateEditSettings((prev) => ({ ...prev, digest_enabled: checked }))
                    }
                  />
                  <Label htmlFor="digest-enabled">Enable Digest</Label>
                </div>
              </div>
            </div>

            <Button onClick={handleSave} disabled={saving || !isDirty}>
              {saving ? 'Saving...' : 'Save Settings'}
            </Button>

            {/* Recent Notifications */}
            {recentNotifications.length > 0 && (
              <div className="space-y-2">
                <Label>Recent Notifications</Label>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {recentNotifications.slice(0, 5).map((notification) => (
                    <div
                      key={notification.id}
                      className={`flex items-center justify-between p-2 rounded text-sm ${
                        notification.status === 'sent'
                          ? 'bg-green-50 dark:bg-green-900/20'
                          : notification.status === 'failed'
                            ? 'bg-red-50 dark:bg-red-900/20'
                            : 'bg-muted/30'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {getChannelIcon(notification.channel)}
                        <span className="truncate">{notification.message}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            notification.status === 'sent'
                              ? 'default'
                              : notification.status === 'failed'
                                ? 'destructive'
                                : 'secondary'
                          }
                        >
                          {notification.status}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(notification.timestamp)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
      </>
    </NotificationsPanelShell>
  );
};

export default function NotificationsPanel({
  settings,
  recentNotifications,
  loading,
  saving,
  onSave,
  onTest,
}: NotificationsPanelProps) {
  if (loading) {
    return (
      <NotificationsPanelShell enabledChannels={0} loading={loading} saving={saving} onTest={onTest}>
        <div className="text-center text-muted-foreground py-8">Loading...</div>
      </NotificationsPanelShell>
    );
  }

  if (!settings) {
    return (
      <NotificationsPanelShell enabledChannels={0} loading={loading} saving={saving} onTest={onTest}>
        <div className="text-center text-muted-foreground py-8">
          <AlertCircle className="h-12 w-12 mx-auto mb-2" />
          <p>Failed to load notification settings</p>
        </div>
      </NotificationsPanelShell>
    );
  }

  return (
    <NotificationsPanelForm
      settings={settings}
      recentNotifications={recentNotifications}
      loading={loading}
      saving={saving}
      onSave={onSave}
      onTest={onTest}
    />
  );
}
