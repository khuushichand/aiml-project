'use client';

import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { KeyRound, RefreshCw } from 'lucide-react';

const summaryCards = [
  { title: 'BYOK Users', value: '—', detail: 'Users with stored keys' },
  { title: 'Shared Keys', value: '—', detail: 'Org/Team shared keys' },
  { title: 'BYOK Requests', value: '—', detail: 'Requests resolved via BYOK' },
  { title: 'Missing Keys', value: '—', detail: 'Missing credential events' },
];

const resolutionMix = [
  { source: 'User', share: '—', note: 'Per-user keys' },
  { source: 'Team', share: '—', note: 'Team shared keys' },
  { source: 'Org', share: '—', note: 'Org shared keys' },
  { source: 'Server', share: '—', note: 'Server defaults' },
];

const keyActivityRows = [
  { when: '—', actor: '—', action: 'Created', scope: 'User', provider: 'OpenAI' },
  { when: '—', actor: '—', action: 'Updated', scope: 'Org', provider: 'Anthropic' },
  { when: '—', actor: '—', action: 'Revoked', scope: 'Team', provider: 'OpenRouter' },
];

export default function ByokDashboardPage() {
  const { selectedOrg } = useOrgContext();

  return (
    <ProtectedRoute requiredRoles={['admin', 'super_admin', 'owner']}>
      <ResponsiveLayout>
        <div className="space-y-6 p-4 lg:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <KeyRound className="h-5 w-5 text-primary" />
                <h1 className="text-2xl font-semibold">BYOK Dashboards</h1>
              </div>
              <p className="text-sm text-muted-foreground">
                Placeholder telemetry views for BYOK adoption, resolution mix, and key activity.
              </p>
              {selectedOrg && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Active scope: {selectedOrg.name}
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Coming soon</Badge>
              <Button variant="outline" size="sm" disabled>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh metrics
              </Button>
            </div>
          </div>

          <Alert>
            <AlertDescription>
              Metrics wiring and admin controls are pending. This view will update once BYOK telemetry endpoints are enabled.
            </AlertDescription>
          </Alert>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((card) => (
              <Card key={card.title}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{card.title}</CardTitle>
                  <CardDescription>{card.detail}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-semibold">{card.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Resolution Mix</CardTitle>
                <CardDescription>Share of requests by credential source.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {resolutionMix.map((row) => (
                  <div key={row.source} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                    <div>
                      <div className="font-medium">{row.source}</div>
                      <div className="text-xs text-muted-foreground">{row.note}</div>
                    </div>
                    <div className="text-xs font-semibold text-muted-foreground">{row.share}</div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Missing Credentials</CardTitle>
                <CardDescription>Top providers with missing key events.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center justify-between rounded-md border px-3 py-2">
                  <span>OpenAI</span>
                  <span>—</span>
                </div>
                <div className="flex items-center justify-between rounded-md border px-3 py-2">
                  <span>Anthropic</span>
                  <span>—</span>
                </div>
                <div className="flex items-center justify-between rounded-md border px-3 py-2">
                  <span>OpenRouter</span>
                  <span>—</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Key Validation</CardTitle>
                <CardDescription>Recent validation results and errors.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div className="rounded-md border px-3 py-2">No validation events yet.</div>
                <Button variant="secondary" size="sm" disabled>
                  Run validation sweep
                </Button>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Key Activity (Placeholder)</CardTitle>
              <CardDescription>Admin and user key changes once audit fields are wired.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Scope</TableHead>
                    <TableHead>Provider</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {keyActivityRows.map((row, idx) => (
                    <TableRow key={`${row.action}-${idx}`}>
                      <TableCell className="text-muted-foreground">{row.when}</TableCell>
                      <TableCell>{row.actor}</TableCell>
                      <TableCell>{row.action}</TableCell>
                      <TableCell>{row.scope}</TableCell>
                      <TableCell>{row.provider}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
