'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api } from '@/lib/api-client';
import type { CompliancePosture } from '@/types';
import { Shield, ShieldCheck, Key, Users, FileText, RefreshCw, ExternalLink } from 'lucide-react';
import Link from 'next/link';

type ComplianceGrade = 'A' | 'B' | 'C' | 'D' | 'F';

function getGrade(score: number): ComplianceGrade {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 70) return 'C';
  if (score >= 60) return 'D';
  return 'F';
}

function getGradeColor(grade: ComplianceGrade): string {
  switch (grade) {
    case 'A': return 'text-green-600 dark:text-green-400';
    case 'B': return 'text-blue-600 dark:text-blue-400';
    case 'C': return 'text-yellow-600 dark:text-yellow-400';
    case 'D': return 'text-orange-600 dark:text-orange-400';
    case 'F': return 'text-red-600 dark:text-red-400';
  }
}

function getGradeBadgeVariant(grade: ComplianceGrade): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (grade) {
    case 'A':
    case 'B':
      return 'default';
    case 'C':
      return 'secondary';
    case 'D':
    case 'F':
      return 'destructive';
  }
}

function getPercentColor(pct: number): string {
  if (pct >= 90) return 'text-green-600 dark:text-green-400';
  if (pct >= 70) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function ProgressBar({ value, className }: { value: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  let barColor = 'bg-red-500';
  if (clamped >= 90) barColor = 'bg-green-500';
  else if (clamped >= 70) barColor = 'bg-yellow-500';
  else if (clamped >= 50) barColor = 'bg-orange-500';

  return (
    <div className={`h-2 w-full rounded-full bg-muted ${className ?? ''}`}>
      <div
        className={`h-full rounded-full transition-all duration-500 ${barColor}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

function CompliancePageContent() {
  const [posture, setPosture] = useState<CompliancePosture | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPosture = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCompliancePosture();
      setPosture(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load compliance posture';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPosture();
  }, [fetchPosture]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Compliance Posture</h1>
            <p className="text-muted-foreground">Loading compliance metrics...</p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <div className="h-4 w-24 animate-pulse rounded bg-muted" />
              </CardHeader>
              <CardContent>
                <div className="h-8 w-16 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Compliance Posture</h1>
            <p className="text-muted-foreground">Security and compliance overview</p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchPosture}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </div>
        <Alert variant="destructive">
          <AlertDescription>Unable to load compliance data: {error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!posture) return null;

  const grade = getGrade(posture.overall_score);
  const gradeColor = getGradeColor(grade);
  const gradeBadge = getGradeBadgeVariant(grade);
  const mfaColor = getPercentColor(posture.mfa_adoption_pct);
  const keyColor = getPercentColor(posture.key_rotation_compliance_pct);
  const usersWithoutMfa = posture.total_users - posture.mfa_enabled_count;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Compliance Posture</h1>
          <p className="text-muted-foreground">Security and compliance overview</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchPosture}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Cards grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Overall Score */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Overall Score</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className={`text-3xl font-bold ${gradeColor}`}>
                {posture.overall_score.toFixed(0)}
              </span>
              <Badge variant={gradeBadge} data-testid="compliance-grade">{grade}</Badge>
            </div>
            <ProgressBar value={posture.overall_score} className="mt-3" />
            <p className="mt-2 text-xs text-muted-foreground">
              Weighted: MFA 40% + Key rotation 40% + Audit 20%
            </p>
          </CardContent>
        </Card>

        {/* MFA Adoption */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">MFA Adoption</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className={`text-3xl font-bold ${mfaColor}`}>
                {posture.mfa_adoption_pct.toFixed(0)}%
              </span>
            </div>
            <ProgressBar value={posture.mfa_adoption_pct} className="mt-3" />
            <p className="mt-2 text-xs text-muted-foreground">
              {posture.mfa_enabled_count} of {posture.total_users} users enabled
            </p>
            {usersWithoutMfa > 0 && (
              <Link
                href="/users?is_active=true"
                className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                {usersWithoutMfa} without MFA
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}
          </CardContent>
        </Card>

        {/* Key Rotation */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Key Rotation</CardTitle>
            <Key className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className={`text-3xl font-bold ${keyColor}`}>
                {posture.key_rotation_compliance_pct.toFixed(0)}%
              </span>
            </div>
            <ProgressBar value={posture.key_rotation_compliance_pct} className="mt-3" />
            <p className="mt-2 text-xs text-muted-foreground">
              {posture.keys_total - posture.keys_needing_rotation} of {posture.keys_total} keys compliant
              ({posture.rotation_threshold_days}d threshold)
            </p>
            {posture.keys_needing_rotation > 0 && (
              <Link
                href="/api-keys"
                className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                {posture.keys_needing_rotation} need rotation
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}
          </CardContent>
        </Card>

        {/* Audit Logging */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Audit Logging</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              {posture.audit_logging_enabled ? (
                <ShieldCheck className="h-8 w-8 text-green-600 dark:text-green-400" />
              ) : (
                <Shield className="h-8 w-8 text-red-600 dark:text-red-400" />
              )}
              <span className="text-lg font-semibold">
                {posture.audit_logging_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              {posture.audit_logging_enabled
                ? 'All admin actions are being recorded'
                : 'Audit logging is not active'}
            </p>
            <Link
              href="/audit"
              className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:underline dark:text-blue-400"
            >
              View audit logs
              <ExternalLink className="h-3 w-3" />
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function CompliancePage() {
  return (
    <PermissionGuard role={['admin', 'super_admin', 'owner']}>
      <ResponsiveLayout>
        <CompliancePageContent />
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
