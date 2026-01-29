'use client';

import { useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import { BackupsSection } from '@/components/data-ops/BackupsSection';
import { RetentionPoliciesSection } from '@/components/data-ops/RetentionPoliciesSection';
import { ExportsSection } from '@/components/data-ops/ExportsSection';
import { MaintenanceSection } from '@/components/data-ops/MaintenanceSection';

export default function DataOpsPage() {
  const [refreshSignal, setRefreshSignal] = useState(0);

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-2xl font-bold">Data Ops</h2>
              <p className="text-muted-foreground">Backups, retention, and export tools.</p>
            </div>
            <Button variant="outline" onClick={() => setRefreshSignal((prev) => prev + 1)}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>

          <BackupsSection refreshSignal={refreshSignal} />
          <RetentionPoliciesSection refreshSignal={refreshSignal} />
          <ExportsSection refreshSignal={refreshSignal} />
          <MaintenanceSection refreshSignal={refreshSignal} />
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
