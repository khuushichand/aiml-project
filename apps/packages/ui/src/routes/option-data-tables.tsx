import { DataTablesPage } from "@/components/Option/DataTables"
import OptionLayout from "@/components/Layouts/Layout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

export default function OptionDataTables() {
  return (
    <RouteErrorBoundary routeId="data-tables" routeLabel="Data Tables">
      <OptionLayout>
        <DataTablesPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
