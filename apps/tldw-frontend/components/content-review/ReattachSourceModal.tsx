import * as Dialog from '@radix-ui/react-dialog';
import { Button } from '@web/components/ui/Button';
import { Input } from '@web/components/ui/Input';

export type ReattachTab = 'file' | 'url';

type ReattachSourceModalProps = {
  isOpen: boolean;
  tab: ReattachTab;
  url: string;
  error: string | null;
  largeFileWarningBytes: number;
  onTabChange: (tab: ReattachTab) => void;
  onUrlChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
  onClose: () => void;
  onSubmit: () => void;
};

export function ReattachSourceModal({
  isOpen,
  tab,
  url,
  error,
  largeFileWarningBytes,
  onTabChange,
  onUrlChange,
  onFileChange,
  onClose,
  onSubmit,
}: ReattachSourceModalProps) {
  const largeFileMb = Math.round(largeFileWarningBytes / (1024 * 1024));
  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg bg-surface p-6 shadow-xl"
        >
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-lg font-semibold">
              Reattach Source
            </Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost">
                Close
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-2 text-sm text-text-muted">
            Attach the original file or URL to enable commit actions.
          </Dialog.Description>
          <div className="mt-4 flex gap-2">
            <Button
              variant={tab === 'file' ? 'primary' : 'secondary'}
              onClick={() => onTabChange('file')}
            >
              Upload File
            </Button>
            <Button
              variant={tab === 'url' ? 'primary' : 'secondary'}
              onClick={() => onTabChange('url')}
            >
              Provide URL
            </Button>
          </div>

          {tab === 'file' ? (
            <div className="mt-4 space-y-3">
              <Input
                key="reattach-file"
                type="file"
                label="Select file"
                onChange={(e) => onFileChange(e.target.files?.[0] || null)}
              />
              <p className="text-xs text-text-muted">
                Files upload during commit. Large files (over {largeFileMb} MB) may take longer.
              </p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <Input
                key="reattach-url"
                label="Source URL"
                placeholder="https://..."
                value={url ?? ''}
                onChange={(e) => onUrlChange(e.target.value)}
              />
              <p className="text-xs text-text-muted">
                Some sources may require cookies or authentication.
              </p>
            </div>
          )}

          {error && (
            <div className="mt-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="secondary">
                Cancel
              </Button>
            </Dialog.Close>
            <Button variant="primary" onClick={onSubmit}>
              Attach Source
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
