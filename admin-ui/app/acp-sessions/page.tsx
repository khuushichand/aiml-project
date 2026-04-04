'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { ExportMenu } from '@/components/ui/export-menu';
import { exportData, type ExportFormat } from '@/lib/export';
import { RefreshCw, MessageSquare, XCircle, Wifi, WifiOff } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api, ApiError } from '@/lib/api-client';
import { formatDateTime, formatTokens } from '@/lib/format';

interface ACPSession {
  session_id: string;
  user_id: number;
  agent_type: string;
  name: string;
  status: string;
  created_at: string;
  last_activity_at: string | null;
  message_count: number;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  tags: string[];
  has_websocket: boolean;
  agent_budget?: number | null;
}

interface ACPSessionListResponse {
  sessions: ACPSession[];
  total: number;
}

export default function ACPSessionsPage() {
  const [sessions, setSessions] = useState<ACPSession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusFilterDraft, setStatusFilterDraft] = useState<string>('');
  const [agentTypeFilterDraft, setAgentTypeFilterDraft] = useState('');
  const [userIdFilterDraft, setUserIdFilterDraft] = useState('');
  const [appliedFilters, setAppliedFilters] = useState<{
    status: string;
    agentType: string;
    userId: string;
  }>({
    status: '',
    agentType: '',
    userId: '',
  });
  const [autoRefresh, setAutoRefresh] = useState(true);
  const confirm = useConfirm();
  const toast = useToast();

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string> = {};
      if (appliedFilters.status) params.status = appliedFilters.status;
      if (appliedFilters.agentType) params.agent_type = appliedFilters.agentType;
      if (appliedFilters.userId) params.user_id = appliedFilters.userId;
      const response = await api.getACPSessions(params) as ACPSessionListResponse;
      setSessions(response.sessions || []);
      setTotal(response.total || 0);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load ACP sessions';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [appliedFilters]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Auto-refresh every 15 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => { void loadSessions(); }, 15_000);
    return () => clearInterval(id);
  }, [autoRefresh, loadSessions]);

  const handleApplyFilters = useCallback(() => {
    setAppliedFilters({
      status: statusFilterDraft,
      agentType: agentTypeFilterDraft.trim(),
      userId: userIdFilterDraft.trim(),
    });
  }, [statusFilterDraft, agentTypeFilterDraft, userIdFilterDraft]);

  const handleCloseSession = useCallback(async (sessionId: string) => {
    const ok = await confirm({
      title: 'Close ACP Session',
      message: `Are you sure you want to force-close session ${sessionId.slice(0, 8)}...?`,
      confirmText: 'Close Session',
      variant: 'danger',
    });
    if (!ok) return;

    try {
      await api.closeACPSession(sessionId);
      toast.success('Session closed successfully');
      loadSessions();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to close session';
      toast.error(message);
    }
  }, [confirm, toast, loadSessions]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default">Active</Badge>;
      case 'closed':
        return <Badge variant="secondary">Closed</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      case 'budget_exceeded':
        return <Badge variant="destructive">Budget Exceeded</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8 space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold">ACP Sessions</h1>
                {autoRefresh && (
                  <Badge variant="default" className="bg-green-600 animate-pulse text-xs">Live</Badge>
                )}
              </div>
              <p className="text-muted-foreground">Monitor and manage Agent Client Protocol sessions across all users</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setAutoRefresh(!autoRefresh)}
                className="text-xs"
              >
                Auto-refresh: {autoRefresh ? 'ON' : 'OFF'}
              </Button>
              <ExportMenu
                onExport={(format: ExportFormat) => {
                  exportData({
                    data: sessions as unknown as Record<string, unknown>[],
                    filename: 'acp-sessions',
                    format,
                  });
                }}
                disabled={sessions.length === 0}
              />
              <AccessibleIconButton
                icon={RefreshCw}
                label="Refresh"
                onClick={loadSessions}
                disabled={loading}
                className={loading ? 'animate-spin' : ''}
              />
            </div>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Filters */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Filters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-3">
                <Select
                  value={statusFilterDraft}
                  onChange={(e) => setStatusFilterDraft(e.target.value)}
                >
                  <option value="">All Statuses</option>
                  <option value="active">Active</option>
                  <option value="closed">Closed</option>
                  <option value="error">Error</option>
                </Select>
                <Input
                  placeholder="Agent type..."
                  value={agentTypeFilterDraft}
                  onChange={(e) => setAgentTypeFilterDraft(e.target.value)}
                  className="w-40"
                />
                <Input
                  placeholder="User ID..."
                  value={userIdFilterDraft}
                  onChange={(e) => setUserIdFilterDraft(e.target.value)}
                  className="w-32"
                />
                <Button variant="outline" size="sm" onClick={handleApplyFilters}>Apply</Button>
              </div>
            </CardContent>
          </Card>

          {/* Session Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Sessions ({total})</CardTitle>
              <CardDescription>All ACP agent sessions across the platform</CardDescription>
            </CardHeader>
            <CardContent>
              {sessions.length === 0 && !loading ? (
                <EmptyState
                  icon={MessageSquare}
                  title="No ACP Sessions"
                  description="No agent sessions found matching your filters."
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Session</TableHead>
                        <TableHead>User</TableHead>
                        <TableHead>Agent</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Messages</TableHead>
                        <TableHead>Tokens</TableHead>
                        <TableHead title="Estimated at blended $3/M tokens — actual cost varies by model">
                          Est. Cost <span className="text-muted-foreground cursor-help">&#9432;</span>
                        </TableHead>
                        <TableHead>WS</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sessions.map((session) => (
                        <TableRow key={session.session_id}>
                          <TableCell className="font-mono text-xs">
                            <div className="flex flex-col">
                              <span className="font-medium">{session.name || 'Unnamed'}</span>
                              <span className="text-muted-foreground">{session.session_id.slice(0, 12)}...</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Link href={`/users/${session.user_id}`} className="text-primary hover:underline">
                              User {session.user_id}
                            </Link>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{session.agent_type}</Badge>
                          </TableCell>
                          <TableCell>{getStatusBadge(session.status)}</TableCell>
                          <TableCell>{session.message_count}</TableCell>
                          <TableCell>
                            {session.agent_budget ? (
                              <div className="flex flex-col gap-1">
                                <span className="text-xs font-mono">
                                  {formatTokens(session.usage.total_tokens)} / {formatTokens(session.agent_budget)}
                                </span>
                                <div
                                  role="progressbar"
                                  aria-valuenow={Math.round((session.usage.total_tokens / session.agent_budget) * 100)}
                                  aria-valuemin={0}
                                  aria-valuemax={100}
                                  aria-label="Token budget usage"
                                  className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
                                >
                                  <div
                                    className={`h-full rounded-full transition-all ${
                                      session.usage.total_tokens / session.agent_budget > 0.9 ? 'bg-red-500' :
                                      session.usage.total_tokens / session.agent_budget > 0.7 ? 'bg-yellow-500' :
                                      'bg-green-500'
                                    }`}
                                    style={{ width: `${Math.min(100, (session.usage.total_tokens / session.agent_budget) * 100)}%` }}
                                  />
                                </div>
                              </div>
                            ) : (
                              <span className="text-xs font-mono" title={`Prompt: ${session.usage.prompt_tokens} | Completion: ${session.usage.completion_tokens}`}>
                                {formatTokens(session.usage.total_tokens)}
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {(() => {
                              // Rough estimate: $0.003/1K tokens (blended input/output average)
                              const cost = session.usage.total_tokens * 0.000003;
                              return cost > 0 ? `$${cost.toFixed(4)}` : '—';
                            })()}
                          </TableCell>
                          <TableCell>
                            {session.has_websocket ? (
                              <Wifi className="h-4 w-4 text-green-500" />
                            ) : (
                              <WifiOff className="h-4 w-4 text-muted-foreground" />
                            )}
                          </TableCell>
                          <TableCell className="text-xs">{formatDateTime(session.created_at)}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              {session.status === 'active' && (
                                <AccessibleIconButton
                                  icon={XCircle}
                                  label="Close session"
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleCloseSession(session.session_id)}
                                />
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
