import { lazy } from "react"

import type { RouteDefinition } from "./route-registry"

import OptionMedia from "./option-media"

const OptionMediaTrash = lazy(() => import("./option-media-trash"))

export const optionMediaViewRoutes: RouteDefinition[] = [
  {
    kind: "options",
    path: "/media",
    element: <OptionMedia />,
  },
  {
    kind: "options",
    path: "/media-trash",
    element: <OptionMediaTrash />,
  }
]
