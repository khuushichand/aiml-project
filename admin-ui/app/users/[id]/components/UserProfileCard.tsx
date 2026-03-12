'use client';

import { Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { formatDateTime } from '@/lib/format';
import type { User } from '@/types';

export type UserProfileFormData = {
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  storage_quota_mb: number;
};

export type UserProfileRoleOption = {
  value: string;
  label: string;
};

interface UserProfileCardProps {
  user: User;
  formData: UserProfileFormData;
  roleOptions: readonly UserProfileRoleOption[];
  isAuthorized: boolean;
  saving: boolean;
  isValidRole: (role: string) => boolean;
  onFormDataChange: (next: UserProfileFormData) => void;
  onSave: () => void;
}

const formatDate = (dateStr?: string) => formatDateTime(dateStr, { fallback: 'Never' });

const formatStorage = (usedMb: number, quotaMb: number) => {
  const percentage = quotaMb > 0 ? (usedMb / quotaMb) * 100 : 0;
  return {
    used: usedMb.toFixed(1),
    quota: quotaMb,
    percentage: Math.min(percentage, 100).toFixed(1),
  };
};

export function UserProfileCard({
  user,
  formData,
  roleOptions,
  isAuthorized,
  saving,
  isValidRole,
  onFormDataChange,
  onSave,
}: UserProfileCardProps) {
  const storage = formatStorage(user.storage_used_mb || 0, user.storage_quota_mb || 0);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>User Information</CardTitle>
          <CardDescription>View and edit user details</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>User ID</Label>
              <Input value={user.id} disabled />
            </div>
            <div className="space-y-2">
              <Label>UUID</Label>
              <Input value={user.uuid} disabled className="font-mono text-xs" />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={formData.username}
              disabled={!isAuthorized}
              onChange={(event) =>
                onFormDataChange({ ...formData, username: event.target.value })
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={formData.email}
              disabled={!isAuthorized}
              onChange={(event) =>
                onFormDataChange({ ...formData, email: event.target.value })
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="role">Role</Label>
            <Select
              id="role"
              value={formData.role}
              disabled={!isAuthorized}
              onChange={(event) => {
                const nextRole = event.target.value;
                if (isValidRole(nextRole)) {
                  onFormDataChange({ ...formData, role: nextRole });
                }
              }}
            >
              {!isValidRole(formData.role) && formData.role ? (
                <option value={formData.role}>
                  Unsupported ({formData.role})
                </option>
              ) : null}
              {roleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            {!isValidRole(formData.role) && formData.role ? (
              <p className="text-xs text-muted-foreground">
                This account uses an unsupported role value. It will be preserved unless you explicitly choose a supported replacement.
              </p>
            ) : null}
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              disabled={!isAuthorized}
              onChange={(event) =>
                onFormDataChange({ ...formData, is_active: event.target.checked })
              }
              className="h-4 w-4 rounded border-primary"
            />
            <Label htmlFor="is_active">Active</Label>
          </div>

          <Button onClick={onSave} disabled={saving || !isAuthorized} loading={saving} loadingText="Saving...">
            <Save className="mr-2 h-4 w-4" />
            Save Changes
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Storage & Activity</CardTitle>
          <CardDescription>Usage statistics and timestamps</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label>Storage Usage</Label>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>{storage.used} MB used</span>
                <span>{storage.quota} MB quota</span>
              </div>
              <div
                className="h-3 w-full rounded-full bg-gray-200"
                role="progressbar"
                aria-valuenow={parseFloat(storage.percentage)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Storage usage: ${storage.percentage}%${
                  parseFloat(storage.percentage) > 90 ? ', critical' :
                  parseFloat(storage.percentage) > 70 ? ', warning' : ''
                }`}
              >
                <div
                  className={`h-3 rounded-full transition-all ${
                    parseFloat(storage.percentage) > 90 ? 'bg-red-500' :
                    parseFloat(storage.percentage) > 70 ? 'bg-yellow-500' :
                    'bg-green-500'
                  }`}
                  style={{ width: `${storage.percentage}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {storage.percentage}% of quota used
              </p>
            </div>

            <div className="pt-2">
              <Label htmlFor="storage_quota">Storage Quota (MB)</Label>
              <Input
                id="storage_quota"
                type="number"
                min="0"
                value={formData.storage_quota_mb}
                disabled={!isAuthorized}
                onChange={(event) => {
                  const nextValue = parseInt(event.target.value, 10);
                  onFormDataChange({
                    ...formData,
                    storage_quota_mb: Number.isNaN(nextValue)
                      ? formData.storage_quota_mb
                      : nextValue,
                  });
                }}
                className="mt-1"
              />
            </div>
          </div>

          <div className="space-y-3 border-t pt-4">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Created</span>
              <span className="text-sm">{formatDate(user.created_at)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Updated</span>
              <span className="text-sm">{formatDate(user.updated_at)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Last Login</span>
              <span className="text-sm">{formatDate(user.last_login)}</span>
            </div>
          </div>

          <div className="border-t pt-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Email Verified</span>
              <Badge variant={user.is_verified ? 'default' : 'secondary'}>
                {user.is_verified ? 'Verified' : 'Not Verified'}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
