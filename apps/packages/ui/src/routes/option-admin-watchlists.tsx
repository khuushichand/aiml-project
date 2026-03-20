import OptionLayout from "~/components/Layouts/Layout"
import WatchlistsPage from "@/components/Option/Admin/WatchlistsPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionAdminWatchlists = () => {
  return (
    <RouteErrorBoundary routeId="admin-watchlists" routeLabel="Watchlists">
      <OptionLayout>
        <WatchlistsPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminWatchlists
