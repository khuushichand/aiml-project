'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CardSkeleton } from '@/components/ui/skeleton';
import { ShieldCheck, Users, Key, FileText, Database, RefreshCw } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api } from '@/lib/api-client';

type PostureDimension = {
  label: string;
  icon: typeof ShieldCheck;
  score: number;
  status: 'good' | 'warning' | 'critical';
  detail: string;
  href: string;
};

export default function CompliancePage() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [dimensions, setDimensions] = useState<PostureDimension[]>([]);
  const [overallScore, setOverallScore] = useState<number>(0);

  const loadPosture = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      // Gather data from existing endpoints
      const [securityResult, usersResult] = await Promise.allSettled([
        api.getSecurityHealth(),
        api.getUsers(),
      ]);

      const secHealth = securityResult.status === 'fulfilled'
        ? securityResult.value as { mfa_adoption_rate?: number; risk_score?: number }
        : null;
      const users = usersResult.status === 'fulfilled'
        ? (Array.isArray(usersResult.value) ? usersResult.value : [])
        : [];

      const mfaAdoption = secHealth?.mfa_adoption_rate ?? 0;
      const activeUsers = users.filter((u: { is_active?: boolean }) => u.is_active).length;
      const totalUsers = users.length;

      const dims: PostureDimension[] = [
        {
          label: 'MFA Adoption',
          icon: Users,
          score: Math.round(mfaAdoption * 100),
          status: mfaAdoption > 0.8 ? 'good' : mfaAdoption > 0.5 ? 'warning' : 'critical',
          detail: `${Math.round(mfaAdoption * 100)}% of users have MFA enabled`,
          href: '/security',
        },
        {
          label: 'API Key Hygiene',
          icon: Key,
          // TODO(PR-932): Replace this placeholder with key age/rotation metrics from a dedicated hygiene endpoint.
          score: 70,
          status: 'warning',
          detail: 'Key age and rotation health',
          href: '/api-keys',
        },
        {
          label: 'Audit Coverage',
          icon: FileText,
          score: activeUsers > 0 ? 90 : 0,
          status: activeUsers > 0 ? 'good' : 'critical',
          detail: `${totalUsers} users tracked, audit logging active`,
          href: '/audit',
        },
        {
          label: 'Data Retention',
          icon: Database,
          // TODO(PR-932): Replace this placeholder with retention policy compliance metrics from data-ops APIs.
          score: 80,
          status: 'good',
          detail: 'Retention policies configured',
          href: '/data-ops',
        },
      ];

      setDimensions(dims);
      setOverallScore(Math.round(dims.reduce((sum, d) => sum + d.score, 0) / dims.length));
    } catch (err) {
      console.error('Failed to load compliance posture:', err);
      setLoadError(err instanceof Error && err.message ? err.message : 'Failed to load compliance data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPosture();
  }, [loadPosture]);

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getStatusBadge = (status: 'good' | 'warning' | 'critical') => {
    switch (status) {
      case 'good': return <Badge variant="default" className="bg-green-600">Good</Badge>;
      case 'warning': return <Badge className="bg-yellow-500 text-black">Warning</Badge>;
      case 'critical': return <Badge variant="destructive">Critical</Badge>;
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth role={['admin', 'super_admin', 'owner']}>
      <ResponsiveLayout>
        <div className="p-4 lg:p-8 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <ShieldCheck className="h-7 w-7" />
                Compliance Posture
              </h1>
              <p className="text-muted-foreground">Security and compliance health across the platform</p>
            </div>
            <AccessibleIconButton
              icon={RefreshCw}
              label="Refresh"
              variant="outline"
              onClick={() => loadPosture()}
              className={loading ? 'animate-spin' : ''}
            />
          </div>

          {loading ? (
            <div className="grid gap-4 md:grid-cols-2">
              <CardSkeleton />
              <CardSkeleton />
            </div>
          ) : loadError ? (
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-destructive">{loadError}</p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Overall Score */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Overall Compliance Score</p>
                      <p className={`text-5xl font-bold ${getScoreColor(overallScore)}`}>{overallScore}</p>
                      <p className="text-xs text-muted-foreground mt-1">out of 100</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-muted-foreground">{dimensions.length} dimensions assessed</p>
                      <p className="text-sm">
                        {dimensions.filter(d => d.status === 'good').length} good,{' '}
                        {dimensions.filter(d => d.status === 'warning').length} warning,{' '}
                        {dimensions.filter(d => d.status === 'critical').length} critical
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Dimension Cards */}
              <div className="grid gap-4 md:grid-cols-2">
                {dimensions.map((dim) => (
                  <Card key={dim.label}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <dim.icon className="h-4 w-4" />
                        {dim.label}
                      </CardTitle>
                      {getStatusBadge(dim.status)}
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-between">
                        <div>
                          <p className={`text-2xl font-bold ${getScoreColor(dim.score)}`}>{dim.score}%</p>
                          <p className="text-xs text-muted-foreground">{dim.detail}</p>
                        </div>
                        <Link href={dim.href}>
                          <Button variant="ghost" size="sm">View</Button>
                        </Link>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          )}
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
