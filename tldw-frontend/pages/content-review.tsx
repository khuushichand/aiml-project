import type { Draft } from '@/types/content-review';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { useToast } from '@/components/ui/ToastProvider';
import { DraftEditor } from '@/components/content-review/DraftEditor';
import { DraftListSidebar } from '@/components/content-review/DraftListSidebar';
import { ReattachSourceModal, type ReattachTab } from '@/components/content-review/ReattachSourceModal';
import {
  getDraftFileAsset,
  persistDraftFileAsset,
  requestFileHandleForFile,
  resolveDraftFileAssetStatus,
} from '@/lib/drafts';

const LARGE_FILE_WARNING_BYTES = 100 * 1024 * 1024;

const seedDrafts: Draft[] = [
  {
    id: 'draft-1',
    title: 'Interview Transcript',
    status: 'in_progress',
    mediaType: 'audio',
    content: '# Interview Highlights\n\n- Speaker A: ...\n- Speaker B: ...',
    keywords: ['interview', 'audio'],
    assetStatus: 'missing',
  },
  {
    id: 'draft-2',
    title: 'Research Notes',
    status: 'pending',
    mediaType: 'document',
    content: '## Notes\n\nCleaned up summary content goes here.',
    keywords: ['research', 'notes'],
    assetStatus: 'present',
    source: { kind: 'url', value: 'https://example.com/article' },
  },
];

export default function ContentReviewPage() {
  const { show } = useToast();
  const [drafts, setDrafts] = useState<Draft[]>(seedDrafts);
  const [selectedId, setSelectedId] = useState<string>(seedDrafts[0]?.id || '');
  const [editorText, setEditorText] = useState<string>(seedDrafts[0]?.content || '');
  const [keywordsInput, setKeywordsInput] = useState<string>(
    seedDrafts[0]?.keywords?.join(', ') || ''
  );
  const [dirty, setDirty] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [reattachOpen, setReattachOpen] = useState(false);
  const [reattachTab, setReattachTab] = useState<ReattachTab>('file');
  const [reattachUrl, setReattachUrl] = useState('');
  const [reattachFile, setReattachFile] = useState<File | null>(null);
  const [reattachError, setReattachError] = useState<string | null>(null);
  const assetsHydratedRef = useRef(false);

  const selectedDraft = useMemo(
    () => drafts.find((d) => d.id === selectedId) || null,
    [drafts, selectedId]
  );

  useEffect(() => {
    setEditorText(selectedDraft?.content || '');
    setKeywordsInput(selectedDraft?.keywords?.join(', ') || '');
    setDirty(false);
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

  useEffect(() => {
    if (assetsHydratedRef.current) {
      return;
    }
    assetsHydratedRef.current = true;
    let cancelled = false;

    const hydrateAssets = async () => {
      const nextDrafts = await Promise.all(
        drafts.map(async (draft) => {
          if (draft.source?.kind !== 'file') {
            return draft;
          }
          const asset = await getDraftFileAsset(draft.id);
          const resolved = await resolveDraftFileAssetStatus(asset);
          if (
            resolved.assetStatus === draft.assetStatus &&
            resolved.assetNote === draft.assetNote &&
            (!resolved.source || resolved.source.filename === draft.source?.filename)
          ) {
            return draft;
          }
          return {
            ...draft,
            assetStatus: resolved.assetStatus,
            assetNote: resolved.assetNote,
            source: resolved.source ?? draft.source,
          };
        })
      );

      if (cancelled) {
        return;
      }

      const changed = nextDrafts.some((draft, index) => draft !== drafts[index]);
      if (changed) {
        setDrafts(nextDrafts);
      }
    };

    void hydrateAssets();

    return () => {
      cancelled = true;
    };
  }, [drafts]);

  const updateDraft = (id: string, patch: Partial<Draft>) => {
    setDrafts((prev) => prev.map((d) => (d.id === id ? { ...d, ...patch } : d)));
  };

  const handleKeywordsChange = (nextValue: string) => {
    setKeywordsInput(nextValue);
    if (selectedDraft) {
      setDirty(true);
    }
  };

  const handleEditorChange = (value: string) => {
    setEditorText(value);
    setDirty(true);
  };

  const saveDraft = () => {
    if (!selectedDraft) return;
    const keywords = keywordsInput
      .split(',')
      .map((keyword) => keyword.trim())
      .filter(Boolean);
    updateDraft(selectedDraft.id, { content: editorText, keywords });
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

  const closeReattachModal = () => {
    setReattachOpen(false);
    setReattachError(null);
  };

  const submitReattach = async () => {
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
      try {
        const oversized = reattachFile.size > LARGE_FILE_WARNING_BYTES;
        let fileHandle: FileSystemFileHandle | null = null;
        if (oversized) {
          fileHandle = await requestFileHandleForFile(reattachFile);
        }
        const persisted = await persistDraftFileAsset({
          draftId: selectedDraft.id,
          file: reattachFile,
          maxInlineBytes: LARGE_FILE_WARNING_BYTES,
          fileHandle,
        });
        updateDraft(selectedDraft.id, {
          assetStatus: persisted.assetStatus,
          source: persisted.source,
          assetNote: persisted.assetNote,
        });
        const needsReselect = persisted.assetStatus === 'pending';
        show({
          title: needsReselect
            ? 'Large file requires re-selection'
            : oversized
              ? 'Large file linked'
              : 'Source attached',
          description: persisted.assetNote || 'Upload will happen on commit.',
          variant: needsReselect || oversized ? 'warning' : 'success',
        });
      } catch (err: unknown) {
        console.error('Failed to persist draft asset:', err);
        setReattachError('Failed to save the attachment. Please try again.');
        return;
      }
    } else {
      if (!reattachUrl.trim()) {
        setReattachError('Provide a valid URL.');
        return;
      }
      try {
        const parsedUrl = new URL(reattachUrl.trim());
        if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
          setReattachError('URL must use http or https.');
          return;
        }
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

    closeReattachModal();
  };

  const handleCommit = () => {
    if (!selectedDraft) return;
    // TODO: wire commit action to upload/service call when backend is ready.
    show({
      title: 'Committed',
      description: 'Draft has been committed.',
      variant: 'success',
    });
  };

  const commitDisabled = !selectedDraft || selectedDraft.assetStatus !== 'present' || !isOnline;

  return (
    <Layout>
      <div className="flex min-h-[calc(100vh-140px)] flex-col gap-6 lg:flex-row">
        <DraftListSidebar drafts={drafts} selectedId={selectedId} onSelect={setSelectedId} />

        <section className="flex-1">
          {!selectedDraft ? (
            <div className="rounded-lg border border-dashed border-gray-300 p-10 text-center text-gray-500">
              No drafts selected.
            </div>
          ) : (
            <DraftEditor
              draft={selectedDraft}
              isOnline={isOnline}
              dirty={dirty}
              editorText={editorText}
              keywordsInput={keywordsInput}
              reattachError={reattachError}
              commitDisabled={commitDisabled}
              onOpenReattach={openReattach}
              onSaveDraft={saveDraft}
              onEditorChange={handleEditorChange}
              onKeywordsChange={handleKeywordsChange}
              onCommit={handleCommit}
            />
          )}
        </section>
      </div>

      <ReattachSourceModal
        isOpen={reattachOpen}
        tab={reattachTab}
        url={reattachUrl}
        error={reattachError}
        largeFileWarningBytes={LARGE_FILE_WARNING_BYTES}
        onTabChange={setReattachTab}
        onUrlChange={setReattachUrl}
        onFileChange={setReattachFile}
        onClose={closeReattachModal}
        onSubmit={submitReattach}
      />
    </Layout>
  );
}
