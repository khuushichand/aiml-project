'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState } from '@/components/ui/empty-state';
import { CardSkeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { UserPlus, Trash2, Copy, RefreshCw } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api } from '@/lib/api-client';
import type { RegistrationCode } from '@/types';

export default function RegistrationPage() {
  const [codes, setCodes] = useState<RegistrationCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const toast = useToast();
  const confirm = useConfirm();

  const loadCodes = useCallback(async () => {
    try {
      setLoading(true);
      setLoadError('');
      const data = await api.getRegistrationCodes();
      setCodes(Array.isArray(data) ? data : []);
    } catch {
      setCodes([]);
      setLoadError('Failed to load registration codes');
      toast.error('Failed to load registration codes');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadCodes();
  }, [loadCodes]);

  const handleDelete = async (code: RegistrationCode) => {
    const ok = await confirm({
      title: 'Delete Registration Code',
      message: `Delete code "${code.code}"? This cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!ok) return;
    try {
      await api.deleteRegistrationCode(code.code);
      toast.success('Registration code deleted');
      loadCodes();
    } catch {
      toast.error('Failed to delete registration code');
    }
  };

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code).then(() => {
      toast.success('Code copied to clipboard');
    });
  };

  return (
    <PermissionGuard variant="route" requireAuth role={['admin', 'super_admin', 'owner']}>
      <ResponsiveLayout>
        <div className="p-4 lg:p-8 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <UserPlus className="h-7 w-7" />
                Registration Codes
              </h1>
              <p className="text-muted-foreground">Manage user registration and invitation codes</p>
            </div>
            <AccessibleIconButton
              icon={RefreshCw}
              label="Refresh"
              variant="outline"
              onClick={() => loadCodes()}
              className={loading ? 'animate-spin' : ''}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Active Codes</CardTitle>
              <CardDescription>Registration codes that can be used to create new accounts</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <CardSkeleton />
              ) : loadError ? (
                <div className="space-y-4">
                  <EmptyState
                    icon={UserPlus}
                    title="Unable to load registration codes"
                    description="The registration code list could not be loaded. Retry to fetch the latest data."
                  />
                  <div className="flex justify-center">
                    <Button type="button" variant="outline" onClick={() => loadCodes()}>
                      Retry
                    </Button>
                  </div>
                </div>
              ) : codes.length === 0 ? (
                <EmptyState
                  icon={UserPlus}
                  title="No Registration Codes"
                  description="Create registration codes from the dashboard to allow new users to sign up."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Max Uses</TableHead>
                      <TableHead>Times Used</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {codes.map((code) => (
                      <TableRow key={code.code}>
                        <TableCell className="font-mono text-sm">{code.code}</TableCell>
                        <TableCell>{code.max_uses ?? '∞'}</TableCell>
                        <TableCell>{code.times_used ?? 0}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{code.role_to_grant || 'user'}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {code.expires_at
                            ? new Date(code.expires_at).toLocaleDateString()
                            : 'Never'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <AccessibleIconButton
                              icon={Copy}
                              label="Copy code"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCopy(code.code)}
                            />
                            <AccessibleIconButton
                              icon={Trash2}
                              label="Delete code"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(code)}
                              className="text-destructive hover:text-destructive"
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
