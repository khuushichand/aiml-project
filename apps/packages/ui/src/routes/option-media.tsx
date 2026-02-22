import OptionLayout from "~/components/Layouts/Layout"
import ViewMediaPage from "@/components/Review/ViewMediaPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionMedia = () => {
  return (
    <OptionLayout>
      <RouteErrorBoundary routeId="media" routeLabel="Media">
        <ViewMediaPage />
      </RouteErrorBoundary>
    </OptionLayout>
  )
}

export default OptionMedia
