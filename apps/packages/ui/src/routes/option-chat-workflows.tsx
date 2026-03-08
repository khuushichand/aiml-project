import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import OptionLayout from "@/components/Layouts/Layout"
import { ChatWorkflowsPage } from "@/components/Option/ChatWorkflows"

export default function OptionChatWorkflows() {
  return (
    <RouteErrorBoundary routeId="chat-workflows" routeLabel="Chat Workflows">
      <OptionLayout>
        <ChatWorkflowsPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
