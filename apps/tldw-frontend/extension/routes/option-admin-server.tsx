import OptionLayout from "@web/components/layout/WebLayout"
import ServerAdminPage from "@/components/Option/Admin/ServerAdminPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminServer = () => {
  return (
    <RouteErrorBoundary routeId="admin-server" routeLabel="Server Admin">
      <OptionLayout>
        <ServerAdminPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminServer
