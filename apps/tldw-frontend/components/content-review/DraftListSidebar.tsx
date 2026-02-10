import type { Draft } from '@web/types/content-review';
import { Badge } from '@web/components/ui/Badge';
import { formatStatus } from '@web/components/content-review/utils';

type DraftListSidebarProps = {
  drafts: Draft[];
  selectedId: string;
  onSelect: (id: string) => void;
};

export function DraftListSidebar({ drafts, selectedId, onSelect }: DraftListSidebarProps) {
  return (
    <aside className="w-full lg:w-80">
      <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Batch</h2>
          <Badge>{drafts.length} items</Badge>
        </div>
        <div className="space-y-2">
          {drafts.map((draft) => (
            <button
              key={draft.id}
              type="button"
              onClick={() => onSelect(draft.id)}
              className={`w-full rounded-md border px-3 py-2 text-left transition ${
                draft.id === selectedId
                  ? 'border-primary bg-primary/10'
                  : 'border-border hover:border-border-strong hover:bg-elevated'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{draft.title}</span>
                {draft.assetStatus !== 'present' && (
                  <Badge variant={draft.assetStatus === 'pending' ? 'warning' : 'danger'}>
                    {draft.assetStatus === 'pending' ? 'Source pending' : 'Source missing'}
                  </Badge>
                )}
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs text-text-muted">
                <span>{draft.mediaType}</span>
                <span>•</span>
                <span>{formatStatus(draft.status)}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
