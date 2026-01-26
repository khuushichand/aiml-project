import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Bell, Mail, Webhook, Send, Check, X, AlertCircle, MessageSquare } from 'lucide-react';
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

export default function NotificationsPanel({
  settings,
  recentNotifications,
  loading,
  saving,
  onSave,
  onTest,
}: NotificationsPanelProps) {
  const [editSettings, setEditSettings] = useState<NotificationSettings | null>(settings);
  const [showAddChannel, setShowAddChannel] = useState(false);
  const [newChannelType, setNewChannelType] = useState<NotificationChannel['type']>('email');
  const [newChannelConfig, setNewChannelConfig] = useState('');

  // Initialize edit settings when settings prop changes
  if (settings && !editSettings) {
    setEditSettings(settings);
  }

  const handleAddChannel = () => {
    if (!editSettings || !newChannelConfig.trim()) return;

    const newChannel: NotificationChannel = {
      type: newChannelType,
      enabled: true,
      config: {
        [newChannelType === 'email' ? 'address' : 'url']: newChannelConfig.trim(),
      },
    };

    setEditSettings({
      ...editSettings,
      channels: [...editSettings.channels, newChannel],
    });
    setShowAddChannel(false);
    setNewChannelConfig('');
  };

  const handleRemoveChannel = (index: number) => {
    if (!editSettings) return;
    setEditSettings({
      ...editSettings,
      channels: editSettings.channels.filter((_, i) => i !== index),
    });
  };

  const handleToggleChannel = (index: number) => {
    if (!editSettings) return;
    const channels = [...editSettings.channels];
    channels[index] = { ...channels[index], enabled: !channels[index].enabled };
    setEditSettings({ ...editSettings, channels });
  };

  const handleSave = () => {
    if (editSettings) {
      onSave(editSettings);
    }
  };

  const enabledChannels = editSettings?.channels.filter((c) => c.enabled).length ?? 0;

  return (
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
        {loading ? (
          <div className="text-center text-muted-foreground py-8">Loading...</div>
        ) : !editSettings ? (
          <div className="text-center text-muted-foreground py-8">
            <AlertCircle className="h-12 w-12 mx-auto mb-2" />
            <p>Failed to load notification settings</p>
          </div>
        ) : (
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
                      key={`channel-${index}`}
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
                          title={channel.enabled ? 'Disable' : 'Enable'}
                        >
                          {channel.enabled ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveChannel(index)}
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
                    setEditSettings({
                      ...editSettings,
                      alert_threshold: e.target.value as NotificationSettings['alert_threshold'],
                    })
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
                    setEditSettings({
                      ...editSettings,
                      digest_frequency: e.target.value as NotificationSettings['digest_frequency'],
                    })
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
                  <input
                    type="checkbox"
                    id="digest-enabled"
                    checked={editSettings.digest_enabled}
                    onChange={(e) =>
                      setEditSettings({ ...editSettings, digest_enabled: e.target.checked })
                    }
                    className="h-4 w-4"
                  />
                  <Label htmlFor="digest-enabled">Enable Digest</Label>
                </div>
              </div>
            </div>

            <Button onClick={handleSave} disabled={saving}>
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
        )}
      </CardContent>
    </Card>
  );
}
