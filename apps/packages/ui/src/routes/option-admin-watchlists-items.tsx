import OptionLayout from "~/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { ItemsTab } from "@/components/Option/Watchlists/ItemsTab"

const OptionAdminWatchlistsItems = () => {
  return (
    <RouteErrorBoundary routeId="admin-watchlists-items" routeLabel="Watchlists Items">
      <OptionLayout>
        <div style={{ padding: "24px", maxWidth: "100%" }}>
          <h2 style={{ marginBottom: 16 }}>Watchlists Items</h2>
          <ItemsTab />
        </div>
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionAdminWatchlistsItems
