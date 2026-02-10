import { useEffect, useId, useRef, type KeyboardEvent } from 'react';
import { cn } from '@web/lib/utils';
import { Button } from '@web/components/ui/Button';

export type FeedbackIssueOption = {
  id: string;
  label: string;
};

type FeedbackModalProps = {
  open: boolean;
  rating: number;
  issues: string[];
  notes: string;
  submitting: boolean;
  issueOptions: FeedbackIssueOption[];
  onClose: () => void;
  onSubmit: () => void;
  onRatingChange: (rating: number) => void;
  onIssuesChange: (issues: string[]) => void;
  onNotesChange: (notes: string) => void;
};

const getFocusableElements = (container: HTMLElement | null): HTMLElement[] => {
  if (!container) return [];
  const selectors = [
    'button:not([disabled])',
    '[href]',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ];
  return Array.from(container.querySelectorAll<HTMLElement>(selectors.join(',')))
    .filter((el) => !el.hasAttribute('disabled'))
    .filter((el) => el.getAttribute('aria-hidden') !== 'true')
    .filter((el) => el.offsetParent !== null);
};

export function FeedbackModal({
  open,
  rating,
  issues,
  notes,
  submitting,
  issueOptions,
  onClose,
  onSubmit,
  onRatingChange,
  onIssuesChange,
  onNotesChange,
}: FeedbackModalProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;

    const focusDialog = () => {
      const focusable = getFocusableElements(dialogRef.current);
      if (focusable.length > 0) {
        focusable[0].focus();
        return;
      }
      dialogRef.current?.focus();
    };

    const supportsRaf = typeof window.requestAnimationFrame === 'function';
    const schedule = supportsRaf
      ? window.requestAnimationFrame
      : (cb: () => void) => window.setTimeout(cb, 0);
    const cancelSchedule = supportsRaf
      ? window.cancelAnimationFrame
      : window.clearTimeout;
    const scheduleId = schedule(focusDialog);

    return () => {
      cancelSchedule(scheduleId);
      const previous = previousFocusRef.current;
      if (previous && document.contains(previous)) {
        previous.focus();
      }
      previousFocusRef.current = null;
    };
  }, [open]);

  if (!open) return null;

  const toggleIssue = (issueId: string) => {
    onIssuesChange(
      issues.includes(issueId)
        ? issues.filter((item) => item !== issueId)
        : [...issues, issueId]
    );
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') {
      return;
    }
    const dialogEl = dialogRef.current;
    const focusable = getFocusableElements(dialogEl);
    if (!dialogEl || focusable.length === 0) {
      event.preventDefault();
      dialogEl?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement as HTMLElement | null;
    if (active && !dialogEl.contains(active)) {
      event.preventDefault();
      first.focus();
      return;
    }
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden="true" />
      <div
        className="relative z-10 w-full max-w-lg rounded-lg bg-surface p-4 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={dialogRef}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 id={titleId} className="text-lg font-semibold text-text">Feedback</h3>
          <button
            type="button"
            className="rounded border border-border px-2 py-1 text-xs text-text-muted hover:bg-surface2"
            onClick={onClose}
            aria-label="Close feedback dialog"
          >
            Close
          </button>
        </div>

        <div className="mb-4">
          <div className="text-sm font-medium text-text">How would you rate this response?</div>
          <div className="mt-2 flex items-center gap-2">
            {Array.from({ length: 5 }).map((_, idx) => {
              const ratingValue = idx + 1;
              const active = ratingValue <= rating;
              return (
                <button
                  key={`rating-${ratingValue}`}
                  type="button"
                  className={cn(
                    'h-8 w-8 rounded-full border text-sm font-semibold transition',
                    active ? 'border-primary bg-primary/10 text-primary' : 'border-border text-text-muted hover:bg-surface2'
                  )}
                  onClick={() => onRatingChange(ratingValue)}
                  aria-label={`Rate ${ratingValue} out of 5`}
                >
                  {ratingValue}
                </button>
              );
            })}
            {rating > 0 && (
              <span className="text-xs text-text-muted">{rating}/5</span>
            )}
          </div>
        </div>

        <div className="mb-4">
          <div className="text-sm font-medium text-text">What was the issue? (select all that apply)</div>
          <div className="mt-2 grid grid-cols-1 gap-2 text-sm text-text sm:grid-cols-2">
            {issueOptions.map((issue) => (
              <label key={issue.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={issues.includes(issue.id)}
                  onChange={() => toggleIssue(issue.id)}
                />
                <span>{issue.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="mb-4">
          <label className="text-sm font-medium text-text" htmlFor="feedback-notes">
            Additional comments (optional)
          </label>
          <textarea
            id="feedback-notes"
            className="mt-2 w-full rounded border border-border p-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            rows={4}
            value={notes}
            onChange={(event) => onNotesChange(event.target.value)}
            placeholder="Share extra context to help improve responses..."
          />
        </div>

        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={submitting}>
            Submit Feedback
          </Button>
        </div>
      </div>
    </div>
  );
}
