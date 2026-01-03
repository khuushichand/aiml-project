import { useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { isAdmin, normalizeStringArray } from '@/lib/authz';

type ClaimRow = {
  id: number;
  claim_text: string;
  review_status?: string;
  reviewer_id?: number;
  review_group?: string;
  media_id?: number;
  chunk_index?: number;
  created_at?: string;
};

const STATUS_OPTIONS = ['pending', 'flagged', 'reassigned', 'approved', 'rejected'];

export default function ClaimsReviewPage() {
  const { show } = useToast();
  const { user } = useAuth();
  const userIsAdmin = isAdmin(user);
  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [reviewGroup, setReviewGroup] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [assignedToMe, setAssignedToMe] = useState(true);
  const [page, setPage] = useState(1);
  const [limit] = useState(25);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkStatus, setBulkStatus] = useState<string>('approved');
  const [bulkReviewerId, setBulkReviewerId] = useState('');
  const [bulkReviewGroup, setBulkReviewGroup] = useState('');
  const [bulkNotes, setBulkNotes] = useState('');
  const [bulkReasonCode, setBulkReasonCode] = useState('');

  const canReview = useMemo(() => {
    if (userIsAdmin) return true;
    if (!user) return false;
    const roles = normalizeStringArray(user.roles);
    const perms = normalizeStringArray(user.permissions);
    return roles.includes('reviewer') || perms.includes('claims.review') || perms.includes('claims.admin');
  }, [user, userIsAdmin]);

  const effectiveReviewerId = useMemo(() => {
    if (assignedToMe && user?.id != null) {
      const idVal = Number(user.id);
      return Number.isFinite(idVal) ? idVal : undefined;
    }
    if (reviewerId.trim()) {
      const parsed = Number(reviewerId.trim());
      return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
  }, [assignedToMe, reviewerId, user]);

  const loadQueue = useCallback(async (pageOverride?: number) => {
    setLoading(true);
    try {
      const pageValue = pageOverride ?? page;
      const params: Record<string, unknown> = {
        limit,
        offset: (pageValue - 1) * limit,
      };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (reviewGroup.trim()) params.review_group = reviewGroup.trim();
      if (effectiveReviewerId !== undefined) params.reviewer_id = effectiveReviewerId;

      const data = await apiClient.get<ClaimRow[]>('/claims/review-queue', { params });
      setClaims(data || []);
      setSelectedIds(new Set());
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Failed to load review queue', description: message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [effectiveReviewerId, limit, page, reviewGroup, show, statusFilter]);

  const toggleSelect = (claimId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(claimId)) {
        next.delete(claimId);
      } else {
        next.add(claimId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === claims.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(claims.map((c) => c.id)));
    }
  };

  const handleBulkAction = async () => {
    if (!selectedIds.size) {
      show({ title: 'No claims selected', description: 'Select at least one claim.', variant: 'warning' });
      return;
    }
    if (bulkStatus === 'reassigned' && !bulkReviewerId.trim() && !bulkReviewGroup.trim()) {
      show({ title: 'Missing reassignment target', description: 'Provide reviewer ID or review group.', variant: 'warning' });
      return;
    }
    try {
      const payload: Record<string, unknown> = {
        claim_ids: Array.from(selectedIds),
        status: bulkStatus,
      };
      if (bulkNotes.trim()) payload.notes = bulkNotes.trim();
      if (bulkReasonCode.trim()) payload.reason_code = bulkReasonCode.trim();
      if (bulkReviewerId.trim()) payload.reviewer_id = Number(bulkReviewerId.trim());
      if (bulkReviewGroup.trim()) payload.review_group = bulkReviewGroup.trim();

      const res = await apiClient.post('/claims/review/bulk', payload);
      const updated = Array.isArray(res?.updated) ? res.updated.length : 0;
      show({
        title: 'Bulk action complete',
        description: `Updated ${updated} claims.`,
        variant: 'success',
      });
      await loadQueue();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Bulk action failed', description: message, variant: 'danger' });
    }
  };

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  if (!canReview) {
    return (
      <Layout>
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-4 text-2xl font-bold text-gray-900">Claims Review</h1>
          <div className="rounded-md border bg-white p-4 text-sm text-gray-700">Review access required.</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-gray-900">Claims Review</h1>
          <Button onClick={loadQueue} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh Queue'}
          </Button>
        </div>

        <div className="grid gap-4 rounded-md border bg-white p-4 md:grid-cols-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Status</label>
            <select
              className="w-full rounded border px-3 py-2 text-sm"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Review group</label>
            <Input
              value={reviewGroup}
              onChange={(e) => setReviewGroup(e.target.value)}
              placeholder="group name"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Reviewer ID</label>
            <Input
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              placeholder={assignedToMe ? String(user?.id || '') : 'user id'}
              disabled={assignedToMe}
            />
          </div>
          <div className="flex items-end gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={assignedToMe}
                onChange={(e) => setAssignedToMe(e.target.checked)}
              />
              Assigned to me
            </label>
            <Button onClick={() => { setPage(1); loadQueue(1); }} disabled={loading}>
              Apply Filters
            </Button>
          </div>
        </div>

        <div className="rounded-md border bg-white">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div className="text-sm text-gray-600">{claims.length} items</div>
            <div className="flex items-center gap-2">
              <Button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
              >
                Prev
              </Button>
              <span className="text-sm text-gray-600">Page {page}</span>
              <Button
                onClick={() => setPage((p) => p + 1)}
                disabled={claims.length < limit || loading}
              >
                Next
              </Button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={claims.length > 0 && selectedIds.size === claims.length}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th className="px-4 py-3 text-left">Claim</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Reviewer</th>
                  <th className="px-4 py-3 text-left">Media</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {claims.map((claim) => (
                  <tr key={claim.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(claim.id)}
                        onChange={() => toggleSelect(claim.id)}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{claim.claim_text}</div>
                      <div className="text-xs text-gray-500">Claim #{claim.id}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700">
                        {claim.review_status || 'pending'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      <div>ID: {claim.reviewer_id ?? '—'}</div>
                      <div>Group: {claim.review_group || '—'}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      <div>Media: {claim.media_id ?? '—'}</div>
                      <div>Chunk: {claim.chunk_index ?? '—'}</div>
                    </td>
                  </tr>
                ))}
                {!claims.length && !loading && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-500">
                      No claims in the review queue.
                    </td>
                  </tr>
                )}
                {loading && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-500">
                      Loading claims…
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-md border bg-white p-4">
          <div className="mb-3 text-lg font-semibold text-gray-800">Bulk Actions</div>
          <div className="grid gap-4 md:grid-cols-5">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Status</label>
              <select
                className="w-full rounded border px-3 py-2 text-sm"
                value={bulkStatus}
                onChange={(e) => setBulkStatus(e.target.value)}
              >
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Reviewer ID</label>
              <Input value={bulkReviewerId} onChange={(e) => setBulkReviewerId(e.target.value)} placeholder="optional" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Review group</label>
              <Input value={bulkReviewGroup} onChange={(e) => setBulkReviewGroup(e.target.value)} placeholder="optional" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Reason code</label>
              <Input value={bulkReasonCode} onChange={(e) => setBulkReasonCode(e.target.value)} placeholder="optional" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Notes</label>
              <Input value={bulkNotes} onChange={(e) => setBulkNotes(e.target.value)} placeholder="optional" />
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <Button onClick={handleBulkAction} disabled={loading || !selectedIds.size}>
              Apply to {selectedIds.size || 0} claims
            </Button>
            <Button variant="secondary" onClick={() => setSelectedIds(new Set())}>
              Clear selection
            </Button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
