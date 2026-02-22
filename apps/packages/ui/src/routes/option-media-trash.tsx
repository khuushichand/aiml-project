import OptionLayout from "@/components/Layouts/Layout"
import MediaTrashPage from "@/components/Review/MediaTrashPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionMediaTrash = () => {
  return (
    <OptionLayout>
      <RouteErrorBoundary routeId="media-trash" routeLabel="Media Trash">
        <MediaTrashPage />
      </RouteErrorBoundary>
    </OptionLayout>
  )
}

export default OptionMediaTrash
