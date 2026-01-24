'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Settings, Save, RefreshCw, Shield, Database, Server, Key } from 'lucide-react';
import { api } from '@/lib/api-client';

interface SetupStatus {
  is_configured: boolean;
  auth_mode: string;
  database_connected: boolean;
  version?: string;
}

interface ConfigSection {
  title: string;
  icon: React.ReactNode;
  fields: ConfigField[];
}

interface ConfigField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'password';
  description?: string;
  sensitive?: boolean;
}

const maskConfigValue = (
  value: unknown,
  isSensitiveKey: (key: string) => boolean
): unknown => {
  if (Array.isArray(value)) {
    return value.map((item) => maskConfigValue(item, isSensitiveKey));
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, val]) => {
        if (isSensitiveKey(key)) {
          if (val === null || val === undefined || val === '') {
            return [key, val];
          }
          return [key, '********'];
        }
        return [key, maskConfigValue(val, isSensitiveKey)];
      })
    );
  }

  return value;
};

export default function ConfigPage() {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [originalConfig, setOriginalConfig] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');

    const [statusData, configData] = await Promise.allSettled([
      api.getSetupStatus(),
      api.getConfig(),
    ]);

    if (statusData.status === 'fulfilled') {
      setStatus(statusData.value as SetupStatus);
    } else {
      console.error('Failed to load status:', statusData.reason);
    }

    if (configData.status === 'fulfilled' && configData.value) {
      setConfig(configData.value as Record<string, unknown>);
      setOriginalConfig(configData.value as Record<string, unknown>);
    } else if (configData.status === 'rejected') {
      console.error('Failed to load configuration:', configData.reason);
      setError(
        configData.reason instanceof Error
          ? configData.reason.message
          : 'Failed to load configuration'
      );
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');

      await api.updateConfig(config);
      setSuccess('Configuration saved successfully. Some changes may require a server restart.');
      setOriginalConfig(config);
    } catch (err: unknown) {
      console.error('Failed to save configuration:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setConfig(originalConfig);
    setError('');
    setSuccess('');
  };

  const updateConfigValue = (key: string, value: unknown) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value,
    }));
    setSuccess('');
  };

  const hasChanges = JSON.stringify(config) !== JSON.stringify(originalConfig);

  // Define configuration sections
  const configSections: ConfigSection[] = [
    {
      title: 'Authentication',
      icon: <Shield className="h-5 w-5" />,
      fields: [
        { key: 'auth_mode', label: 'Auth Mode', type: 'text', description: 'single_user or multi_user' },
        { key: 'jwt_secret_key', label: 'JWT Secret', type: 'password', sensitive: true },
        { key: 'access_token_expire_minutes', label: 'Token Expiry (minutes)', type: 'number' },
      ],
    },
    {
      title: 'Database',
      icon: <Database className="h-5 w-5" />,
      fields: [
        { key: 'database_url', label: 'Database URL', type: 'text', description: 'SQLite or PostgreSQL connection string' },
        { key: 'media_db_path', label: 'Media DB Path', type: 'text' },
      ],
    },
    {
      title: 'Server',
      icon: <Server className="h-5 w-5" />,
      fields: [
        { key: 'host', label: 'Host', type: 'text' },
        { key: 'port', label: 'Port', type: 'number' },
        { key: 'debug', label: 'Debug Mode', type: 'boolean' },
        { key: 'log_level', label: 'Log Level', type: 'text', description: 'DEBUG, INFO, WARNING, ERROR' },
      ],
    },
    {
      title: 'API Keys',
      icon: <Key className="h-5 w-5" />,
      fields: [
        { key: 'api_key_length', label: 'API Key Length', type: 'number' },
        { key: 'api_key_prefix', label: 'API Key Prefix', type: 'text' },
      ],
    },
  ];

  const sensitiveKeySet = new Set(
    configSections
      .flatMap((section) => section.fields)
      .filter((field) => field.sensitive)
      .map((field) => field.key.toLowerCase())
  );

  const isSensitiveKey = (key: string) => {
    const normalized = key.toLowerCase();
    if (sensitiveKeySet.has(normalized)) return true;
    if (normalized === 'api_key' || normalized.endsWith('_api_key')) return true;
    if (normalized.includes('secret') || normalized.includes('password')) return true;
    return false;
  };

  const maskedConfig = maskConfigValue(config, isSensitiveKey);

  const renderField = (field: ConfigField) => {
    const value = config[field.key];
    const inputValue =
      typeof value === 'string' || typeof value === 'number'
        ? value
        : value == null
          ? ''
          : String(value);

    if (field.type === 'boolean') {
      return (
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id={field.key}
            checked={Boolean(value)}
            onChange={(e) => updateConfigValue(field.key, e.target.checked)}
            className="h-4 w-4 rounded border-primary"
          />
          <Label htmlFor={field.key}>{field.label}</Label>
        </div>
      );
    }

    return (
      <div className="space-y-2">
        <Label htmlFor={field.key}>{field.label}</Label>
        <Input
          id={field.key}
          type={field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : 'text'}
          value={inputValue}
          onChange={(e) => {
            if (field.type === 'number') {
              if (e.target.value === '') {
                updateConfigValue(field.key, '');
                setFieldErrors((prev) => ({ ...prev, [field.key]: '' }));
                return;
              }
              const parsed = parseInt(e.target.value, 10);
              if (Number.isNaN(parsed)) {
                setFieldErrors((prev) => ({ ...prev, [field.key]: 'Must be a valid number' }));
                return;
              }
              updateConfigValue(field.key, parsed);
              setFieldErrors((prev) => ({ ...prev, [field.key]: '' }));
              return;
            }
            updateConfigValue(field.key, e.target.value);
          }}
          placeholder={field.sensitive ? '********' : undefined}
        />
        {field.description && (
          <p className="text-xs text-muted-foreground">{field.description}</p>
        )}
        {fieldErrors[field.key] && (
          <p className="text-xs text-red-600">{fieldErrors[field.key]}</p>
        )}
      </div>
    );
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Configuration</h1>
                <p className="text-muted-foreground">
                  Manage system settings and configuration
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={loadData} disabled={loading}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
                <Button variant="outline" onClick={handleReset} disabled={!hasChanges || saving}>
                  Reset
                </Button>
                <Button onClick={handleSave} disabled={!hasChanges || saving}>
                  <Save className="mr-2 h-4 w-4" />
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="mb-6 bg-green-50 border-green-200">
                <AlertDescription className="text-green-800">{success}</AlertDescription>
              </Alert>
            )}

            {/* Status Card */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <Settings className="h-8 w-8 text-primary mt-1" />
                  <div className="flex-1">
                    <h3 className="font-semibold">System Status</h3>
                    <div className="flex flex-wrap gap-4 mt-2">
                      {status ? (
                        <>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Configured:</span>
                            <Badge variant={status.is_configured ? 'default' : 'destructive'}>
                              {status.is_configured ? 'Yes' : 'No'}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Auth Mode:</span>
                            <Badge variant="outline">{status.auth_mode}</Badge>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Database:</span>
                            <Badge variant={status.database_connected ? 'default' : 'destructive'}>
                              {status.database_connected ? 'Connected' : 'Disconnected'}
                            </Badge>
                          </div>
                          {status.version && (
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-muted-foreground">Version:</span>
                              <Badge variant="secondary">{status.version}</Badge>
                            </div>
                          )}
                        </>
                      ) : (
                        <span className="text-sm text-muted-foreground">Loading status...</span>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Warning for sensitive settings */}
            <Alert className="mb-6 bg-yellow-50 border-yellow-200">
              <AlertDescription className="text-yellow-800">
                <strong>Warning:</strong> Some settings contain sensitive information and may require a server restart after changes.
                Be careful when modifying authentication or database settings.
              </AlertDescription>
            </Alert>

            {loading ? (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center text-muted-foreground py-8">Loading configuration...</div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 lg:grid-cols-2">
                {configSections.map((section) => (
                  <Card key={section.title}>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        {section.icon}
                        {section.title}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {section.fields.map((field) => (
                        <div key={field.key}>{renderField(field)}</div>
                      ))}
                    </CardContent>
                  </Card>
                ))}

                {/* Raw Config View */}
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle>Raw Configuration</CardTitle>
                    <CardDescription>
                      View all configuration values as JSON
                    </CardDescription>
                  </CardHeader>
                <CardContent>
                  <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm">
                      {JSON.stringify(maskedConfig, null, 2)}
                  </pre>
                </CardContent>
              </Card>
              </div>
            )}

            {hasChanges && (
              <div className="mt-6 p-4 bg-muted rounded-lg flex items-center justify-between">
                <span className="text-sm">
                  You have unsaved changes
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleReset}>
                    Discard
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={saving}>
                    {saving ? 'Saving...' : 'Save Changes'}
                  </Button>
                </div>
              </div>
            )}
          </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
