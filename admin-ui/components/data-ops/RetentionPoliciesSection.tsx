'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/components/ui/toast';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { api } from '@/lib/api-client';
import type { RetentionPolicy } from '@/types';
import { AlertTriangle, ShieldCheck } from 'lucide-react';

type RetentionPoliciesSectionProps = {
  refreshSignal: number;
};

export const RetentionPoliciesSection = ({ refreshSignal }: RetentionPoliciesSectionProps) => {
  const { success, error: showError } = useToast();
  const confirm = useConfirm();

  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [policyError, setPolicyError] = useState('');
  const [policyLoading, setPolicyLoading] = useState(true);
  const [policyEdits, setPolicyEdits] = useState<Record<string, string>>({});
  const [policySaving, setPolicySaving] = useState<Record<string, boolean>>({});

  const loadPolicies = useCallback(async () => {
    try {
      setPolicyLoading(true);
      setPolicyError('');
      const data = await api.getRetentionPolicies();
      setPolicies(data.policies);
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to load retention policies';
      setPolicyError(message);
      setPolicies([]);
    } finally {
      setPolicyLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPolicies();
  }, [loadPolicies, refreshSignal]);

  const handlePolicyUpdate = async (policy: RetentionPolicy) => {
    const raw = policyEdits[policy.key] ?? '';
    if (!raw.trim()) {
      showError('Invalid value', 'Retention days cannot be empty.');
      return;
    }
    const value = Number(raw.trim());
    if (!Number.isFinite(value) || value < 1) {
      showError('Invalid value', 'Retention days must be a positive number.');
      return;
    }
    const accepted = await confirm({
      title: 'Apply retention policy change?',
      message: 'This update applies immediately and persists across restarts. Review retention windows before saving.',
      confirmText: 'Apply',
      variant: 'warning',
      icon: 'warning',
    });
    if (!accepted) return;
    setPolicySaving((prev) => ({ ...prev, [policy.key]: true }));
    try {
      await api.updateRetentionPolicy(policy.key, { days: Number(value) });
      success('Retention updated', `${policy.key} set to ${value} days.`);
      setPolicyEdits((prev) => {
        const next = { ...prev };
        delete next[policy.key];
        return next;
      });
      await loadPolicies();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to update retention policy';
      showError('Update failed', message);
    } finally {
      setPolicySaving((prev) => ({ ...prev, [policy.key]: false }));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5" />
          Retention Policies
        </CardTitle>
        <CardDescription>Adjust cleanup windows for system datasets.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {policyError && (
          <Alert variant="destructive">
            <AlertDescription>{policyError}</AlertDescription>
          </Alert>
        )}
        <Alert className="bg-yellow-50 border-yellow-200">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800">
            Retention policy changes apply immediately and persist across restarts. Lower values can delete data
            sooner than expected, so review carefully before saving.
          </AlertDescription>
        </Alert>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Policy</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Days</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {policyLoading ? (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  Loading retention policies...
                </TableCell>
              </TableRow>
            ) : policies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  No retention policies found.
                </TableCell>
              </TableRow>
            ) : (
              policies.map((policy) => {
                const draft = policyEdits[policy.key];
                const value = draft ?? (policy.days?.toString() ?? '');
                return (
                  <TableRow key={policy.key}>
                    <TableCell className="font-mono text-xs">{policy.key}</TableCell>
                    <TableCell>{policy.description || '—'}</TableCell>
                    <TableCell className="w-40">
                      <Input
                        value={value}
                        onChange={(event) =>
                          setPolicyEdits((prev) => ({ ...prev, [policy.key]: event.target.value }))
                        }
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        onClick={() => handlePolicyUpdate(policy)}
                        disabled={policySaving[policy.key]}
                      >
                        {policySaving[policy.key] ? 'Saving...' : 'Save'}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
