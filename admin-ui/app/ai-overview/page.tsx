'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CardSkeleton } from '@/components/ui/skeleton';
import { Brain, DollarSign, Zap, Users, RefreshCw } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api } from '@/lib/api-client';

function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

interface ProviderUsage {
  name: string;
  requests: number;
  tokens: number;
  cost: number;
  errorRate: number;
}

interface AgentUsage {
  agent_type: string;
  invocation_count: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export default function AIOverviewPage() {
  const [loading, setLoading] = useState(true);
  const [activeSessions, setActiveSessions] = useState<number>(0);
  const [totalTokens, setTotalTokens] = useState<number>(0);
  const [totalCost, setTotalCost] = useState<number>(0);
  const [providerUsage, setProviderUsage] = useState<ProviderUsage[]>([]);
  const [topAgents, setTopAgents] = useState<AgentUsage[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch data from multiple endpoints in parallel
      const [sessionsResult, agentUsageResult, providersResult] = await Promise.allSettled([
        api.getACPSessions({ status: 'active' }),
        api.getACPAgentUsage(7),
        api.getLLMProviders(),
      ]);

      // Active sessions count
      if (sessionsResult.status === 'fulfilled') {
        const data = sessionsResult.value as { total?: number; sessions?: unknown[] };
        setActiveSessions(data.total ?? (Array.isArray(data.sessions) ? data.sessions.length : 0));
      }

      // Agent usage (top 5 by cost)
      if (agentUsageResult.status === 'fulfilled') {
        const data = agentUsageResult.value as { agents: AgentUsage[] };
        const agents = data.agents || [];
        setTopAgents(agents.slice(0, 5));
        setTotalTokens(agents.reduce((sum, a) => sum + a.total_tokens, 0));
        setTotalCost(agents.reduce((sum, a) => sum + a.estimated_cost_usd, 0));
      }

      // Provider usage
      if (providersResult.status === 'fulfilled') {
        const providers = Array.isArray(providersResult.value) ? providersResult.value : [];
        setProviderUsage(
          providers
            .filter((p: Record<string, unknown>) => p.enabled)
            .map((p: Record<string, unknown>) => ({
              name: String(p.name || 'Unknown'),
              requests: 0,
              tokens: 0,
              cost: 0,
              errorRate: 0,
            }))
        );
      }
    } catch (err) {
      console.error('Failed to load AI overview:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <PermissionGuard variant="route" requireAuth role={['admin', 'super_admin', 'owner']}>
      <ResponsiveLayout>
        <div className="p-4 lg:p-8 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <Brain className="h-7 w-7" />
                AI Operations Overview
              </h1>
              <p className="text-muted-foreground">Cross-cutting view of AI spend, token consumption, and agent activity</p>
            </div>
            <AccessibleIconButton
              icon={RefreshCw}
              label="Refresh"
              variant="outline"
              onClick={() => loadData()}
              className={loading ? 'animate-spin' : ''}
            />
          </div>

          {loading ? (
            <div className="grid gap-4 md:grid-cols-4">
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </div>
          ) : (
            <>
              {/* Summary Cards */}
              <div className="grid gap-4 md:grid-cols-4">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Total AI Spend (7d)</CardTitle>
                    <DollarSign className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">${totalCost.toFixed(2)}</div>
                    <p className="text-xs text-muted-foreground">Estimated from agent sessions</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Tokens (7d)</CardTitle>
                    <Zap className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{formatCompact(totalTokens)}</div>
                    <p className="text-xs text-muted-foreground">Across all agent types</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
                    <Users className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{activeSessions}</div>
                    <p className="text-xs text-muted-foreground">ACP sessions right now</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Enabled Providers</CardTitle>
                    <Brain className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{providerUsage.length}</div>
                    <p className="text-xs text-muted-foreground">LLM providers configured</p>
                  </CardContent>
                </Card>
              </div>

              {/* Top Agents by Cost */}
              <Card>
                <CardHeader>
                  <CardTitle>Top Agents by Cost (7d)</CardTitle>
                  <CardDescription>Agent types ranked by estimated token spend</CardDescription>
                </CardHeader>
                <CardContent>
                  {topAgents.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No agent usage data available.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Agent Type</TableHead>
                          <TableHead className="text-right">Invocations</TableHead>
                          <TableHead className="text-right">Tokens</TableHead>
                          <TableHead className="text-right">Est. Cost</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {topAgents.map((agent) => (
                          <TableRow key={agent.agent_type}>
                            <TableCell>
                              <Badge variant="outline">{agent.agent_type}</Badge>
                            </TableCell>
                            <TableCell className="text-right font-mono">{agent.invocation_count}</TableCell>
                            <TableCell className="text-right font-mono">{formatCompact(agent.total_tokens)}</TableCell>
                            <TableCell className="text-right font-mono">${agent.estimated_cost_usd.toFixed(2)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Enabled Providers */}
              <Card>
                <CardHeader>
                  <CardTitle>Enabled Providers</CardTitle>
                  <CardDescription>LLM providers currently active in the platform</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {providerUsage.map((p) => (
                      <Badge key={p.name} variant="secondary" className="text-sm">{p.name}</Badge>
                    ))}
                    {providerUsage.length === 0 && (
                      <p className="text-sm text-muted-foreground">No providers enabled.</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
