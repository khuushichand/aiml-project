'use client';

import { Suspense } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import MonitoringFeedbackBanners from './components/MonitoringFeedbackBanners';
import MonitoringManagementPanels from './components/MonitoringManagementPanels';
import MonitoringMetricsSection from './components/MonitoringMetricsSection';
import MonitoringPageHeader from './components/MonitoringPageHeader';
import { useMonitoringPageController } from './use-monitoring-page-controller';

function MonitoringPageContent() {
  const {
    headerProps,
    feedbackBannersProps,
    metricsSectionProps,
    managementPanelsProps,
  } = useMonitoringPageController();

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <MonitoringPageHeader {...headerProps} />
          <MonitoringFeedbackBanners {...feedbackBannersProps} />
          <MonitoringMetricsSection {...metricsSectionProps} />
          <MonitoringManagementPanels {...managementPanelsProps} />
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}

// Suspense boundary required: useMonitoringPageController uses useSearchParams(),
// which Next.js requires to be wrapped in Suspense for static generation.
export default function MonitoringPage() {
  return (
    <Suspense fallback={<div className="p-4 lg:p-8 text-muted-foreground">Loading monitoring...</div>}>
      <MonitoringPageContent />
    </Suspense>
  );
}
