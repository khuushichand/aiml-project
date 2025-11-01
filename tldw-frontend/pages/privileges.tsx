import { useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Tabs } from '@/components/ui/Tabs';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import VirtualizedTable, { VirtualizedColumn } from '@/components/ui/VirtualizedTable';
import { apiClient, buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import { useToast } from '@/components/ui/ToastProvider';

type PrivilegeSelfItem = {
  endpoint: string;
  method: string;
  privilege_scope_id: string;
  feature_flag_id?: string | null;
  sensitivity_tier?: string | null;
  ownership_predicates?: string[];
  status: 'allowed' | 'blocked';
  blocked_reason?: string | null;
  dependencies?: { id: string; type: string; module?: string | null }[];
  dependency_sources?: string[];
  rate_limit_class?: string | null;
  rate_limit_resources?: string[];
  source_module?: string | null;
  summary?: string | null;
  tags?: string[];
};

type PrivilegeBucketRow = {
  key: string;
  users: number;
  scopes: number;
  endpoints?: number;
  metadata?: Record<string, any> | null;
};

type PrivilegeDetailRow = {
  user_id?: string;
  user_name?: string;
  role?: string;
  endpoint: string;
  method: string;
  privilege_scope_id: string;
  status: 'allowed' | 'blocked';
  blocked_reason?: string | null;
  feature_flag_id?: string | null;
  sensitivity_tier?: string | null;
  ownership_predicates?: string[];
  dependencies?: { id: string; module?: string | null }[];
  rate_limit_class?: string | null;
  rate_limit_resources?: string[];
  source_module?: string | null;
  summary?: string | null;
  tags?: string[];
};

type SnapshotRow = {
  snapshotId: string;
  generatedAt: string;
  targetScope?: string | null;
  catalogVersion: string;
  generatedBy: string;
  orgId?: string | null;
  teamId?: string | null;
  summaryUsers?: number;
  summaryScopes?: number;
};

export default function PrivilegesPage() {
  const { show } = useToast();
  const [activeTab, setActiveTab] = useState<'self' | 'org' | 'team' | 'snapshots'>('self');

  const [selfLoading, setSelfLoading] = useState(false);
  const [selfMap, setSelfMap] = useState<{ generated_at: string; items: PrivilegeSelfItem[] } | null>(null);

  const [orgLoading, setOrgLoading] = useState(false);
  const [orgSummary, setOrgSummary] = useState<{ generated_at: string; buckets: PrivilegeBucketRow[] } | null>(null);
  const [orgDetail, setOrgDetail] = useState<{ generated_at: string; items: PrivilegeDetailRow[]; total_items: number } | null>(null);

  const [teamId, setTeamId] = useState('team-1');
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamSummary, setTeamSummary] = useState<{ generated_at: string; buckets: PrivilegeBucketRow[] } | null>(null);
  const [teamDetail, setTeamDetail] = useState<{ generated_at: string; items: PrivilegeDetailRow[]; total_items: number } | null>(null);

  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [exportingSnapshot, setExportingSnapshot] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === 'self' && !selfMap && !selfLoading) {
      loadSelfMap();
    }
    if (activeTab === 'org' && !orgSummary && !orgLoading) {
      loadOrgSummary();
    }
    if (activeTab === 'snapshots' && snapshots.length === 0 && !snapshotsLoading) {
      loadSnapshots();
    }
  }, [activeTab]);

  const loadSelfMap = async () => {
    setSelfLoading(true);
    try {
      const data = await apiClient.get('/privileges/self');
      setSelfMap({
        generated_at: data.generated_at,
        items: data.items || [],
      });
      show({ title: 'Self map refreshed', variant: 'success' });
    } catch (err: any) {
      show({ title: 'Failed to load self map', description: err?.message, variant: 'danger' });
    } finally {
      setSelfLoading(false);
    }
  };

  const loadOrgSummary = async () => {
    setOrgLoading(true);
    try {
      const data = await apiClient.get('/privileges/org', { params: { group_by: 'role' } });
      setOrgSummary({
        generated_at: data.generated_at,
        buckets: data.buckets || [],
      });
    } catch (err: any) {
      show({ title: 'Failed to load org summary', description: err?.message, variant: 'danger' });
    } finally {
      setOrgLoading(false);
    }
  };

  const loadOrgDetail = async () => {
    setOrgLoading(true);
    try {
      const data = await apiClient.get('/privileges/org', {
        params: { view: 'detail', page_size: 500 },
      });
      setOrgDetail({
        generated_at: data.generated_at,
        items: data.items || [],
        total_items: data.total_items || 0,
      });
    } catch (err: any) {
      show({ title: 'Failed to load org detail', description: err?.message, variant: 'danger' });
    } finally {
      setOrgLoading(false);
    }
  };

  const loadTeamSummary = async () => {
    if (!teamId.trim()) {
      show({ title: 'Team ID required', variant: 'warning' });
      return;
    }
    setTeamLoading(true);
    try {
      const data = await apiClient.get(`/privileges/teams/${teamId.trim()}`, {
        params: { group_by: 'member' },
      });
      setTeamSummary({ generated_at: data.generated_at, buckets: data.buckets || [] });
    } catch (err: any) {
      show({ title: 'Failed to load team summary', description: err?.message, variant: 'danger' });
    } finally {
      setTeamLoading(false);
    }
  };

  const loadTeamDetail = async () => {
    if (!teamId.trim()) {
      show({ title: 'Team ID required', variant: 'warning' });
      return;
    }
    setTeamLoading(true);
    try {
      const data = await apiClient.get(`/privileges/teams/${teamId.trim()}`, {
        params: { view: 'detail', page_size: 500 },
      });
      setTeamDetail({
        generated_at: data.generated_at,
        items: data.items || [],
        total_items: data.total_items || 0,
      });
    } catch (err: any) {
      show({ title: 'Failed to load team detail', description: err?.message, variant: 'danger' });
    } finally {
      setTeamLoading(false);
    }
  };

  const loadSnapshots = async () => {
    setSnapshotsLoading(true);
    try {
      const data = await apiClient.get('/privileges/snapshots', { params: { include_counts: true, page_size: 100 } });
      const rows: SnapshotRow[] = (data.items || []).map((item: any) => ({
        snapshotId: item.snapshot_id,
        generatedAt: item.generated_at,
        targetScope: item.target_scope,
        catalogVersion: item.catalog_version,
        generatedBy: item.generated_by,
        orgId: item.org_id,
        teamId: item.team_id,
        summaryUsers: item.summary?.users,
        summaryScopes: item.summary?.scopes,
      }));
      setSnapshots(rows);
    } catch (err: any) {
      show({ title: 'Failed to load snapshots', description: err?.message, variant: 'danger' });
    } finally {
      setSnapshotsLoading(false);
    }
  };

  const handleRequestAccess = (item: PrivilegeSelfItem) => {
    show({
      title: 'Request submitted',
      description: `We will notify admins to review scope ${item.privilege_scope_id}.`,
      variant: 'info',
    });
  };

  const handleSnapshotExport = async (snapshotId: string, format: 'csv' | 'json') => {
    setExportingSnapshot(`${snapshotId}:${format}`);
    try {
      const baseUrl = getApiBaseUrl();
      const url = `${baseUrl}/privileges/snapshots/${snapshotId}/export.${format}`;
      const response = await fetch(url, {
        headers: buildAuthHeaders('GET'),
      });
      if (!response.ok) {
        throw new Error(`Export failed (${response.status})`);
      }
      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `privilege-snapshot-${snapshotId}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(objectUrl);
      show({ title: `Snapshot exported (${format.toUpperCase()})`, variant: 'success' });
    } catch (err: any) {
      show({ title: 'Export failed', description: err?.message, variant: 'danger' });
    } finally {
      setExportingSnapshot(null);
    }
  };

  const selfColumns: VirtualizedColumn<PrivilegeSelfItem & { index?: number }>[] = useMemo(() => [
    {
      key: 'endpoint',
      label: 'Endpoint',
      width: '30%',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-medium text-gray-900">{row.endpoint}</span>
          <span className="text-xs text-gray-500">{row.privilege_scope_id}</span>
        </div>
      ),
    },
    {
      key: 'method',
      label: 'Method',
      width: 80,
      render: (row) => (
        <Badge variant="primary" className="uppercase tracking-wider">{row.method}</Badge>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      width: 100,
      render: (row) => (
        <Badge variant={row.status === 'allowed' ? 'success' : 'danger'}>
          {row.status === 'allowed' ? 'Allowed' : 'Blocked'}
        </Badge>
      ),
    },
    {
      key: 'sensitivity_tier',
      label: 'Sensitivity',
      width: 120,
      render: (row) => row.sensitivity_tier || '-',
    },
    {
      key: 'feature_flag_id',
      label: 'Feature Flag',
      width: 160,
      render: (row) => row.feature_flag_id || '-',
    },
    {
      key: 'dependencies',
      label: 'Dependencies',
      render: (row) => (row.dependencies || []).map((dep) => dep.id).join(' · ') || '-',
    },
    {
      key: 'actions',
      label: 'Actions',
      width: 140,
      render: (row) => (
        row.status === 'blocked' ? (
          <Button size="sm" variant="secondary" onClick={() => handleRequestAccess(row)}>Request Access</Button>
        ) : null
      ),
    },
  ], [handleRequestAccess]);

  const orgSummaryColumns: VirtualizedColumn<PrivilegeBucketRow>[] = [
    {
      key: 'key',
      label: 'Bucket',
      width: '30%',
    },
    {
      key: 'users',
      label: 'Users',
      width: 100,
    },
    {
      key: 'scopes',
      label: 'Scopes',
      width: 100,
    },
    {
      key: 'endpoints',
      label: 'Endpoints',
      width: 110,
      render: (row) => row.endpoints ?? '-',
    },
  ];

  const detailColumns: VirtualizedColumn<PrivilegeDetailRow>[] = [
    {
      key: 'endpoint',
      label: 'Endpoint',
      width: '28%',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-medium text-gray-900">{row.endpoint}</span>
          <span className="text-xs text-gray-500">{row.privilege_scope_id}</span>
        </div>
      ),
    },
    {
      key: 'user_name',
      label: 'User',
      width: '18%',
      render: (row) => row.user_name || row.user_id || '-',
    },
    {
      key: 'status',
      label: 'Status',
      width: 100,
      render: (row) => (
        <Badge variant={row.status === 'allowed' ? 'success' : 'danger'}>
          {row.status === 'allowed' ? 'Allowed' : 'Blocked'}
        </Badge>
      ),
    },
    {
      key: 'sensitivity_tier',
      label: 'Sensitivity',
      width: 120,
      render: (row) => row.sensitivity_tier || '-',
    },
    {
      key: 'rate_limit_class',
      label: 'Rate Limit',
      width: 120,
      render: (row) => row.rate_limit_class || '-',
    },
    {
      key: 'dependencies',
      label: 'Dependencies',
      render: (row) => (row.dependencies || []).map((dep) => dep.id).join(' · ') || '-',
    },
  ];

  const snapshotColumns: VirtualizedColumn<SnapshotRow>[] = [
    {
      key: 'snapshotId',
      label: 'Snapshot',
      width: '26%',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-medium text-gray-900">{row.snapshotId}</span>
          <span className="text-xs text-gray-500">{row.catalogVersion}</span>
        </div>
      ),
    },
    {
      key: 'generatedAt',
      label: 'Generated',
      width: 160,
      render: (row) => formatRelativeTime(row.generatedAt),
    },
    {
      key: 'targetScope',
      label: 'Scope',
      width: 120,
      render: (row) => row.targetScope || '-',
    },
    {
      key: 'summaryUsers',
      label: 'Users',
      width: 100,
      render: (row) => row.summaryUsers ?? '-',
    },
    {
      key: 'actions',
      label: 'Exports',
      render: (row) => (
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            loading={exportingSnapshot === `${row.snapshotId}:json`}
            onClick={() => handleSnapshotExport(row.snapshotId, 'json')}
          >
            JSON
          </Button>
          <Button
            size="sm"
            variant="secondary"
            loading={exportingSnapshot === `${row.snapshotId}:csv`}
            onClick={() => handleSnapshotExport(row.snapshotId, 'csv')}
          >
            CSV
          </Button>
        </div>
      ),
    },
  ];

  const renderSelfTab = () => (
    <div className="mt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">My Access</h2>
          <p className="text-sm text-gray-500">Live view of your allowed endpoints, scopes, and feature flags.</p>
          {selfMap?.generated_at && (
            <p className="mt-1 text-xs text-gray-400">Refreshed {formatRelativeTime(selfMap.generated_at)}</p>
          )}
        </div>
        <Button onClick={loadSelfMap} loading={selfLoading}>Refresh</Button>
      </div>
      <VirtualizedTable
        data={selfMap?.items || []}
        columns={selfColumns}
        height={420}
        emptyState={<span>No privileges found for your account.</span>}
      />
    </div>
  );

  const renderOrgTab = () => (
    <div className="mt-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Organization Summary</h2>
          <p className="text-sm text-gray-500">Aggregated privileges by role. Drill down for per-user detail.</p>
          {orgSummary?.generated_at && (
            <p className="mt-1 text-xs text-gray-400">Generated {formatRelativeTime(orgSummary.generated_at)}</p>
          )}
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={loadOrgSummary} loading={orgLoading}>Refresh Summary</Button>
          <Button onClick={loadOrgDetail} loading={orgLoading}>Load Detail</Button>
        </div>
      </div>
      <VirtualizedTable
        data={orgSummary?.buckets || []}
        columns={orgSummaryColumns}
        height={260}
        emptyState={<span>No organization data available.</span>}
      />
      {orgDetail && (
        <div>
          <h3 className="text-md font-semibold text-gray-900">Detail Matrix</h3>
          <p className="text-xs text-gray-500 mb-2">Showing {orgDetail.items.length} of {orgDetail.total_items} entries.</p>
          <VirtualizedTable
            data={orgDetail.items}
            columns={detailColumns}
            height={360}
            emptyState={<span>No detailed entries loaded.</span>}
          />
        </div>
      )}
    </div>
  );

  const renderTeamTab = () => (
    <div className="mt-6 space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Team Insights</h2>
          <p className="text-sm text-gray-500">Compare team members and verify the right scopes before projects start.</p>
        </div>
        <div className="flex gap-3">
          <Input
            value={teamId}
            onChange={(event) => setTeamId(event.target.value)}
            placeholder="team-id"
            className="w-48"
          />
          <Button variant="secondary" onClick={loadTeamSummary} loading={teamLoading}>Summary</Button>
          <Button onClick={loadTeamDetail} loading={teamLoading}>Detail</Button>
        </div>
      </div>
      <VirtualizedTable
        data={teamSummary?.buckets || []}
        columns={orgSummaryColumns}
        height={260}
        emptyState={<span>Run a summary to view team buckets.</span>}
      />
      {teamDetail && (
        <div>
          <h3 className="text-md font-semibold text-gray-900">Team Detail</h3>
          <p className="text-xs text-gray-500 mb-2">Showing {teamDetail.items.length} of {teamDetail.total_items} entries.</p>
          <VirtualizedTable
            data={teamDetail.items}
            columns={detailColumns}
            height={360}
            emptyState={<span>No team detail loaded.</span>}
          />
        </div>
      )}
    </div>
  );

  const renderSnapshotsTab = () => (
    <div className="mt-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Snapshot Catalog</h2>
          <p className="text-sm text-gray-500">Exports honor retention policy (90 days with weekly keepers).</p>
        </div>
        <Button variant="secondary" onClick={loadSnapshots} loading={snapshotsLoading}>Refresh</Button>
      </div>
      <VirtualizedTable
        data={snapshots}
        columns={snapshotColumns}
        height={420}
        emptyState={<span>No snapshots generated yet.</span>}
      />
    </div>
  );

  return (
    <Layout title="Privilege Maps">
      <div className="mx-auto max-w-6xl py-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold text-gray-900">Privilege Maps</h1>
          <p className="text-sm text-gray-600">
            Explore live access for individuals, teams, and the entire organization. Export historical snapshots or request additional scopes without waiting on support tickets.
          </p>
        </div>
        <Tabs
          className="mt-6"
          items={[
            { key: 'self', label: 'My Access' },
            { key: 'org', label: 'Organization' },
            { key: 'team', label: 'Team' },
            { key: 'snapshots', label: 'Snapshots' },
          ]}
          value={activeTab}
          onChange={(value) => setActiveTab(value as typeof activeTab)}
        />

        {activeTab === 'self' && renderSelfTab()}
        {activeTab === 'org' && renderOrgTab()}
        {activeTab === 'team' && renderTeamTab()}
        {activeTab === 'snapshots' && renderSnapshotsTab()}
      </div>
    </Layout>
  );
}
