import OptionLayout from "@web/components/layout/WebLayout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import { ScheduledTasksPage } from "@/components/Option/ScheduledTasks/ScheduledTasksPage"

const OptionScheduledTasks = () => {
  return (
    <RouteErrorBoundary routeId="scheduled-tasks" routeLabel="Scheduled Tasks">
      <OptionLayout>
        <ScheduledTasksPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionScheduledTasks
