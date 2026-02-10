import type { Draft } from '@web/types/content-review';
import { Button } from '@web/components/ui/Button';
import { Input } from '@web/components/ui/Input';
import { formatStatus } from '@web/components/content-review/utils';

type DraftEditorProps = {
  draft: Draft;
  isOnline: boolean;
  dirty: boolean;
  editorText: string;
  keywordsInput: string;
  commitDisabled: boolean;
  onOpenReattach: () => void;
  onSaveDraft: () => void;
  onEditorChange: (value: string) => void;
  onKeywordsChange: (value: string) => void;
  onCommit: () => void;
};

export function DraftEditor({
  draft,
  isOnline,
  dirty,
  editorText,
  keywordsInput,
  commitDisabled,
  onOpenReattach,
  onSaveDraft,
  onEditorChange,
  onKeywordsChange,
  onCommit,
}: DraftEditorProps) {
  const needsSource = draft.assetStatus !== 'present';

  return (
    <div className="flex h-full flex-col gap-4">
      {!isOnline && (
        <div className="rounded-md border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-warn">
          You are offline. Commit actions are disabled until connection is restored.
        </div>
      )}
      {needsSource && (
        <div className="rounded-md border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          Source required to commit this item. Reattach the original file or URL.
        </div>
      )}
      {draft.assetNote && (
        <div className="rounded-md border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-primary">
          {draft.assetNote}
        </div>
      )}
      <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-xl font-semibold">{draft.title}</h2>
            <p className="text-sm text-text-muted">
              {draft.mediaType} • {formatStatus(draft.status)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {needsSource && (
              <Button variant="secondary" onClick={onOpenReattach}>
                Reattach Source
              </Button>
            )}
            <Button variant="ghost" onClick={onSaveDraft} disabled={!dirty}>
              Save Draft
            </Button>
          </div>
        </div>
        <div className="mt-4">
          <textarea
            aria-label="Draft content editor"
            value={editorText}
            onChange={(e) => onEditorChange(e.target.value)}
            className="min-h-[320px] w-full rounded-md border border-border p-3 font-mono text-sm focus:border-primary focus:ring-primary"
          />
          <div className="mt-2 text-xs text-text-muted">
            {editorText.trim().split(/\s+/).filter(Boolean).length} words
            {dirty ? ' • Unsaved changes' : ' • Saved'}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-text">Metadata</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Input label="Title" value={draft.title} readOnly />
          <Input
            label="Keywords"
            placeholder="comma-separated"
            value={keywordsInput}
            onChange={(event) => onKeywordsChange(event.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4 shadow-sm">
        <div className="text-sm text-text-muted">
          {commitDisabled ? 'Commit disabled until source is attached.' : 'Ready to commit.'}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span title="Not yet implemented" className="inline-flex">
            <Button variant="danger" disabled>
              Discard
            </Button>
          </span>
          <span title="Not yet implemented" className="inline-flex">
            <Button variant="secondary" disabled>
              Mark Reviewed
            </Button>
          </span>
          <Button variant="primary" disabled={commitDisabled} onClick={onCommit}>
            Commit
          </Button>
        </div>
      </div>
    </div>
  );
}
