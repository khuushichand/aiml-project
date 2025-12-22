'use client';

import { useCallback, useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useConfirm } from '@/components/ui/confirm-dialog';
import {
  Activity, RefreshCw, Bell, Eye, AlertTriangle, CheckCircle, Clock, Server,
  Plus, Trash2, Check, X
} from 'lucide-react';
import { api } from '@/lib/api-client';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area
} from 'recharts';

interface Metric {
  name: string;
  value: string | number;
  unit?: string;
  status?: 'healthy' | 'warning' | 'critical';
}

interface Watchlist {
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

interface SystemAlert {
  id: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  source?: string;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_at?: string;
  acknowledged_by?: string;
}

interface MetricsHistoryPoint {
  time: string;
  cpu: number;
  memory: number;
}

type SystemHealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown';
type SystemStatusKey = 'api' | 'database' | 'llm' | 'rag';

interface ApiHealthResponse {
  status?: string;
  checks?: {
    database?: { status?: string };
  };
}

interface ServiceHealthResponse {
  status?: string;
}

interface HealthMetricsResponse {
  cpu?: { percent?: number };
  memory?: { percent?: number };
}

interface SystemStatusItem {
  key: SystemStatusKey;
  label: string;
  status: SystemHealthStatus;
  detail: string;
}

const METRICS_HISTORY_MAX_POINTS = 288;
const METRICS_HISTORY_POLL_MS = 5 * 60 * 1000;
const DEFAULT_SYSTEM_STATUS: SystemStatusItem[] = [
  { key: 'api', label: 'API Server', status: 'unknown', detail: 'Checking...' },
  { key: 'database', label: 'Database', status: 'unknown', detail: 'Checking...' },
  { key: 'llm', label: 'LLM Services', status: 'unknown', detail: 'Checking...' },
  { key: 'rag', label: 'RAG Service', status: 'unknown', detail: 'Checking...' },
];
const SYSTEM_STATUS_DETAILS: Record<SystemStatusKey, Record<SystemHealthStatus, string>> = {
  api: {
    healthy: 'Operational',
    warning: 'Degraded',
    critical: 'Unhealthy',
    unknown: 'Unknown',
  },
  database: {
    healthy: 'Connected',
    warning: 'Degraded',
    critical: 'Unreachable',
    unknown: 'Unknown',
  },
  llm: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unknown',
  },
  rag: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unknown',
  },
};

const normalizeHealthStatus = (status?: string): SystemHealthStatus => {
  const value = (status || '').toLowerCase();
  if (['ok', 'healthy', 'ready', 'alive'].includes(value)) {
    return 'healthy';
  }
  if (['degraded', 'warning'].includes(value)) {
    return 'warning';
  }
  if (['unhealthy', 'error', 'critical', 'not_ready'].includes(value)) {
    return 'critical';
  }
  return 'unknown';
};

export default function MonitoringPage() {
  const confirm = useConfirm();
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [metricsHistory, setMetricsHistory] = useState<MetricsHistoryPoint[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatusItem[]>(DEFAULT_SYSTEM_STATUS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Create watchlist dialog
  const [showCreateWatchlist, setShowCreateWatchlist] = useState(false);
  const [newWatchlist, setNewWatchlist] = useState({
    name: '',
    description: '',
    target: '',
    type: 'resource',
    threshold: 80,
  });

  const appendMetricsHistory = useCallback((cpu: number, memory: number) => {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMetricsHistory((prev) => {
      const next = [...prev, { time, cpu, memory }];
      if (next.length <= METRICS_HISTORY_MAX_POINTS) {
        return next;
      }
      return next.slice(-METRICS_HISTORY_MAX_POINTS);
    });
  }, []);

  const loadMetricsHistorySample = useCallback(async () => {
    try {
      const health = (await api.getHealthMetrics()) as HealthMetricsResponse;
      const cpu = Number(health?.cpu?.percent ?? 0);
      const memory = Number(health?.memory?.percent ?? 0);
      appendMetricsHistory(cpu, memory);
    } catch (err: unknown) {
      console.warn('Failed to load health metrics history:', err);
    }
  }, [appendMetricsHistory]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const [
        metricsData,
        watchlistsData,
        alertsData,
        healthData,
        llmHealthData,
        ragHealthData,
      ] = await Promise.allSettled([
        api.getMetrics(),
        api.getWatchlists(),
        api.getAlerts(),
        api.getHealth(),
        api.getLlmHealth(),
        api.getRagHealth(),
      ]);

      [
        { name: 'metrics', result: metricsData },
        { name: 'watchlists', result: watchlistsData },
        { name: 'alerts', result: alertsData },
        { name: 'health', result: healthData },
        { name: 'llmHealth', result: llmHealthData },
        { name: 'ragHealth', result: ragHealthData },
      ].forEach(({ name, result }) => {
        if (result.status === 'rejected') {
          console.warn(`Failed to load ${name}:`, result.reason);
        }
      });

      // Process metrics
      if (metricsData.status === 'fulfilled' && metricsData.value) {
        const rawMetrics = metricsData.value;
        const metricsArray: Metric[] = [];
        if (typeof rawMetrics === 'object') {
          Object.entries(rawMetrics).forEach(([key, value]) => {
            if (typeof value === 'number' || typeof value === 'string') {
              metricsArray.push({
                name: key,
                value,
                status: typeof value === 'number' && value > 90 ? 'critical' :
                        typeof value === 'number' && value > 70 ? 'warning' : 'healthy'
              });
            }
          });
        }
        setMetrics(metricsArray);
      }

      // Process watchlists
      if (watchlistsData.status === 'fulfilled') {
        setWatchlists(Array.isArray(watchlistsData.value) ? watchlistsData.value : []);
      }

      // Process alerts
      if (alertsData.status === 'fulfilled') {
        setAlerts(Array.isArray(alertsData.value) ? alertsData.value : []);
      }

      const healthAvailable = healthData.status === 'fulfilled';
      const llmAvailable = llmHealthData.status === 'fulfilled';
      const ragAvailable = ragHealthData.status === 'fulfilled';
      const healthPayload = healthAvailable ? (healthData.value as ApiHealthResponse) : undefined;
      const llmPayload = llmAvailable ? (llmHealthData.value as ServiceHealthResponse) : undefined;
      const ragPayload = ragAvailable ? (ragHealthData.value as ServiceHealthResponse) : undefined;
      const apiStatus = healthAvailable
        ? normalizeHealthStatus(healthPayload?.status)
        : 'unknown';
      const dbStatus = healthAvailable
        ? normalizeHealthStatus(healthPayload?.checks?.database?.status)
        : 'unknown';
      const llmStatus = llmAvailable
        ? normalizeHealthStatus(llmPayload?.status)
        : 'unknown';
      const ragStatus = ragAvailable
        ? normalizeHealthStatus(ragPayload?.status)
        : 'unknown';
      const statusDetail = (
        key: SystemStatusKey,
        status: SystemHealthStatus,
        available: boolean
      ) => {
        if (!available) {
          return 'Unavailable';
        }
        return SYSTEM_STATUS_DETAILS[key][status];
      };
      setSystemStatus([
        {
          key: 'api',
          label: 'API Server',
          status: apiStatus,
          detail: statusDetail('api', apiStatus, healthAvailable),
        },
        {
          key: 'database',
          label: 'Database',
          status: dbStatus,
          detail: statusDetail('database', dbStatus, healthAvailable),
        },
        {
          key: 'llm',
          label: 'LLM Services',
          status: llmStatus,
          detail: statusDetail('llm', llmStatus, llmAvailable),
        },
        {
          key: 'rag',
          label: 'RAG Service',
          status: ragStatus,
          detail: statusDetail('rag', ragStatus, ragAvailable),
        },
      ]);

      void loadMetricsHistorySample();
    } catch (err: unknown) {
      console.error('Failed to load monitoring data:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to load monitoring data');
    } finally {
      setLoading(false);
    }
  }, [loadMetricsHistorySample]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    loadMetricsHistorySample();
    const intervalId = window.setInterval(loadMetricsHistorySample, METRICS_HISTORY_POLL_MS);
    return () => window.clearInterval(intervalId);
  }, [loadMetricsHistorySample]);

  const handleCreateWatchlist = async () => {
    if (!newWatchlist.name || !newWatchlist.target) {
      setError('Name and target are required');
      return;
    }

    try {
      setError('');
      await api.createWatchlist(newWatchlist);
      setSuccess('Watchlist created successfully');
      setShowCreateWatchlist(false);
      setNewWatchlist({ name: '', description: '', target: '', type: 'resource', threshold: 80 });
      loadData();
    } catch (err: unknown) {
      console.error('Failed to create watchlist:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to create watchlist');
    }
  };

  const handleDeleteWatchlist = async (watchlist: Watchlist) => {
    const confirmed = await confirm({
      title: 'Delete Watchlist',
      message: `Delete watchlist "${watchlist.name}"?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.deleteWatchlist(watchlist.id);
      setSuccess('Watchlist deleted');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to delete watchlist:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to delete watchlist');
    }
  };

  const handleAcknowledgeAlert = async (alert: SystemAlert) => {
    try {
      setError('');
      await api.acknowledgeAlert(alert.id);
      setSuccess('Alert acknowledged');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to acknowledge alert:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to acknowledge alert');
    }
  };

  const handleDismissAlert = async (alert: SystemAlert) => {
    const confirmed = await confirm({
      title: 'Dismiss Alert',
      message: 'Dismiss this alert?',
      confirmText: 'Dismiss',
      variant: 'warning',
      icon: 'warning',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.dismissAlert(alert.id);
      setSuccess('Alert dismissed');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to dismiss alert:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to dismiss alert');
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'healthy':
      case 'active':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'critical':
      case 'error':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <Badge variant="destructive">Critical</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      case 'warning':
        return <Badge className="bg-yellow-500">Warning</Badge>;
      default:
        return <Badge variant="secondary">Info</Badge>;
    }
  };

  const getSystemStatusIcon = (status: SystemHealthStatus) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-8 w-8 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="h-8 w-8 text-yellow-500" />;
      case 'critical':
        return <AlertTriangle className="h-8 w-8 text-red-500" />;
      default:
        return <Clock className="h-8 w-8 text-muted-foreground" />;
    }
  };

  const formatTimestamp = (ts?: string) => {
    if (!ts) return '-';
    return new Date(ts).toLocaleString();
  };

  const activeAlerts = alerts.filter((a) => !a.acknowledged);
  const acknowledgedAlerts = alerts.filter((a) => a.acknowledged);

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Monitoring</h1>
                <p className="text-muted-foreground">
                  System health, metrics, and alerts
                </p>
              </div>
              <Button variant="outline" onClick={loadData} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
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

            {/* Active Alerts Banner */}
            {activeAlerts.length > 0 && (
              <Alert variant="destructive" className="mb-6">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {activeAlerts.length} active alert{activeAlerts.length !== 1 ? 's' : ''} require attention
                </AlertDescription>
              </Alert>
            )}

            {/* Metrics Chart */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  System Metrics (24h)
                </CardTitle>
                <CardDescription>CPU, memory usage, and request volume over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={metricsHistory}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="time" className="text-xs" />
                      <YAxis className="text-xs" />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--background))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                        }}
                      />
                      <Area type="monotone" dataKey="cpu" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} name="CPU %" />
                      <Area type="monotone" dataKey="memory" stroke="#10b981" fill="#10b981" fillOpacity={0.2} name="Memory %" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Metrics Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6">
              {loading ? (
                <Card className="col-span-full">
                  <CardContent className="pt-6">
                    <div className="text-center text-muted-foreground">Loading metrics...</div>
                  </CardContent>
                </Card>
              ) : metrics.length === 0 ? (
                <Card className="col-span-full">
                  <CardContent className="pt-6">
                    <div className="text-center text-muted-foreground">
                      No metrics available. The server may not expose metrics.
                    </div>
                  </CardContent>
                </Card>
              ) : (
                metrics.slice(0, 8).map((metric, index) => (
                  <Card key={index}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">
                        {metric.name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                      </CardTitle>
                      {getStatusIcon(metric.status)}
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {typeof metric.value === 'number' ? metric.value.toLocaleString() : metric.value}
                        {metric.unit && <span className="text-sm font-normal text-muted-foreground ml-1">{metric.unit}</span>}
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              {/* Alerts Section */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Bell className="h-5 w-5" />
                      Alerts
                    </CardTitle>
                    <CardDescription>
                      {activeAlerts.length} active, {acknowledgedAlerts.length} acknowledged
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-center text-muted-foreground py-8">Loading...</div>
                  ) : alerts.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      <CheckCircle className="h-12 w-12 mx-auto mb-2 text-green-500" />
                      <p>No alerts - system is healthy</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {alerts.slice(0, 10).map((alert) => (
                        <div
                          key={alert.id}
                          className={`flex items-start justify-between p-3 rounded-lg border ${
                            alert.acknowledged ? 'bg-muted/30 opacity-60' : 'bg-background'
                          }`}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              {getSeverityBadge(alert.severity)}
                              {alert.acknowledged && (
                                <Badge variant="outline" className="text-xs">
                                  <Check className="mr-1 h-3 w-3" />
                                  Acknowledged
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm font-medium truncate">{alert.message}</p>
                            <p className="text-xs text-muted-foreground">
                              {alert.source && `${alert.source} • `}
                              {formatTimestamp(alert.timestamp)}
                            </p>
                          </div>
                          {!alert.acknowledged && (
                            <div className="flex gap-1 ml-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleAcknowledgeAlert(alert)}
                                title="Acknowledge"
                              >
                                <Check className="h-4 w-4 text-green-500" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDismissAlert(alert)}
                                title="Dismiss"
                              >
                                <X className="h-4 w-4 text-red-500" />
                              </Button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Watchlists Section */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Eye className="h-5 w-5" />
                      Watchlists
                    </CardTitle>
                    <CardDescription>
                      {watchlists.length} watchlist{watchlists.length !== 1 ? 's' : ''} configured
                    </CardDescription>
                  </div>
                  <Dialog open={showCreateWatchlist} onOpenChange={setShowCreateWatchlist}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="mr-2 h-4 w-4" />
                        Add
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create Watchlist</DialogTitle>
                        <DialogDescription>
                          Configure a new resource or metric to monitor
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="watchName">Name</Label>
                          <Input
                            id="watchName"
                            placeholder="e.g., API Response Time"
                            value={newWatchlist.name}
                            onChange={(e) => setNewWatchlist({ ...newWatchlist, name: e.target.value })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="watchDescription">Description</Label>
                          <Input
                            id="watchDescription"
                            placeholder="What this watchlist monitors..."
                            value={newWatchlist.description}
                            onChange={(e) => setNewWatchlist({ ...newWatchlist, description: e.target.value })}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="watchTarget">Target</Label>
                          <Input
                            id="watchTarget"
                            placeholder="e.g., /api/v1/chat, cpu_usage"
                            value={newWatchlist.target}
                            onChange={(e) => setNewWatchlist({ ...newWatchlist, target: e.target.value })}
                          />
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="watchType">Type</Label>
                            <select
                              id="watchType"
                              value={newWatchlist.type}
                              onChange={(e) => setNewWatchlist({ ...newWatchlist, type: e.target.value })}
                              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            >
                              <option value="resource">Resource</option>
                              <option value="metric">Metric</option>
                              <option value="endpoint">Endpoint</option>
                              <option value="user">User Activity</option>
                            </select>
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="watchThreshold">Threshold (%)</Label>
                            <Input
                              id="watchThreshold"
                              type="number"
                              min="0"
                              max="100"
                              value={newWatchlist.threshold}
                              onChange={(e) => setNewWatchlist({ ...newWatchlist, threshold: parseInt(e.target.value, 10) || 80 })}
                            />
                          </div>
                        </div>
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setShowCreateWatchlist(false)}>Cancel</Button>
                        <Button onClick={handleCreateWatchlist}>Create Watchlist</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-center text-muted-foreground py-8">Loading...</div>
                  ) : watchlists.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      <Eye className="h-12 w-12 mx-auto mb-2 opacity-50" />
                      <p>No watchlists configured</p>
                      <p className="text-sm mt-1">Create one to start monitoring resources</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {watchlists.map((watchlist) => (
                        <div
                          key={watchlist.id}
                          className="flex items-start justify-between p-3 rounded-lg border"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              {getStatusIcon(watchlist.status)}
                              <span className="font-medium">{watchlist.name}</span>
                              <Badge variant="outline" className="text-xs">{watchlist.type}</Badge>
                            </div>
                            <p className="text-sm text-muted-foreground truncate">
                              Target: <code className="bg-muted px-1 rounded">{watchlist.target}</code>
                            </p>
                            {watchlist.last_checked && (
                              <p className="text-xs text-muted-foreground">
                                Last checked: {formatTimestamp(watchlist.last_checked)}
                              </p>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteWatchlist(watchlist)}
                            title="Delete watchlist"
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* System Status */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Server className="h-5 w-5" />
                  System Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-4">
                  {systemStatus.map((item) => (
                    <div
                      key={item.key}
                      className="flex items-center gap-3 p-4 rounded-lg bg-muted/50"
                    >
                      {getSystemStatusIcon(item.status)}
                      <div>
                        <div className="font-semibold">{item.label}</div>
                        <div className="text-sm text-muted-foreground">{item.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
