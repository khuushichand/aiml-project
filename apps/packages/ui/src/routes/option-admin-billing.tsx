import OptionLayout from "~/components/Layouts/Layout"
import BillingDashboardPage from "@/components/Option/Admin/BillingDashboardPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminBilling = () => {
  return (
    <RouteErrorBoundary routeId="admin-billing" routeLabel="Billing">
      <OptionLayout>
        <BillingDashboardPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminBilling
