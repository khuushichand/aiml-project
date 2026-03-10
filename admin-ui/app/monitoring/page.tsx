'use client';

import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import MonitoringFeedbackBanners from './components/MonitoringFeedbackBanners';
import MonitoringManagementPanels from './components/MonitoringManagementPanels';
import MonitoringMetricsSection from './components/MonitoringMetricsSection';
import MonitoringPageHeader from './components/MonitoringPageHeader';
import { useMonitoringPageController } from './use-monitoring-page-controller';

export default function MonitoringPage() {
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
