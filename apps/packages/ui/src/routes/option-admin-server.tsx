import OptionLayout from "~/components/Layouts/Layout"
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
