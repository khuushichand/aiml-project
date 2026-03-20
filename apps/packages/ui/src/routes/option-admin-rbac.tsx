import OptionLayout from "~/components/Layouts/Layout"
import RbacEditorPage from "@/components/Option/Admin/RbacEditorPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminRbac = () => {
  return (
    <RouteErrorBoundary routeId="admin-rbac" routeLabel="RBAC / Permissions">
      <OptionLayout>
        <RbacEditorPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminRbac
