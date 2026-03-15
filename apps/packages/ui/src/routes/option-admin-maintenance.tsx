import OptionLayout from "~/components/Layouts/Layout"
import MaintenancePage from "@/components/Option/Admin/MaintenancePage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminMaintenance = () => {
  return (
    <RouteErrorBoundary routeId="admin-maintenance" routeLabel="Maintenance">
      <OptionLayout>
        <MaintenancePage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminMaintenance
