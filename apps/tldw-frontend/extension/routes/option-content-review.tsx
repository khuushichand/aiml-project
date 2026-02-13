import OptionLayout from "@web/components/layout/WebLayout"
import ContentReviewPage from "@/components/ContentReview/ContentReviewPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionContentReview = () => {
  return (
    <RouteErrorBoundary routeId="content-review" routeLabel="Content Review">
      <OptionLayout>
        <ContentReviewPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionContentReview
