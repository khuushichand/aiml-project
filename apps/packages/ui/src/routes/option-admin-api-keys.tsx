import OptionLayout from "~/components/Layouts/Layout"
import ApiKeyManagementPage from "@/components/Option/Admin/ApiKeyManagementPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminApiKeys = () => {
  return (
    <RouteErrorBoundary routeId="admin-api-keys" routeLabel="API Key Management">
      <OptionLayout>
        <ApiKeyManagementPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminApiKeys
