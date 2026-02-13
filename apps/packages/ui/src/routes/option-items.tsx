import OptionLayout from "~/components/Layouts/Layout"
import { ItemsWorkspace } from "@/components/Option/Items/ItemsWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionItems = () => {
  return (
    <RouteErrorBoundary routeId="items" routeLabel="Items">
      <OptionLayout>
        <ItemsWorkspace />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionItems
