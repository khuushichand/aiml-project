import OptionLayout from "~/components/Layouts/Layout"
import DataOpsPage from "@/components/Option/Admin/DataOpsPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminDataOps = () => {
  return (
    <RouteErrorBoundary routeId="admin-data-ops" routeLabel="Data Operations">
      <OptionLayout>
        <DataOpsPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminDataOps
