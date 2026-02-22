import OptionLayout from "@web/components/layout/WebLayout"
import { QuizWorkspace } from "@/components/Quiz/QuizWorkspace"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionQuiz = () => {
  return (
    <RouteErrorBoundary routeId="quiz" routeLabel="Quiz">
      <OptionLayout>
        <QuizWorkspace />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionQuiz
