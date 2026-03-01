'use client';

import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import {
  normalizeMonitoringHealthStatus,
} from '@/lib/monitoring-health';
import MonitoringFeedbackBanners from './components/MonitoringFeedbackBanners';
import MonitoringManagementPanels from './components/MonitoringManagementPanels';
import MonitoringMetricsSection from './components/MonitoringMetricsSection';
import MonitoringPageHeader from './components/MonitoringPageHeader';
import { useMonitoringPageController } from './use-monitoring-page-controller';
import type { SystemHealthStatus } from './types';

export const normalizeHealthStatus = (status?: string): SystemHealthStatus => {
  return normalizeMonitoringHealthStatus(status);
};

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
