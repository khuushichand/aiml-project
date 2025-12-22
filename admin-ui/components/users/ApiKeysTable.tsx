import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { RotateCw, Trash2 } from 'lucide-react';
import { ApiKey } from '@/types';

type ApiKeysTableProps = {
  apiKeys: ApiKey[];
  onRotate: (keyId: string) => void;
  onRevoke: (keyId: string, keyName: string) => void;
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString();
};

const isExpired = (expiresAt?: string) => {
  if (!expiresAt) return false;
  return new Date(expiresAt) < new Date();
};

const isRevoked = (revokedAt?: string) => {
  return !!revokedAt;
};

const getKeyStatus = (key: ApiKey) => {
  if (isRevoked(key.revoked_at)) return { label: 'Revoked', variant: 'destructive' as const };
  if (isExpired(key.expires_at)) return { label: 'Expired', variant: 'secondary' as const };
  return { label: 'Active', variant: 'default' as const };
};

export const ApiKeysTable = ({ apiKeys, onRotate, onRevoke }: ApiKeysTableProps) => {
  if (apiKeys.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-8">
        No API keys found. Create one to get started.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Key Prefix</TableHead>
          <TableHead>Scope</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Expires</TableHead>
          <TableHead>Last Used</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {apiKeys.map((key) => {
          const status = getKeyStatus(key);
          const isActive = status.label === 'Active';

          return (
            <TableRow key={key.id} className={!isActive ? 'opacity-60' : ''}>
              <TableCell className="font-medium">{key.name || '-'}</TableCell>
              <TableCell>
                <code className="bg-muted px-2 py-1 rounded text-sm">
                  {key.key_prefix}...
                </code>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{key.scope}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant={status.variant}>{status.label}</Badge>
              </TableCell>
              <TableCell className="text-sm">{formatDate(key.created_at)}</TableCell>
              <TableCell className="text-sm">
                {key.expires_at ? (
                  <span className={isExpired(key.expires_at) ? 'text-red-500' : ''}>
                    {formatDate(key.expires_at)}
                  </span>
                ) : (
                  'Never'
                )}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {formatDate(key.last_used_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRotate(key.id)}
                    disabled={!isActive}
                    title="Rotate key"
                  >
                    <RotateCw className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRevoke(key.id, key.name || '')}
                    disabled={!isActive}
                    title="Revoke key"
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
};
