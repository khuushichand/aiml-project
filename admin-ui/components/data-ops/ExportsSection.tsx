'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { buildApiUrl } from '@/lib/api-config';
import { buildAuthHeaders } from '@/lib/http';
import { Download } from 'lucide-react';
import { Field } from '@/components/data-ops/Field';

const EXPORT_FORMATS = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
];

type ExportsSectionProps = {
  refreshSignal: number;
};

const splitDispositionParts = (value: string) => {
  const parts: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < value.length; i += 1) {
    const char = value[i];
    if (char === '"' && (i === 0 || value[i - 1] !== '\\')) {
      inQuotes = !inQuotes;
    }
    if (char === ';' && !inQuotes) {
      const trimmed = current.trim();
      if (trimmed) {
        parts.push(trimmed);
      }
      current = '';
      continue;
    }
    current += char;
  }
  const trimmed = current.trim();
  if (trimmed) {
    parts.push(trimmed);
  }
  return parts;
};

const unquoteHeaderValue = (value: string) => {
  if (value.startsWith('"') && value.endsWith('"')) {
    return value.slice(1, -1).replace(/\\(.)/g, '$1');
  }
  return value;
};

const decode5987Value = (value: string) => {
  const raw = unquoteHeaderValue(value);
  const match = raw.match(/^([^']*)'[^']*'(.*)$/);
  const encoded = match ? match[2] : raw;
  try {
    return decodeURIComponent(encoded);
  } catch {
    return encoded;
  }
};

const getFilenameFromDisposition = (disposition: string | null): string | null => {
  if (!disposition) return null;
  const parts = splitDispositionParts(disposition);
  const params: Record<string, string> = {};
  for (const part of parts.slice(1)) {
    const eqIndex = part.indexOf('=');
    if (eqIndex === -1) continue;
    const key = part.slice(0, eqIndex).trim().toLowerCase();
    if (!key) continue;
    const rawValue = part.slice(eqIndex + 1).trim();
    if (!rawValue) continue;
    params[key] = unquoteHeaderValue(rawValue);
  }
  if (params['filename*']) {
    const decoded = decode5987Value(params['filename*']);
    if (decoded) return decoded;
  }
  return params.filename || null;
};

const downloadExport = async (
  endpoint: string,
  params: Record<string, string>,
  fallbackFilename: string
) => {
  const timeoutMs = 30_000;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  const query = new URLSearchParams(params).toString();
  try {
    const response = await fetch(buildApiUrl(`${endpoint}${query ? `?${query}` : ''}`), {
      headers: buildAuthHeaders('GET'),
      credentials: 'include',
      signal: controller.signal,
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || 'Failed to download export');
    }
    const blob = await response.blob();
    const filename = getFilenameFromDisposition(response.headers.get('content-disposition')) || fallbackFilename;
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Download aborted: timeout');
    }
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Download aborted: timeout');
    }
    throw err;
  } finally {
    window.clearTimeout(timeoutId);
  }
};

export const ExportsSection = ({ refreshSignal }: ExportsSectionProps) => {
  const { selectedOrg } = useOrgContext();
  const { success, error: showError } = useToast();

  const [auditExporting, setAuditExporting] = useState(false);
  const [userExporting, setUserExporting] = useState(false);
  const [auditStart, setAuditStart] = useState('');
  const [auditEnd, setAuditEnd] = useState('');
  const [auditAction, setAuditAction] = useState('');
  const [auditUserId, setAuditUserId] = useState('');
  const [auditResource, setAuditResource] = useState('');
  const [auditFormat, setAuditFormat] = useState('csv');

  const [userSearch, setUserSearch] = useState('');
  const [userRole, setUserRole] = useState('');
  const [userStatus, setUserStatus] = useState('');
  const [userFormat, setUserFormat] = useState('csv');

  useEffect(() => {
    if (refreshSignal === 0) return;
    setAuditStart('');
    setAuditEnd('');
    setAuditAction('');
    setAuditUserId('');
    setAuditResource('');
    setAuditFormat('csv');
    setUserSearch('');
    setUserRole('');
    setUserStatus('');
    setUserFormat('csv');
  }, [refreshSignal]);

  const handleAuditExport = async () => {
    try {
      setAuditExporting(true);
      const params: Record<string, string> = { format: auditFormat };
      if (auditStart) params.start = auditStart;
      if (auditEnd) params.end = auditEnd;
      if (auditAction.trim()) params.action = auditAction.trim();
      if (auditUserId.trim()) params.user_id = auditUserId.trim();
      if (auditResource.trim()) params.resource = auditResource.trim();
      if (selectedOrg) params.org_id = String(selectedOrg.id);
      const filename = `audit_log.${auditFormat}`;
      await downloadExport('/admin/audit-log/export', params, filename);
      success('Export ready', 'Audit log download started.');
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to export audit logs';
      showError('Export failed', message);
    } finally {
      setAuditExporting(false);
    }
  };

  const handleUserExport = async () => {
    try {
      setUserExporting(true);
      const params: Record<string, string> = { format: userFormat };
      if (userSearch.trim()) params.search = userSearch.trim();
      if (userRole.trim()) params.role = userRole.trim();
      if (userStatus.trim()) params.is_active = userStatus.trim();
      if (selectedOrg) params.org_id = String(selectedOrg.id);
      const filename = `users.${userFormat}`;
      await downloadExport('/admin/users/export', params, filename);
      success('Export ready', 'User export download started.');
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to export users';
      showError('Export failed', message);
    } finally {
      setUserExporting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="h-5 w-5" />
          Exports
        </CardTitle>
        <CardDescription>Server-side exports for audit logs and users.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3 rounded-lg border p-4">
            <div>
              <h4 className="font-semibold">Audit Log Export</h4>
              <p className="text-sm text-muted-foreground">Filter and download audit events.</p>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <Field id="audit-start" label="Start (YYYY-MM-DD)">
                <Input
                  id="audit-start"
                  type="date"
                  value={auditStart}
                  onChange={(e) => setAuditStart(e.target.value)}
                />
              </Field>
              <Field id="audit-end" label="End (YYYY-MM-DD)">
                <Input
                  id="audit-end"
                  type="date"
                  value={auditEnd}
                  onChange={(e) => setAuditEnd(e.target.value)}
                />
              </Field>
              <Field id="audit-action" label="Action">
                <Input id="audit-action" value={auditAction} onChange={(e) => setAuditAction(e.target.value)} />
              </Field>
              <Field id="audit-user" label="User ID">
                <Input id="audit-user" value={auditUserId} onChange={(e) => setAuditUserId(e.target.value)} />
              </Field>
              <Field id="audit-resource" label="Resource">
                <Input id="audit-resource" value={auditResource} onChange={(e) => setAuditResource(e.target.value)} />
              </Field>
              <Field id="audit-format" label="Format">
                <Select
                  id="audit-format"
                  value={auditFormat}
                  onChange={(event) => setAuditFormat(event.target.value)}
                >
                  {EXPORT_FORMATS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Button onClick={handleAuditExport} disabled={auditExporting}>
              {auditExporting ? 'Exporting...' : 'Download audit logs'}
            </Button>
          </div>

          <div className="space-y-3 rounded-lg border p-4">
            <div>
              <h4 className="font-semibold">User Export</h4>
              <p className="text-sm text-muted-foreground">Download user list snapshots.</p>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <Field id="users-search" label="Search">
                <Input id="users-search" value={userSearch} onChange={(e) => setUserSearch(e.target.value)} />
              </Field>
              <Field id="users-role" label="Role">
                <Input id="users-role" value={userRole} onChange={(e) => setUserRole(e.target.value)} />
              </Field>
              <Field id="users-active" label="Active">
                <Select
                  id="users-active"
                  value={userStatus}
                  onChange={(event) => setUserStatus(event.target.value)}
                >
                  <option value="">All</option>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </Select>
              </Field>
              <Field id="users-format" label="Format">
                <Select
                  id="users-format"
                  value={userFormat}
                  onChange={(event) => setUserFormat(event.target.value)}
                >
                  {EXPORT_FORMATS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Button onClick={handleUserExport} disabled={userExporting}>
              {userExporting ? 'Exporting...' : 'Download users'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
