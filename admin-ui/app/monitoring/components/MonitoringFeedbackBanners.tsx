import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertTriangle } from 'lucide-react';

type MonitoringFeedbackBannersProps = {
  error: string;
  success: string;
  activeAlertsCount: number;
};

export default function MonitoringFeedbackBanners({
  error,
  success,
  activeAlertsCount,
}: MonitoringFeedbackBannersProps) {
  return (
    <>
      <p
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        data-testid="monitoring-alert-count-live"
      >
        {activeAlertsCount} active alert
        {activeAlertsCount !== 1 ? 's' : ''} currently require attention.
      </p>

      {error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {success ? (
        <Alert className="mb-6 bg-green-50 border-green-200">
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      ) : null}

      {activeAlertsCount > 0 ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            {activeAlertsCount} active alert{activeAlertsCount !== 1 ? 's' : ''} require attention
          </AlertDescription>
        </Alert>
      ) : null}
    </>
  );
}
