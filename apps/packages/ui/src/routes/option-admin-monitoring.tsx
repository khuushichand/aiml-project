import OptionLayout from "~/components/Layouts/Layout"
import MonitoringDashboardPage from "@/components/Option/Admin/MonitoringDashboardPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminMonitoring = () => {
  return (
    <RouteErrorBoundary routeId="admin-monitoring" routeLabel="Monitoring">
      <OptionLayout>
        <MonitoringDashboardPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminMonitoring
