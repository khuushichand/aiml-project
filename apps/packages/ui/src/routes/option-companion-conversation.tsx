import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"
import OptionLayout from "@/components/Layouts/Layout"

import SidepanelPersona from "./sidepanel-persona"

export default function OptionCompanionConversation() {
  return (
    <RouteErrorBoundary
      routeId="companion-conversation"
      routeLabel="Companion conversation"
    >
      <OptionLayout>
        <SidepanelPersona mode="companion" shell="options" />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}
