import OptionLayout from "~/components/Layouts/Layout"
import RateLimitingPage from "@/components/Option/Admin/RateLimitingPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminRateLimiting = () => {
  return (
    <RouteErrorBoundary routeId="admin-rate-limiting" routeLabel="Rate Limiting">
      <OptionLayout>
        <RateLimitingPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminRateLimiting
