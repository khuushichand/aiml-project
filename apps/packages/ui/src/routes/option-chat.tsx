import { Playground } from "~/components/Option/Playground/Playground"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionChat = () => {
  return (
    <RouteErrorBoundary routeId="chat" routeLabel="Chat">
      <Playground />
    </RouteErrorBoundary>
  )
}

export default OptionChat
