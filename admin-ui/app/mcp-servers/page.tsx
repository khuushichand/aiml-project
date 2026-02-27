'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Server, Activity, Wrench, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api, ApiError } from '@/lib/api-client';

interface MCPModule {
  name: string;
  description?: string;
  tools_count?: number;
  resources_count?: number;
  prompts_count?: number;
  status?: string;
}

interface MCPTool {
  name: string;
  description?: string;
  module?: string;
  input_schema?: Record<string, unknown>;
}

interface MCPHealthResult {
  module: string;
  status: string;
  message?: string;
  latency_ms?: number;
}

interface MCPStatus {
  status?: string;
  connections?: {
    active_websocket?: number;
    active_http?: number;
    total?: number;
  };
  modules?: string[] | MCPModule[];
  uptime_seconds?: number;
}

interface MCPMetrics {
  modules?: Record<string, {
    calls?: number;
    errors?: number;
    avg_latency_ms?: number;
  }>;
  requests?: Record<string, unknown>;
}

export default function MCPServersPage() {
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [modules, setModules] = useState<MCPModule[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [health, setHealth] = useState<MCPHealthResult[]>([]);
  const [metrics, setMetrics] = useState<MCPMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'modules' | 'tools'>('overview');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const results = await Promise.allSettled([
        api.getMCPStatus(),
        api.getMCPModules(),
        api.getMCPTools(),
        api.getMCPModulesHealth(),
        api.getMCPMetrics(),
      ]);

      if (results[0].status === 'fulfilled') setMcpStatus(results[0].value as MCPStatus);
      if (results[1].status === 'fulfilled') {
        const modResult = results[1].value;
        const modList = Array.isArray(modResult) ? modResult : (modResult as Record<string, unknown>)?.modules;
        setModules(Array.isArray(modList) ? modList as MCPModule[] : []);
      }
      if (results[2].status === 'fulfilled') {
        const toolResult = results[2].value;
        const toolList = Array.isArray(toolResult) ? toolResult : (toolResult as Record<string, unknown>)?.tools;
        setTools(Array.isArray(toolList) ? toolList as MCPTool[] : []);
      }
      if (results[3].status === 'fulfilled') {
        const healthResult = results[3].value;
        const healthList = Array.isArray(healthResult) ? healthResult : (healthResult as Record<string, unknown>)?.results;
        setHealth(Array.isArray(healthList) ? healthList as MCPHealthResult[] : []);
      }
      if (results[4].status === 'fulfilled') setMetrics(results[4].value as MCPMetrics);

      const failures = results.filter(r => r.status === 'rejected');
      if (failures.length === results.length) {
        setError('Failed to connect to MCP server. Is it running?');
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load MCP data';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getStatusIcon = (statusStr: string | undefined) => {
    switch (statusStr?.toLowerCase()) {
      case 'healthy':
      case 'ok':
      case 'running':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'degraded':
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'error':
      case 'unhealthy':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Activity className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const formatUptime = (seconds: number | undefined) => {
    if (!seconds) return '-';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8 space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">MCP Servers</h1>
              <p className="text-muted-foreground">Model Context Protocol server status, modules, and tool catalog</p>
            </div>
            <AccessibleIconButton
              icon={RefreshCw}
              label="Refresh"
              onClick={loadData}
              disabled={loading}
              className={loading ? 'animate-spin' : ''}
            />
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Status Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Status</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  {getStatusIcon(mcpStatus?.status)}
                  <span className="text-xl font-bold capitalize">{mcpStatus?.status || 'Unknown'}</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Connections</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold">
                  {mcpStatus?.connections?.total ?? '-'}
                </div>
                <p className="text-xs text-muted-foreground">
                  WS: {mcpStatus?.connections?.active_websocket ?? 0} | HTTP: {mcpStatus?.connections?.active_http ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Modules</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold">{modules.length}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Uptime</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold">{formatUptime(mcpStatus?.uptime_seconds)}</div>
              </CardContent>
            </Card>
          </div>

          {/* Tab Navigation */}
          <div className="flex gap-2 border-b pb-2">
            <Button variant={activeTab === 'overview' ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab('overview')}>
              <Server className="h-4 w-4 mr-2" />
              Health
            </Button>
            <Button variant={activeTab === 'modules' ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab('modules')}>
              <Activity className="h-4 w-4 mr-2" />
              Modules ({modules.length})
            </Button>
            <Button variant={activeTab === 'tools' ? 'default' : 'ghost'} size="sm" onClick={() => setActiveTab('tools')}>
              <Wrench className="h-4 w-4 mr-2" />
              Tools ({tools.length})
            </Button>
          </div>

          {/* Health Tab */}
          {activeTab === 'overview' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Module Health</CardTitle>
                <CardDescription>Health status of each MCP module</CardDescription>
              </CardHeader>
              <CardContent>
                {health.length === 0 ? (
                  <EmptyState
                    icon={Server}
                    title="No Health Data"
                    description="Health check data is not yet available."
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Module</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Latency</TableHead>
                        <TableHead>Message</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {health.map((h, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-medium">{h.module}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {getStatusIcon(h.status)}
                              <span className="capitalize">{h.status}</span>
                            </div>
                          </TableCell>
                          <TableCell>{h.latency_ms != null ? `${h.latency_ms}ms` : '-'}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{h.message || '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}

          {/* Modules Tab */}
          {activeTab === 'modules' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Active Modules</CardTitle>
                <CardDescription>MCP modules registered with the server</CardDescription>
              </CardHeader>
              <CardContent>
                {modules.length === 0 ? (
                  <EmptyState icon={Activity} title="No Modules" description="No MCP modules are currently registered." />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Module</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Tools</TableHead>
                        <TableHead>Metrics</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {modules.map((mod, i) => {
                        const modName = typeof mod === 'string' ? mod : mod.name;
                        const modDesc = typeof mod === 'string' ? '' : (mod.description || '');
                        const modMetrics = metrics?.modules?.[modName];
                        return (
                          <TableRow key={i}>
                            <TableCell className="font-medium">{modName}</TableCell>
                            <TableCell className="text-xs text-muted-foreground">{modDesc}</TableCell>
                            <TableCell>{typeof mod !== 'string' ? mod.tools_count ?? '-' : '-'}</TableCell>
                            <TableCell className="text-xs">
                              {modMetrics ? (
                                <span>
                                  {modMetrics.calls ?? 0} calls, {modMetrics.errors ?? 0} errors
                                  {modMetrics.avg_latency_ms != null && `, ~${modMetrics.avg_latency_ms}ms`}
                                </span>
                              ) : '-'}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}

          {/* Tools Tab */}
          {activeTab === 'tools' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Tool Catalog</CardTitle>
                <CardDescription>All tools available through the MCP server</CardDescription>
              </CardHeader>
              <CardContent>
                {tools.length === 0 ? (
                  <EmptyState icon={Wrench} title="No Tools" description="No tools are currently registered." />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tool Name</TableHead>
                        <TableHead>Module</TableHead>
                        <TableHead>Description</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tools.map((tool, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-mono text-sm">{tool.name}</TableCell>
                          <TableCell><Badge variant="outline">{tool.module || '-'}</Badge></TableCell>
                          <TableCell className="text-xs text-muted-foreground max-w-md truncate">{tool.description || '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
