/**
 * Export utilities for downloading data as CSV or JSON
 */

export type ExportFormat = 'csv' | 'json';

interface ExportOptions<T> {
  /** Data to export */
  data: T[];
  /** Filename without extension */
  filename: string;
  /** Export format */
  format: ExportFormat;
  /** Column definitions for CSV (order and headers) */
  columns?: {
    key: keyof T | string;
    header: string;
    /** Transform function for the value */
    transform?: (value: unknown, row: T) => string;
  }[];
}

/**
 * Escape a value for CSV format
 */
function escapeCSV(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }

  const str = typeof value === 'object' ? JSON.stringify(value) : String(value);

  // If the value contains comma, newline, or quote, wrap in quotes and escape internal quotes
  if (str.includes(',') || str.includes('\n') || str.includes('"')) {
    return `"${str.replace(/"/g, '""')}"`;
  }

  return str;
}

/**
 * Get nested property from object using dot notation
 */
function getNestedValue(obj: Record<string, unknown> | null | undefined, path: string): unknown {
  return path.split('.').reduce<unknown>((current, key) => {
    if (current && typeof current === 'object') {
      return (current as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

function toIsoDateString(value: unknown, fallback = ''): string {
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (typeof value === 'string' || typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? fallback : date.toISOString();
  }
  return fallback;
}

/**
 * Convert data array to CSV string
 */
function toCSV<T extends Record<string, unknown>>(data: T[], columns: ExportOptions<T>['columns']): string {
  if (!columns || columns.length === 0) {
    // Auto-generate columns from first item
    if (data.length === 0) return '';
    const keys = Object.keys(data[0] as object);
    columns = keys.map(key => ({ key, header: key }));
  }

  const headers = columns.map(col => escapeCSV(col.header));
  const rows = data.map(row =>
    columns!.map(col => {
      const value = getNestedValue(row, col.key as string);
      const transformed = col.transform ? col.transform(value, row) : value;
      return escapeCSV(transformed);
    }).join(',')
  );

  return [headers.join(','), ...rows].join('\n');
}

/**
 * Convert data array to formatted JSON string
 */
function toJSON<T>(data: T[]): string {
  return JSON.stringify(data, null, 2);
}

/**
 * Trigger file download in browser
 */
function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Export data to CSV or JSON file
 */
export function exportData<T extends Record<string, unknown>>(options: ExportOptions<T>): void {
  const { data, filename, format, columns } = options;
  const timestamp = new Date().toISOString().split('T')[0];

  if (format === 'csv') {
    const content = toCSV(data, columns);
    downloadFile(content, `${filename}-${timestamp}.csv`, 'text/csv;charset=utf-8');
  } else {
    const content = toJSON(data);
    downloadFile(content, `${filename}-${timestamp}.json`, 'application/json');
  }
}

/**
 * Pre-configured export for audit logs
 */
export function exportAuditLogs<T extends object>(logs: T[], format: ExportFormat = 'csv'): void {
  exportData({
    data: logs as unknown as Record<string, unknown>[],
    filename: 'audit-logs',
    format,
    columns: [
      { key: 'timestamp', header: 'Timestamp', transform: (v) => toIsoDateString(v) },
      { key: 'user_id', header: 'User ID' },
      { key: 'action', header: 'Action' },
      { key: 'resource', header: 'Resource' },
      { key: 'resource_id', header: 'Resource ID' },
      { key: 'ip_address', header: 'IP Address' },
      { key: 'details', header: 'Details', transform: (v) => v ? JSON.stringify(v) : '' },
    ],
  });
}

/**
 * Pre-configured export for users
 */
export function exportUsers<T extends object>(users: T[], format: ExportFormat = 'csv'): void {
  exportData({
    data: users as Record<string, unknown>[],
    filename: 'users',
    format,
    columns: [
      { key: 'id', header: 'ID' },
      { key: 'username', header: 'Username' },
      { key: 'email', header: 'Email' },
      { key: 'role', header: 'Role' },
      { key: 'is_active', header: 'Active', transform: (v) => v ? 'Yes' : 'No' },
      { key: 'is_verified', header: 'Verified', transform: (v) => v ? 'Yes' : 'No' },
      { key: 'storage_used_mb', header: 'Storage Used (MB)' },
      { key: 'storage_quota_mb', header: 'Storage Quota (MB)' },
      { key: 'created_at', header: 'Created At', transform: (v) => toIsoDateString(v) },
      { key: 'last_login', header: 'Last Login', transform: (v) => toIsoDateString(v) },
    ],
  });
}

/**
 * Pre-configured export for API keys
 */
export function exportApiKeys<T extends object>(keys: T[], format: ExportFormat = 'csv'): void {
  exportData({
    data: keys as Record<string, unknown>[],
    filename: 'api-keys',
    format,
    columns: [
      { key: 'id', header: 'ID' },
      { key: 'name', header: 'Name' },
      { key: 'prefix', header: 'Key Prefix' },
      { key: 'user_id', header: 'User ID' },
      { key: 'is_active', header: 'Active', transform: (v) => v ? 'Yes' : 'No' },
      { key: 'created_at', header: 'Created At', transform: (v) => toIsoDateString(v) },
      { key: 'expires_at', header: 'Expires At', transform: (v) => toIsoDateString(v, 'Never') },
      { key: 'last_used_at', header: 'Last Used', transform: (v) => toIsoDateString(v, 'Never') },
    ],
  });
}
