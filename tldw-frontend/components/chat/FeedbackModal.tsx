import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/Button';

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
  if (!open) return null;

  const toggleIssue = (issueId: string) => {
    onIssuesChange(
      issues.includes(issueId)
        ? issues.filter((item) => item !== issueId)
        : [...issues, issueId]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-lg bg-white p-4 shadow-xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Feedback</h3>
          <button
            type="button"
            className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
            onClick={onClose}
            aria-label="Close feedback dialog"
          >
            Close
          </button>
        </div>

        <div className="mb-4">
          <div className="text-sm font-medium text-gray-800">How would you rate this response?</div>
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
                    active ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-300 text-gray-500 hover:bg-gray-100'
                  )}
                  onClick={() => onRatingChange(ratingValue)}
                  aria-label={`Rate ${ratingValue} out of 5`}
                >
                  {ratingValue}
                </button>
              );
            })}
            {rating > 0 && (
              <span className="text-xs text-gray-500">{rating}/5</span>
            )}
          </div>
        </div>

        <div className="mb-4">
          <div className="text-sm font-medium text-gray-800">What was the issue? (select all that apply)</div>
          <div className="mt-2 grid grid-cols-1 gap-2 text-sm text-gray-700 sm:grid-cols-2">
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
          <label className="text-sm font-medium text-gray-800" htmlFor="feedback-notes">
            Additional comments (optional)
          </label>
          <textarea
            id="feedback-notes"
            className="mt-2 w-full rounded border border-gray-300 p-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
