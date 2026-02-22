import OptionLayout from "~/components/Layouts/Layout"
import NotesManagerPage from "@/components/Notes/NotesManagerPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionNotes = () => {
  return (
    <OptionLayout>
      <RouteErrorBoundary routeId="notes" routeLabel="Notes">
        <NotesManagerPage />
      </RouteErrorBoundary>
    </OptionLayout>
  )
}

export default OptionNotes
