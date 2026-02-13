import OptionLayout from "@web/components/layout/WebLayout"
import MlxAdminPage from "@/components/Option/Admin/MlxAdminPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminMlx = () => {
  return (
    <RouteErrorBoundary routeId="admin-mlx" routeLabel="MLX Admin">
      <OptionLayout>
        <MlxAdminPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminMlx
