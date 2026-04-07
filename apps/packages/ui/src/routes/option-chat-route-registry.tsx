import type { RouteDefinition } from "./route-registry"

import OptionChat from "./option-chat"

export const optionChatRoutes: RouteDefinition[] = [
  { kind: "options", path: "/chat", element: <OptionChat /> }
]
