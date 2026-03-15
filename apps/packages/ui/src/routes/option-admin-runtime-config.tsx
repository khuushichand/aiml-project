import OptionLayout from "~/components/Layouts/Layout"
import RuntimeConfigPage from "@/components/Option/Admin/RuntimeConfigPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminRuntimeConfig = () => {
  return (
    <RouteErrorBoundary routeId="admin-runtime-config" routeLabel="Runtime Config">
      <OptionLayout>
        <RuntimeConfigPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminRuntimeConfig
