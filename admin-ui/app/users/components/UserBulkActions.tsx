'use client';

import { ShieldCheck, ShieldOff, Trash2, UserCheck, UserX } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';

interface UserBulkActionsProps {
  selectedCount: number;
  bulkRole: string;
  bulkRoleOptions: string[];
  bulkBusy: boolean;
  bulkAction: string | null;
  onBulkRoleChange: (value: string) => void;
  onAssignRole: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
  onRequireMfa: () => void;
  onClearMfa: () => void;
  onDelete: () => void;
  onClearSelection: () => void;
}

export function UserBulkActions({
  selectedCount,
  bulkRole,
  bulkRoleOptions,
  bulkBusy,
  bulkAction,
  onBulkRoleChange,
  onAssignRole,
  onActivate,
  onDeactivate,
  onRequireMfa,
  onClearMfa,
  onDelete,
  onClearSelection,
}: UserBulkActionsProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="mb-4 flex flex-col gap-3 rounded-md border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{selectedCount} selected</Badge>
        <span className="text-sm text-muted-foreground">
          Bulk actions apply to selected users.
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Select
          value={bulkRole}
          onChange={(event) => onBulkRoleChange(event.target.value)}
          className="min-w-[160px]"
          aria-label="Bulk role selection"
          disabled={bulkBusy}
        >
          {bulkRoleOptions.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </Select>
        <Button
          variant="outline"
          size="sm"
          onClick={onAssignRole}
          loading={bulkAction === 'assign-role'}
          loadingText="Assigning..."
          disabled={bulkBusy && bulkAction !== 'assign-role'}
        >
          Assign Role
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onActivate}
          loading={bulkAction === 'activate'}
          loadingText="Activating..."
          disabled={bulkBusy && bulkAction !== 'activate'}
        >
          <UserCheck className="mr-2 h-4 w-4" />
          Activate
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onDeactivate}
          loading={bulkAction === 'deactivate'}
          loadingText="Deactivating..."
          disabled={bulkBusy && bulkAction !== 'deactivate'}
        >
          <UserX className="mr-2 h-4 w-4" />
          Deactivate
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onRequireMfa}
          loading={bulkAction === 'mfa-require'}
          loadingText="Applying..."
          disabled={bulkBusy && bulkAction !== 'mfa-require'}
        >
          <ShieldCheck className="mr-2 h-4 w-4" />
          Require MFA
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onClearMfa}
          loading={bulkAction === 'mfa-clear'}
          loadingText="Clearing..."
          disabled={bulkBusy && bulkAction !== 'mfa-clear'}
        >
          <ShieldOff className="mr-2 h-4 w-4" />
          Clear MFA
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onDelete}
          loading={bulkAction === 'delete'}
          loadingText="Deleting..."
          disabled={bulkBusy && bulkAction !== 'delete'}
        >
          <Trash2 className="mr-2 h-4 w-4 text-destructive" />
          Delete
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClearSelection}
          disabled={bulkBusy}
        >
          Clear selection
        </Button>
      </div>
    </div>
  );
}
