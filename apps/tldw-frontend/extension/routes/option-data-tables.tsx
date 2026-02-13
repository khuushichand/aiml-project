import { DataTablesPage } from "@/components/Option/DataTables"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

export default function OptionDataTables() {
  return (
    <RouteErrorBoundary routeId="data-tables" routeLabel="Data Tables">
      <DataTablesPage />
    </RouteErrorBoundary>
  )
}
