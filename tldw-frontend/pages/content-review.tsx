import type { Draft } from '@/types/content-review';
import type { DraftFileLoadResult } from '@/lib/drafts';
import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { useToast } from '@/components/ui/ToastProvider';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { DraftEditor } from '@/components/content-review/DraftEditor';
import { DraftListSidebar } from '@/components/content-review/DraftListSidebar';
import { ReattachSourceModal, type ReattachTab } from '@/components/content-review/ReattachSourceModal';
import { apiClient } from '@/lib/api';
import {
  getDraftFileAsset,
  getDraftFileForUpload,
  loadDrafts,
  persistDraft,
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

const mergeDrafts = (defaults: Draft[], stored: Draft[]) => {
  if (stored.length === 0) {
    return defaults;
  }
  const storedIds = new Set(stored.map((draft) => draft.id));
  const missingDefaults = defaults.filter((draft) => !storedIds.has(draft.id));
  return [...stored, ...missingDefaults];
};

type ContentReviewState = {
  drafts: Draft[];
  selectedId: string;
  editorText: string;
  keywordsInput: string;
  dirty: boolean;
  isOnline: boolean;
  reattachOpen: boolean;
  reattachTab: ReattachTab;
  reattachUrl: string;
  reattachFile: File | null;
  reattachError: string | null;
  draftsHydrated: boolean;
  isCommitting: boolean;
};

type ContentReviewAction =
  | { type: 'SET_DRAFTS'; drafts: Draft[] }
  | { type: 'UPDATE_DRAFT'; id: string; patch: Partial<Draft> }
  | { type: 'SET_SELECTED_ID'; selectedId: string }
  | { type: 'SYNC_EDITOR_FROM_DRAFT'; draft: Draft | null }
  | { type: 'SET_EDITOR_TEXT'; value: string }
  | { type: 'SET_KEYWORDS_INPUT'; value: string }
  | { type: 'SET_DIRTY'; value: boolean }
  | { type: 'SET_ONLINE'; value: boolean }
  | { type: 'OPEN_REATTACH' }
  | { type: 'CLOSE_REATTACH' }
  | { type: 'SET_REATTACH_TAB'; value: ReattachTab }
  | { type: 'SET_REATTACH_URL'; value: string }
  | { type: 'SET_REATTACH_FILE'; value: File | null }
  | { type: 'SET_REATTACH_ERROR'; value: string | null }
  | { type: 'SET_DRAFTS_HYDRATED'; value: boolean }
  | { type: 'SET_COMMITTING'; value: boolean };

const initialState: ContentReviewState = {
  drafts: seedDrafts,
  selectedId: seedDrafts[0]?.id || '',
  editorText: seedDrafts[0]?.content || '',
  keywordsInput: seedDrafts[0]?.keywords?.join(', ') || '',
  dirty: false,
  isOnline: true,
  reattachOpen: false,
  reattachTab: 'file',
  reattachUrl: '',
  reattachFile: null,
  reattachError: null,
  draftsHydrated: false,
  isCommitting: false,
};

const contentReviewReducer = (
  state: ContentReviewState,
  action: ContentReviewAction
): ContentReviewState => {
  switch (action.type) {
    case 'SET_DRAFTS':
      return { ...state, drafts: action.drafts };
    case 'UPDATE_DRAFT':
      return {
        ...state,
        drafts: state.drafts.map((draft) =>
          draft.id === action.id ? { ...draft, ...action.patch } : draft
        ),
      };
    case 'SET_SELECTED_ID':
      return { ...state, selectedId: action.selectedId };
    case 'SYNC_EDITOR_FROM_DRAFT':
      return {
        ...state,
        editorText: action.draft?.content || '',
        keywordsInput: action.draft?.keywords?.join(', ') || '',
        dirty: false,
      };
    case 'SET_EDITOR_TEXT':
      return { ...state, editorText: action.value };
    case 'SET_KEYWORDS_INPUT':
      return { ...state, keywordsInput: action.value };
    case 'SET_DIRTY':
      return { ...state, dirty: action.value };
    case 'SET_ONLINE':
      return { ...state, isOnline: action.value };
    case 'OPEN_REATTACH':
      return {
        ...state,
        reattachOpen: true,
        reattachTab: 'file',
        reattachUrl: '',
        reattachFile: null,
        reattachError: null,
      };
    case 'CLOSE_REATTACH':
      return { ...state, reattachOpen: false, reattachError: null };
    case 'SET_REATTACH_TAB':
      return { ...state, reattachTab: action.value };
    case 'SET_REATTACH_URL':
      return { ...state, reattachUrl: action.value };
    case 'SET_REATTACH_FILE':
      return { ...state, reattachFile: action.value };
    case 'SET_REATTACH_ERROR':
      return { ...state, reattachError: action.value };
    case 'SET_DRAFTS_HYDRATED':
      return { ...state, draftsHydrated: action.value };
    case 'SET_COMMITTING':
      return { ...state, isCommitting: action.value };
    default:
      return state;
  }
};

export default function ContentReviewPage() {
  const { show } = useToast();
  const [state, dispatch] = useReducer(contentReviewReducer, initialState);
  const assetsHydratedRef = useRef(false);
  const dirtyRef = useRef(false);
  const selectedIdRef = useRef(state.selectedId);
  const draftsRef = useRef(state.drafts);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pendingSelectionRef = useRef<string | null>(null);
  const selectedDraftRef = useRef<Draft | null>(null);

  const {
    drafts,
    selectedId,
    editorText,
    keywordsInput,
    dirty,
    isOnline,
    reattachOpen,
    reattachTab,
    reattachUrl,
    reattachFile,
    reattachError,
    draftsHydrated,
    isCommitting,
  } = state;

  const selectedDraft = useMemo(
    () => drafts.find((d) => d.id === selectedId) || null,
    [drafts, selectedId]
  );

  useEffect(() => {
    selectedDraftRef.current = selectedDraft;
  }, [selectedDraft]);

  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);

  const selectDraftWithConfirm = (nextId: string) => {
    if (nextId === selectedId) {
      return;
    }
    if (dirtyRef.current) {
      pendingSelectionRef.current = nextId;
      setConfirmOpen(true);
      return;
    }
    dispatch({ type: 'SET_SELECTED_ID', selectedId: nextId });
  };

  const handleConfirmSwitch = () => {
    const nextId = pendingSelectionRef.current;
    if (nextId) {
      dispatch({ type: 'SET_SELECTED_ID', selectedId: nextId });
    }
    pendingSelectionRef.current = null;
    setConfirmOpen(false);
  };

  const handleCancelSwitch = () => {
    pendingSelectionRef.current = null;
    setConfirmOpen(false);
  };

  useEffect(() => {
    dispatch({ type: 'SYNC_EDITOR_FROM_DRAFT', draft: selectedDraftRef.current });
  }, [selectedDraft?.id]); // Reset editor only when switching drafts, not on content changes

  useEffect(() => {
    const update = () =>
      dispatch({ type: 'SET_ONLINE', value: typeof navigator !== 'undefined' ? navigator.onLine : true });
    update();
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const hydrateDrafts = async () => {
      try {
        const storedDrafts = await loadDrafts();
        if (cancelled || storedDrafts.length === 0) {
          return;
        }
        const nextDrafts = mergeDrafts(seedDrafts, storedDrafts);
        const currentSelectedId = selectedIdRef.current;
        const nextSelectedId = nextDrafts.some((draft) => draft.id === currentSelectedId)
          ? currentSelectedId
          : nextDrafts[0]?.id || '';
        const selectionChanged = nextSelectedId !== currentSelectedId;

        dispatch({ type: 'SET_DRAFTS', drafts: nextDrafts });
        dispatch({ type: 'SET_SELECTED_ID', selectedId: nextSelectedId });

        if (!dirtyRef.current && !selectionChanged) {
          const selected = nextDrafts.find((draft) => draft.id === nextSelectedId) || null;
          dispatch({ type: 'SYNC_EDITOR_FROM_DRAFT', draft: selected });
        }
      } catch (err: unknown) {
        console.error('Failed to load stored drafts:', err);
      } finally {
        if (!cancelled) {
          dispatch({ type: 'SET_DRAFTS_HYDRATED', value: true });
        }
      }
    };

    void hydrateDrafts();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!draftsHydrated || assetsHydratedRef.current) {
      return;
    }
    assetsHydratedRef.current = true;
    let cancelled = false;

    const hydrateAssets = async () => {
      const draftSnapshot = draftsRef.current;
      const nextDrafts = await Promise.all(
        draftSnapshot.map(async (draft) => {
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

      const changed = nextDrafts.some((draft, index) => draft !== draftSnapshot[index]);
      if (changed) {
        dispatch({ type: 'SET_DRAFTS', drafts: nextDrafts });
      }
    };

    void hydrateAssets();

    return () => {
      cancelled = true;
    };
  }, [draftsHydrated]);

  const updateDraft = (id: string, patch: Partial<Draft>) => {
    dispatch({ type: 'UPDATE_DRAFT', id, patch });
  };

  const parseKeywords = (input: string) => {
    return input
      .split(',')
      .map((keyword) => keyword.trim())
      .filter(Boolean);
  };

  const handleKeywordsChange = (nextValue: string) => {
    dispatch({ type: 'SET_KEYWORDS_INPUT', value: nextValue });
    if (selectedDraft) {
      dispatch({ type: 'SET_DIRTY', value: true });
    }
  };

  const handleEditorChange = (value: string) => {
    dispatch({ type: 'SET_EDITOR_TEXT', value });
    if (selectedDraft) {
      dispatch({ type: 'SET_DIRTY', value: true });
    }
  };

  const saveDraft = async () => {
    if (!selectedDraft) return;
    const keywords = parseKeywords(keywordsInput);
    const updatedDraft = {
      ...selectedDraft,
      content: editorText,
      keywords,
    };
    try {
      await persistDraft(updatedDraft);
    } catch (err: unknown) {
      console.error('Failed to persist draft:', err);
      show({
        title: 'Save failed',
        description: 'Draft changes could not be saved locally.',
        variant: 'danger',
      });
      return;
    }
    updateDraft(selectedDraft.id, { content: editorText, keywords });
    dispatch({ type: 'SET_DIRTY', value: false });
    show({ title: 'Draft saved', variant: 'success' });
  };

  const openReattach = () => {
    dispatch({ type: 'OPEN_REATTACH' });
  };

  const closeReattachModal = () => {
    dispatch({ type: 'CLOSE_REATTACH' });
  };

  const validateCommit = (draft: Draft, content: string): boolean => {
    if (!draft.title.trim()) {
      show({
        title: 'Title required',
        description: 'Provide a title before committing.',
        variant: 'warning',
      });
      return false;
    }
    if (!content.trim()) {
      show({
        title: 'Content required',
        description: 'Provide content before committing.',
        variant: 'warning',
      });
      return false;
    }
    return true;
  };

  const buildCommitFormData = async (
    draft: Draft,
    keywords: string[]
  ): Promise<{ formData: FormData } | { formData: null; fileResult?: DraftFileLoadResult; message?: string }> => {
    const formData = new FormData();
    formData.append('media_type', draft.mediaType);
    formData.append('title', draft.title);
    formData.append('keywords', keywords.join(', '));

    if (draft.source?.kind === 'url' && draft.source.value) {
      formData.append('urls', draft.source.value);
      return { formData };
    }

    if (draft.source?.kind === 'file') {
      const fileResult = await getDraftFileForUpload(draft.id);
      if (!fileResult.file) {
        return { formData: null, fileResult };
      }
      formData.append('files', fileResult.file, fileResult.file.name);
      return { formData };
    }

    return {
      formData: null,
      message: 'Reattach a file or URL before committing.',
    };
  };

  const uploadMedia = async (formData: FormData): Promise<number> => {
    const addResponse = await apiClient.post<{ results?: Array<Record<string, unknown>> }>(
      '/media/add',
      formData
    );

    const results = Array.isArray(addResponse?.results) ? addResponse.results : [];
    const success = results.find(
      (result) =>
        typeof result?.db_id === 'number'
        && (result?.status === 'Success' || result?.status === 'success')
    );
    if (!success || typeof success.db_id !== 'number') {
      throw new Error('Media ingestion did not return a media id.');
    }

    return success.db_id;
  };

  const updateMediaMetadata = async (mediaId: number, draft: Draft) => {
    const safeMetadata: Record<string, string> = {
      content_review_draft_id: draft.id,
      content_review_media_type: draft.mediaType,
      content_review_source_kind: draft.source?.kind || 'unknown',
    };
    if (draft.source?.kind === 'url' && draft.source.value) {
      safeMetadata.content_review_source_value = draft.source.value;
    }
    if (draft.source?.kind === 'file' && draft.source.filename) {
      safeMetadata.content_review_source_filename = draft.source.filename;
    }

    try {
      await apiClient.patch(`/media/${mediaId}/metadata`, {
        safe_metadata: safeMetadata,
        merge: true,
        new_version: false,
      });
    } catch (err: unknown) {
      console.error('Failed to update metadata:', err);
      show({
        title: 'Metadata update failed',
        description: 'Content saved, but metadata update failed.',
        variant: 'warning',
      });
    }
  };

  const triggerReprocess = async (mediaId: number) => {
    try {
      await apiClient.post(`/media/${mediaId}/reprocess`, {
        perform_chunking: true,
        generate_embeddings: true,
      });
    } catch (err: unknown) {
      console.error('Failed to reprocess media:', err);
      show({
        title: 'Reprocess queued with issues',
        description: 'Content saved, but reprocessing failed. Try reprocessing later.',
        variant: 'warning',
      });
    }
  };

  const submitReattach = async () => {
    if (!selectedDraft) return;
    if (!isOnline) {
      dispatch({ type: 'SET_REATTACH_ERROR', value: 'You are offline. Reattach requires a connection.' });
      return;
    }

    if (reattachTab === 'file') {
      if (!reattachFile) {
        dispatch({ type: 'SET_REATTACH_ERROR', value: 'Select a file to attach.' });
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
        dispatch({
          type: 'SET_REATTACH_ERROR',
          value: 'Failed to save the attachment. Please try again.',
        });
        return;
      }
    } else {
      if (!reattachUrl.trim()) {
        dispatch({ type: 'SET_REATTACH_ERROR', value: 'Provide a valid URL.' });
        return;
      }
      try {
        const parsedUrl = new URL(reattachUrl.trim());
        if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
          dispatch({ type: 'SET_REATTACH_ERROR', value: 'URL must use http or https.' });
          return;
        }
      } catch {
        dispatch({ type: 'SET_REATTACH_ERROR', value: 'URL format looks invalid.' });
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

  const handleCommit = async () => {
    if (!selectedDraft) return;
    if (!isOnline) {
      show({
        title: 'Offline',
        description: 'Reconnect to commit this draft.',
        variant: 'warning',
      });
      return;
    }
    if (selectedDraft.assetStatus !== 'present') {
      show({
        title: 'Source required',
        description: 'Reattach the source before committing.',
        variant: 'warning',
      });
      return;
    }

    const isValid = validateCommit(selectedDraft, editorText);
    if (!isValid) {
      return;
    }

    dispatch({ type: 'SET_COMMITTING', value: true });
    try {
      const keywords = parseKeywords(keywordsInput);
      const formResult = await buildCommitFormData(selectedDraft, keywords);
      if (!formResult.formData) {
        if (formResult.fileResult) {
          updateDraft(selectedDraft.id, {
            assetStatus: formResult.fileResult.assetStatus,
            assetNote: formResult.fileResult.assetNote,
            source: formResult.fileResult.source ?? selectedDraft.source,
          });
          show({
            title: 'Source missing',
            description: formResult.fileResult.assetNote || 'Reattach the file to continue.',
            variant: 'warning',
          });
        } else {
          show({
            title: 'Source missing',
            description: formResult.message || 'Reattach a file or URL before committing.',
            variant: 'warning',
          });
        }
        return;
      }

      const mediaId = await uploadMedia(formResult.formData);

      await apiClient.put(`/media/${mediaId}`, {
        title: selectedDraft.title,
        content: editorText,
        keywords,
      });

      await updateMediaMetadata(mediaId, selectedDraft);
      await triggerReprocess(mediaId);

      updateDraft(selectedDraft.id, {
        content: editorText,
        keywords,
        status: 'reviewed',
      });
      dispatch({ type: 'SET_DIRTY', value: false });
      show({
        title: 'Committed',
        description: 'Draft has been committed.',
        variant: 'success',
      });
    } catch (err: unknown) {
      console.error('Commit failed:', err);
      const message = err instanceof Error ? err.message : 'Failed to commit draft.';
      show({
        title: 'Commit failed',
        description: message,
        variant: 'danger',
      });
    } finally {
      dispatch({ type: 'SET_COMMITTING', value: false });
    }
  };

  const commitDisabled = !selectedDraft || selectedDraft.assetStatus !== 'present' || !isOnline || isCommitting;

  return (
    <Layout>
      <div className="flex min-h-[calc(100vh-140px)] flex-col gap-6 lg:flex-row">
        <DraftListSidebar drafts={drafts} selectedId={selectedId} onSelect={selectDraftWithConfirm} />

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
        onTabChange={(value) => dispatch({ type: 'SET_REATTACH_TAB', value })}
        onUrlChange={(value) => dispatch({ type: 'SET_REATTACH_URL', value })}
        onFileChange={(value) => dispatch({ type: 'SET_REATTACH_FILE', value })}
        onClose={closeReattachModal}
        onSubmit={submitReattach}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Discard unsaved changes?"
        message="You have unsaved edits in this draft. Discard them and switch drafts?"
        confirmText="Discard changes"
        cancelText="Keep editing"
        destructive
        onConfirm={handleConfirmSwitch}
        onCancel={handleCancelSwitch}
      />
    </Layout>
  );
}
