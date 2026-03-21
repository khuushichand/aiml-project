import OptionLayout from "@web/components/layout/WebLayout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { IntegrationManagementPage } from "@/components/Option/Integrations/IntegrationManagementPage"

const OptionAdminIntegrations = () => {
  return (
    <RouteErrorBoundary routeId="admin-integrations" routeLabel="Integrations">
      <OptionLayout>
        <IntegrationManagementPage scope="workspace" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminIntegrations
