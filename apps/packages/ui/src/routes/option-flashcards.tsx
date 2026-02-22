import OptionLayout from "~/components/Layouts/Layout"
import { FlashcardsWorkspace } from "@/components/Flashcards/FlashcardsWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionFlashcards = () => {
  return (
    <RouteErrorBoundary routeId="flashcards" routeLabel="Flashcards">
      <OptionLayout>
        <FlashcardsWorkspace />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionFlashcards
