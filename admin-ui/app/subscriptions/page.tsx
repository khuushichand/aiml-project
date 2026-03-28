'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import { EmptyState } from '@/components/ui/empty-state';
import { TableSkeleton } from '@/components/ui/skeleton';
import { PlanBadge } from '@/components/PlanBadge';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
import { isBillingEnabled } from '@/lib/billing';
import Link from 'next/link';
import { ExportMenu } from '@/components/ui/export-menu';
import { exportData, type ExportFormat } from '@/lib/export';
import { formatDate } from '@/lib/formatters';
import type { Subscription, SubscriptionStatus } from '@/types';

const STATUS_VARIANTS: Record<SubscriptionStatus, 'default' | 'outline' | 'destructive' | 'secondary'> = {
  active: 'default',
  trialing: 'outline',
  past_due: 'destructive',
  canceled: 'secondary',
  incomplete: 'secondary',
};

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'All Statuses' },
  { value: 'active', label: 'Active' },
  { value: 'trialing', label: 'Trialing' },
  { value: 'past_due', label: 'Past Due' },
  { value: 'canceled', label: 'Canceled' },
];

function SubscriptionsPageContent() {
  const { error: showError } = useToast();
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [orgNames, setOrgNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const fetchSubscriptions = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const data = await api.getSubscriptions(params);
      setSubscriptions(data);
      // Batch-fetch org names for display
      try {
        const orgs = await api.getOrganizations();
        const names: Record<string, string> = {};
        (Array.isArray(orgs) ? orgs : []).forEach((o: { id: number | string; name: string }) => {
          names[String(o.id)] = o.name;
        });
        setOrgNames(names);
      } catch { /* org names are optional — fail silently */ }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load subscriptions';
      setLoadError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, showError]);

  useEffect(() => {
    if (isBillingEnabled()) {
      fetchSubscriptions();
    } else {
      setLoading(false);
    }
  }, [fetchSubscriptions]);

  if (!isBillingEnabled()) {
    return (
      <ResponsiveLayout>
        <Alert>
          <AlertDescription>Billing is not enabled</AlertDescription>
        </Alert>
      </ResponsiveLayout>
    );
  }

  return (
    <ResponsiveLayout>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Subscriptions</CardTitle>
            <div className="flex items-center gap-2">
              <ExportMenu
                onExport={(format: ExportFormat) => {
                  exportData({
                    data: subscriptions as unknown as Record<string, unknown>[],
                    filename: 'subscriptions',
                    format,
                  });
                }}
                disabled={subscriptions.length === 0}
              />
              <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-48"
              aria-label="Filter by status"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loadError && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{loadError}</AlertDescription>
            </Alert>
          )}

          {!loading && (() => {
            const atRisk = subscriptions.filter(s => s.status === 'past_due' || s.status === 'incomplete');
            if (atRisk.length === 0) return null;
            return (
              <Alert className="mb-4 border-red-200 bg-red-50">
                <AlertDescription className="text-red-900">
                  <strong>{atRisk.length} subscription{atRisk.length !== 1 ? 's' : ''} need attention</strong> — {atRisk.filter(s => s.status === 'past_due').length} past due, {atRisk.filter(s => s.status === 'incomplete').length} incomplete.
                </AlertDescription>
              </Alert>
            );
          })()}

          {loading ? (
            <TableSkeleton rows={5} columns={5} />
          ) : subscriptions.length === 0 ? (
            <EmptyState title="No subscriptions found" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Organization</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Current Period</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subscriptions.map((sub) => (
                  <TableRow key={sub.id}>
                    <TableCell>
                      <Link
                        href={`/organizations/${sub.org_id}`}
                        className="text-blue-600 hover:underline"
                      >
                        {orgNames[String(sub.org_id)] || `Org ${sub.org_id}`}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {sub.plan ? (
                        <PlanBadge tier={sub.plan.tier} />
                      ) : (
                        sub.plan_id
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANTS[sub.status] ?? 'secondary'}>
                        {sub.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {formatDate(sub.current_period_start)} &ndash; {formatDate(sub.current_period_end)}
                    </TableCell>
                    <TableCell>{formatDate(sub.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </ResponsiveLayout>
  );
}

export default function SubscriptionsPage() {
  return (
    <PermissionGuard role={['admin', 'super_admin', 'owner']}>
      <SubscriptionsPageContent />
    </PermissionGuard>
  );
}
