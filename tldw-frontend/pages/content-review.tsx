import { useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { useToast } from '@/components/ui/ToastProvider';

type DraftStatus = 'pending' | 'in_progress' | 'reviewed';
type AssetStatus = 'present' | 'missing';
type AssetKind = 'url' | 'file' | 'stream';

type DraftSource = {
  kind: AssetKind;
  value?: string;
  filename?: string;
};

type Draft = {
  id: string;
  title: string;
  status: DraftStatus;
  mediaType: string;
  content: string;
  assetStatus: AssetStatus;
  source?: DraftSource;
  assetNote?: string;
};

const MAX_LOCAL_BYTES = 100 * 1024 * 1024;

const seedDrafts: Draft[] = [
  {
    id: 'draft-1',
    title: 'Interview Transcript',
    status: 'in_progress',
    mediaType: 'audio',
    content: '# Interview Highlights\n\n- Speaker A: ...\n- Speaker B: ...',
    assetStatus: 'missing',
  },
  {
    id: 'draft-2',
    title: 'Research Notes',
    status: 'pending',
    mediaType: 'document',
    content: '## Notes\n\nCleaned up summary content goes here.',
    assetStatus: 'present',
    source: { kind: 'url', value: 'https://example.com/article' },
  },
];

export default function ContentReviewPage() {
  const { show } = useToast();
  const [drafts, setDrafts] = useState<Draft[]>(seedDrafts);
  const [selectedId, setSelectedId] = useState<string>(seedDrafts[0]?.id || '');
  const [editorText, setEditorText] = useState<string>(seedDrafts[0]?.content || '');
  const [dirty, setDirty] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [reattachOpen, setReattachOpen] = useState(false);
  const [reattachTab, setReattachTab] = useState<'file' | 'url'>('file');
  const [reattachUrl, setReattachUrl] = useState('');
  const [reattachFile, setReattachFile] = useState<File | null>(null);
  const [reattachError, setReattachError] = useState<string | null>(null);

  const selectedDraft = useMemo(
    () => drafts.find((d) => d.id === selectedId) || null,
    [drafts, selectedId]
  );

  useEffect(() => {
    setEditorText(selectedDraft?.content || '');
    setDirty(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDraft?.id]); // Reset editor only when switching drafts, not on content changes

  useEffect(() => {
    const update = () => setIsOnline(typeof navigator !== 'undefined' ? navigator.onLine : true);
    update();
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);

  const updateDraft = (id: string, patch: Partial<Draft>) => {
    setDrafts((prev) => prev.map((d) => (d.id === id ? { ...d, ...patch } : d)));
  };

  const saveDraft = () => {
    if (!selectedDraft) return;
    updateDraft(selectedDraft.id, { content: editorText });
    setDirty(false);
    show({ title: 'Draft saved', variant: 'success' });
  };

  const openReattach = () => {
    setReattachTab('file');
    setReattachUrl('');
    setReattachFile(null);
    setReattachError(null);
    setReattachOpen(true);
  };

  const submitReattach = () => {
    if (!selectedDraft) return;
    if (!isOnline) {
      setReattachError('You are offline. Reattach requires a connection.');
      return;
    }

    if (reattachTab === 'file') {
      if (!reattachFile) {
        setReattachError('Select a file to attach.');
        return;
      }
      const oversized = reattachFile.size > MAX_LOCAL_BYTES;
      updateDraft(selectedDraft.id, {
        assetStatus: 'present',
        source: { kind: 'file', filename: reattachFile.name },
        assetNote: oversized
          ? 'File exceeds local storage limit. It will upload on commit.'
          : 'File stored locally.',
      });
      show({
        title: oversized ? 'Source attached for commit' : 'Source attached',
        description: oversized ? 'Local storage skipped for large file.' : undefined,
        variant: oversized ? 'warning' : 'success',
      });
    } else {
      if (!reattachUrl.trim()) {
        setReattachError('Provide a valid URL.');
        return;
      }
      try {
        new URL(reattachUrl.trim());
      } catch {
        setReattachError('URL format looks invalid.');
        return;
      }
      updateDraft(selectedDraft.id, {
        assetStatus: 'present',
        source: { kind: 'url', value: reattachUrl.trim() },
        assetNote: 'URL attached for commit.',
      });
      show({ title: 'Source URL attached', variant: 'success' });
    }

    setReattachOpen(false);
    setReattachError(null);
  };

  const commitDisabled = !selectedDraft || selectedDraft.assetStatus === 'missing' || !isOnline;

  return (
    <Layout>
      <div className="flex min-h-[calc(100vh-140px)] flex-col gap-6 lg:flex-row">
        <aside className="w-full lg:w-80">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Batch</h2>
              <Badge>{drafts.length} items</Badge>
            </div>
            <div className="space-y-2">
              {drafts.map((draft) => (
                <button
                  key={draft.id}
                  type="button"
                  onClick={() => setSelectedId(draft.id)}
                  className={`w-full rounded-md border px-3 py-2 text-left transition ${
                    draft.id === selectedId
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{draft.title}</span>
                    {draft.assetStatus === 'missing' && (
                      <Badge variant="danger">Source missing</Badge>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                    <span>{draft.mediaType}</span>
                    <span>•</span>
                    <span>{draft.status.replace('_', ' ')}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="flex-1">
          {!selectedDraft ? (
            <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center text-gray-500">
              No drafts selected.
            </div>
          ) : (
            <div className="flex h-full flex-col gap-4">
              {!isOnline && (
                <div className="rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
                  You are offline. Commit actions are disabled until connection is restored.
                </div>
              )}
              {selectedDraft.assetStatus === 'missing' && (
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  Source required to commit this item. Reattach the original file or URL.
                </div>
              )}
              {selectedDraft.assetNote && (
                <div className="rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  {selectedDraft.assetNote}
                </div>
              )}
              {reattachError && (
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {reattachError}
                </div>
              )}

              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-xl font-semibold">{selectedDraft.title}</h2>
                    <p className="text-sm text-gray-500">
                      {selectedDraft.mediaType} • {selectedDraft.status.replace('_', ' ')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedDraft.assetStatus === 'missing' && (
                      <Button variant="secondary" onClick={openReattach}>
                        Reattach Source
                      </Button>
                    )}
                    <Button variant="ghost" onClick={saveDraft} disabled={!dirty}>
                      Save Draft
                    </Button>
                  </div>
                </div>
                <div className="mt-4">
                  <textarea
                    value={editorText}
                    onChange={(e) => {
                      setEditorText(e.target.value);
                      setDirty(true);
                    }}
                    className="min-h-[320px] w-full rounded-md border border-gray-200 p-3 font-mono text-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                  <div className="mt-2 text-xs text-gray-500">
                    {editorText.trim().split(/\s+/).filter(Boolean).length} words
                    {dirty ? ' • Unsaved changes' : ' • Saved'}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-700">Metadata</h3>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <Input label="Title" value={selectedDraft.title} readOnly />
                  <Input label="Keywords" placeholder="comma-separated" />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <div className="text-sm text-gray-500">
                  {commitDisabled ? 'Commit disabled until source is attached.' : 'Ready to commit.'}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="danger" disabled title="Not yet implemented">
                    Discard
                  </Button>
                  <Button variant="secondary" disabled title="Not yet implemented">
                    Mark Reviewed
                  </Button>
                  <Button variant="primary" disabled={commitDisabled}>
                    Commit
                  </Button>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>

      {reattachOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Reattach Source</h3>
              <Button
                variant="ghost"
                onClick={() => {
                  setReattachOpen(false);
                  setReattachError(null);
                }}
              >
                Close
              </Button>
            </div>
            <div className="mt-4 flex gap-2">
              <Button
                variant={reattachTab === 'file' ? 'primary' : 'secondary'}
                onClick={() => setReattachTab('file')}
              >
                Upload File
              </Button>
              <Button
                variant={reattachTab === 'url' ? 'primary' : 'secondary'}
                onClick={() => setReattachTab('url')}
              >
                Provide URL
              </Button>
            </div>

            {reattachTab === 'file' ? (
              <div className="mt-4 space-y-3">
                <Input
                  type="file"
                  label="Select file"
                  onChange={(e) => setReattachFile(e.target.files?.[0] || null)}
                />
                <p className="text-xs text-gray-500">
                  Max local storage: 100 MB. Larger files will upload during commit.
                </p>
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                <Input
                  label="Source URL"
                  placeholder="https://..."
                  value={reattachUrl}
                  onChange={(e) => setReattachUrl(e.target.value)}
                />
                <p className="text-xs text-gray-500">
                  Some sources may require cookies or authentication.
                </p>
              </div>
            )}

            {reattachError && (
              <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {reattachError}
              </div>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setReattachOpen(false);
                  setReattachError(null);
                }}
              >
                Cancel
              </Button>
              <Button variant="primary" onClick={submitReattach}>
                Attach Source
              </Button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
