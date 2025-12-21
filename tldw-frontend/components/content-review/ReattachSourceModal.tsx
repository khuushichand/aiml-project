import { useEffect, useId, useRef, type KeyboardEvent } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

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
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = dialog.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    const focusTarget = focusable[0] ?? dialog;
    focusTarget.focus();

    return () => {
      previouslyFocusedRef.current?.focus();
    };
  }, [isOpen]);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }

    if (event.key !== 'Tab') return;

    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = Array.from(
      dialog.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((node) => node.offsetParent !== null);

    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement as HTMLElement | null;

    if (event.shiftKey) {
      if (!active || active === first || !dialog.contains(active)) {
        event.preventDefault();
        last.focus();
      }
      return;
    }

    if (active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!isOpen) return null;

  const largeFileMb = Math.round(largeFileWarningBytes / (1024 * 1024));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl"
      >
        <div className="flex items-center justify-between">
          <h3 id={titleId} className="text-lg font-semibold">
            Reattach Source
          </h3>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
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
              type="file"
              label="Select file"
              onChange={(e) => onFileChange(e.target.files?.[0] || null)}
            />
            <p className="text-xs text-gray-500">
              Files upload during commit. Large files (over {largeFileMb} MB) may take longer.
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            <Input
              label="Source URL"
              placeholder="https://..."
              value={url}
              onChange={(e) => onUrlChange(e.target.value)}
            />
            <p className="text-xs text-gray-500">
              Some sources may require cookies or authentication.
            </p>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onSubmit}>
            Attach Source
          </Button>
        </div>
      </div>
    </div>
  );
}
