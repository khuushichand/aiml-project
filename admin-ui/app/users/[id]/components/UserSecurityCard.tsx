'use client';

import { Clock, Monitor, RefreshCw, Shield, Trash2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatDateTime } from '@/lib/format';
import type { LoginHistoryEntry, MfaStatus, UserSession } from '../hooks/use-user-security';

interface UserSecurityCardProps {
  isAuthorized: boolean;
  securityLoading: boolean;
  securityError: string;
  mfaStatus: MfaStatus | null;
  sessions: UserSession[];
  loginHistory: LoginHistoryEntry[];
  loginHistoryLoading: boolean;
  loginHistoryError: string;
  forcePasswordChangeOnNextLogin: boolean;
  passwordResetLoading: boolean;
  resetPasswordValue: string;
  onForcePasswordChangeOnNextLogin: (next: boolean) => void;
  onResetPasswordValueChange: (value: string) => void;
  onResetPassword: () => void;
  onDisableMfa: () => void;
  onRefreshSecurity: () => void;
  onRevokeAllSessions: () => void;
  onRevokeSession: (session: UserSession) => void;
  onRefreshLoginHistory: () => void;
}

const formatDate = (dateStr?: string) => formatDateTime(dateStr, { fallback: 'Never' });

export function UserSecurityCard({
  isAuthorized,
  securityLoading,
  securityError,
  mfaStatus,
  sessions,
  loginHistory,
  loginHistoryLoading,
  loginHistoryError,
  forcePasswordChangeOnNextLogin,
  passwordResetLoading,
  resetPasswordValue,
  onForcePasswordChangeOnNextLogin,
  onResetPasswordValueChange,
  onResetPassword,
  onDisableMfa,
  onRefreshSecurity,
  onRevokeAllSessions,
  onRevokeSession,
  onRefreshLoginHistory,
}: UserSecurityCardProps) {
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Security Controls</CardTitle>
        <CardDescription>MFA status and active sessions</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {securityError && (
          <Alert variant="destructive">
            <AlertDescription>{securityError}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-3 rounded-lg border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="font-medium">Password reset</div>
              <p className="text-sm text-muted-foreground">
                Generate a temporary password for this user.
              </p>
            </div>
            <Button
              onClick={onResetPassword}
              disabled={!isAuthorized || passwordResetLoading}
              loading={passwordResetLoading}
              loadingText="Resetting..."
            >
              Reset Password
            </Button>
          </div>
          <div className="space-y-2">
            <Label htmlFor="temporary-password">Temporary Password to Set</Label>
            <Input
              id="temporary-password"
              type="password"
              autoComplete="new-password"
              value={resetPasswordValue}
              onChange={(event) => onResetPasswordValueChange(event.target.value)}
              disabled={!isAuthorized || passwordResetLoading}
              minLength={10}
              placeholder="Enter a temporary password to share securely"
            />
            <p className="text-xs text-muted-foreground">
              Set the temporary password yourself so it never needs to be returned to the browser.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={forcePasswordChangeOnNextLogin}
              onChange={(event) => onForcePasswordChangeOnNextLogin(event.target.checked)}
              disabled={!isAuthorized || passwordResetLoading}
              className="h-4 w-4 rounded border-primary"
            />
            Force Password Change on Next Login
          </label>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">Multi-factor authentication</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <Badge variant={mfaStatus?.enabled ? 'default' : 'secondary'}>
                {mfaStatus?.enabled ? 'Enabled' : 'Disabled'}
              </Badge>
              {mfaStatus?.method ? <span className="text-xs">Method: {mfaStatus.method}</span> : null}
              <span className="text-xs">
                Backup codes: {mfaStatus?.has_backup_codes ? 'Set' : 'Not set'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              MFA enrollment is managed by the user from their profile.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={onDisableMfa}
            disabled={!mfaStatus?.enabled || !isAuthorized}
          >
            Disable MFA
          </Button>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Monitor className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">Active sessions</span>
              <Badge variant="outline">{sessions.length}</Badge>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={onRefreshSecurity} disabled={securityLoading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${securityLoading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onRevokeAllSessions}
                disabled={!sessions.length || !isAuthorized}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Revoke all
              </Button>
            </div>
          </div>

          {securityLoading ? (
            <div className="text-sm text-muted-foreground">Loading sessions...</div>
          ) : sessions.length === 0 ? (
            <div className="text-sm text-muted-foreground">No active sessions found.</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Session</TableHead>
                    <TableHead>IP Address</TableHead>
                    <TableHead>Last Activity</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sessions.map((session) => (
                    <TableRow key={session.id}>
                      <TableCell>
                        <div className="text-sm font-mono">{session.id}</div>
                        <div className="max-w-[240px] truncate text-xs text-muted-foreground">
                          {session.user_agent || 'Unknown device'}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm font-mono">
                        {session.ip_address || '—'}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDate(session.last_activity || session.created_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDate(session.expires_at || '')}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onRevokeSession(session)}
                          disabled={!isAuthorized}
                        >
                          Revoke
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <div className="space-y-3 border-t pt-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">Login History</span>
              <Badge variant="outline">{loginHistory.length}</Badge>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={onRefreshLoginHistory}
              disabled={loginHistoryLoading}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${loginHistoryLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          {loginHistoryError && (
            <Alert variant="destructive">
              <AlertDescription>{loginHistoryError}</AlertDescription>
            </Alert>
          )}

          {loginHistoryLoading ? (
            <div className="text-sm text-muted-foreground">Loading login history...</div>
          ) : loginHistory.length === 0 ? (
            <div className="text-sm text-muted-foreground">No recent login attempts found.</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>IP Address</TableHead>
                    <TableHead>User Agent</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loginHistory.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="text-sm">{formatDate(entry.timestamp)}</TableCell>
                      <TableCell>
                        <Badge variant={entry.status === 'success' ? 'default' : 'destructive'}>
                          {entry.status === 'success' ? 'Success' : 'Failure'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm font-mono">{entry.ipAddress || '—'}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {entry.userAgent || 'Unknown client'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
