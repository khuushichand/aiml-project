'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { api } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import type { SecurityHealthData } from '@/types';
import { ShieldAlert, ShieldCheck, RefreshCw, AlertTriangle, Key, Users, Lock } from 'lucide-react';
import Link from 'next/link';

type SecurityAlertStatus = {
  total_alerts?: number;
  critical_alerts?: number;
  warning_alerts?: number;
  unacknowledged?: number;
  recent_alerts?: {
    id: string;
    severity: string;
    message: string;
    timestamp: string;
    source?: string;
  }[];
};

const formatDate = (dateStr?: string) => formatDateTime(dateStr, { fallback: '—' });

const getRiskLevelLabel = (score: number) => {
  if (score >= 70) return { label: 'High Risk', variant: 'destructive' as const };
  if (score >= 40) return { label: 'Medium Risk', variant: 'secondary' as const };
  return { label: 'Low Risk', variant: 'default' as const };
};

const getRiskLevelColor = (score: number) => {
  if (score >= 70) return 'text-red-500';
  if (score >= 40) return 'text-yellow-500';
  return 'text-green-500';
};

export default function SecurityPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [securityHealth, setSecurityHealth] = useState<SecurityHealthData | null>(null);
  const [alertStatus, setAlertStatus] = useState<SecurityAlertStatus | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [healthResult, alertsResult] = await Promise.allSettled([
        api.getSecurityHealth(),
        api.getSecurityAlertStatus(),
      ]);

      if (healthResult.status === 'fulfilled') {
        setSecurityHealth(healthResult.value as SecurityHealthData);
      } else {
        // Set defaults if endpoint unavailable
        setSecurityHealth({
          risk_score: 0,
          recent_security_events: 0,
          failed_logins_24h: 0,
          suspicious_activity: 0,
          mfa_adoption_rate: 0,
          active_sessions: 0,
          api_keys_active: 0,
        });
      }

      if (alertsResult.status === 'fulfilled') {
        setAlertStatus(alertsResult.value as SecurityAlertStatus);
      } else {
        setAlertStatus({
          total_alerts: 0,
          critical_alerts: 0,
          warning_alerts: 0,
          unacknowledged: 0,
          recent_alerts: [],
        });
      }

      if (healthResult.status === 'rejected' && alertsResult.status === 'rejected') {
        setError('Failed to load security data. Some endpoints may not be available.');
      }
    } catch (err: unknown) {
      console.error('Failed to load security data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load security data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const riskLevel = getRiskLevelLabel(securityHealth?.risk_score ?? 0);
  const riskColor = getRiskLevelColor(securityHealth?.risk_score ?? 0);

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <ShieldAlert className="h-8 w-8" />
                Security Dashboard
              </h1>
              <p className="text-muted-foreground">
                Monitor security posture, alerts, and authentication activity
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

          {/* Risk Score Card */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {(securityHealth?.risk_score ?? 0) < 40 ? (
                  <ShieldCheck className="h-5 w-5 text-green-500" />
                ) : (
                  <ShieldAlert className="h-5 w-5 text-yellow-500" />
                )}
                Security Risk Assessment
              </CardTitle>
              <CardDescription>Overall security posture score</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-8">
                <div>
                  <div className={`text-6xl font-bold ${riskColor}`}>
                    {securityHealth?.risk_score ?? 0}
                  </div>
                  <Badge variant={riskLevel.variant} className="mt-2">
                    {riskLevel.label}
                  </Badge>
                </div>
                <div className="flex-1">
                  <div className="h-4 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        (securityHealth?.risk_score ?? 0) >= 70
                          ? 'bg-red-500'
                          : (securityHealth?.risk_score ?? 0) >= 40
                            ? 'bg-yellow-500'
                            : 'bg-green-500'
                      }`}
                      style={{ width: `${securityHealth?.risk_score ?? 0}%` }}
                    />
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    {securityHealth?.last_security_scan
                      ? `Last scan: ${formatDate(securityHealth.last_security_scan)}`
                      : 'Risk score based on recent security events and configuration'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Stats Grid */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  Security Events (24h)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {securityHealth?.recent_security_events ?? 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  {securityHealth?.suspicious_activity ?? 0} suspicious
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Lock className="h-4 w-4" />
                  Failed Logins (24h)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`text-3xl font-bold ${
                  (securityHealth?.failed_logins_24h ?? 0) > 10 ? 'text-red-500' : ''
                }`}>
                  {securityHealth?.failed_logins_24h ?? 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  Potential brute force attempts
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  MFA Adoption
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {securityHealth?.mfa_adoption_rate ?? 0}%
                </div>
                <p className="text-xs text-muted-foreground">
                  Users with MFA enabled
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Key className="h-4 w-4" />
                  Active Sessions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {securityHealth?.active_sessions ?? 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  {securityHealth?.api_keys_active ?? 0} API keys in use
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Alert Summary */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5" />
                  Security Alerts
                </CardTitle>
                <CardDescription>
                  {alertStatus?.unacknowledged ?? 0} unacknowledged alerts
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-900/20">
                    <div className="text-2xl font-bold text-red-500">
                      {alertStatus?.critical_alerts ?? 0}
                    </div>
                    <div className="text-xs text-muted-foreground">Critical</div>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                    <div className="text-2xl font-bold text-yellow-500">
                      {alertStatus?.warning_alerts ?? 0}
                    </div>
                    <div className="text-xs text-muted-foreground">Warning</div>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted">
                    <div className="text-2xl font-bold">
                      {alertStatus?.total_alerts ?? 0}
                    </div>
                    <div className="text-xs text-muted-foreground">Total</div>
                  </div>
                </div>
                <Link href="/monitoring">
                  <Button variant="outline" className="w-full">
                    View All Alerts
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Recent Security Events */}
            <Card>
              <CardHeader>
                <CardTitle>Recent Security Events</CardTitle>
                <CardDescription>Latest security-related activity</CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center text-muted-foreground py-8">
                    Loading...
                  </div>
                ) : !alertStatus?.recent_alerts?.length ? (
                  <div className="text-center text-muted-foreground py-8">
                    <ShieldCheck className="h-12 w-12 mx-auto mb-2 text-green-500" />
                    <p>No recent security events</p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Severity</TableHead>
                        <TableHead>Event</TableHead>
                        <TableHead>Time</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {alertStatus.recent_alerts.slice(0, 5).map((alert) => (
                        <TableRow key={alert.id}>
                          <TableCell>
                            <Badge
                              variant={
                                alert.severity === 'critical'
                                  ? 'destructive'
                                  : alert.severity === 'warning'
                                    ? 'secondary'
                                    : 'outline'
                              }
                            >
                              {alert.severity}
                            </Badge>
                          </TableCell>
                          <TableCell className="max-w-[200px] truncate">
                            {alert.message}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {formatDate(alert.timestamp)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
                <Link href="/audit?filter=security" className="block mt-4">
                  <Button variant="ghost" className="w-full">
                    View Security Audit Logs
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>

          {/* Quick Actions */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Security Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-4">
                <Link href="/users">
                  <Button variant="outline">
                    <Users className="mr-2 h-4 w-4" />
                    Manage Users
                  </Button>
                </Link>
                <Link href="/api-keys">
                  <Button variant="outline">
                    <Key className="mr-2 h-4 w-4" />
                    API Key Management
                  </Button>
                </Link>
                <Link href="/audit">
                  <Button variant="outline">
                    Audit Logs
                  </Button>
                </Link>
                <Link href="/roles">
                  <Button variant="outline">
                    Roles & Permissions
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
