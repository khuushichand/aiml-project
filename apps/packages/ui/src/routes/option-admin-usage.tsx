import OptionLayout from "~/components/Layouts/Layout"
import UsageAnalyticsPage from "@/components/Option/Admin/UsageAnalyticsPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminUsage = () => {
  return (
    <RouteErrorBoundary routeId="admin-usage" routeLabel="Usage Analytics">
      <OptionLayout>
        <UsageAnalyticsPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminUsage
