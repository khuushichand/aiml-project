import type { RouteDefinition } from "./route-registry"

import OptionHomeResolver from "./option-home-resolver"

export const optionStartupRoutes: RouteDefinition[] = [
  { kind: "options", path: "/", element: <OptionHomeResolver /> }
]
