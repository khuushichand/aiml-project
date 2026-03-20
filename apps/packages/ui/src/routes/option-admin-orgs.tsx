import OptionLayout from "~/components/Layouts/Layout"
import OrgsTeamsPage from "@/components/Option/Admin/OrgsTeamsPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminOrgs = () => {
  return (
    <RouteErrorBoundary routeId="admin-orgs" routeLabel="Organizations & Teams">
      <OptionLayout>
        <OrgsTeamsPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminOrgs
