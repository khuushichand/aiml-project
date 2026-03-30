import React from "react"
import { RouteShell } from "./app-route"
import { sidepanelRoutes } from "./sidepanel-route-registry"

export const SidepanelRouteShell = () => (
  <RouteShell kind="sidepanel" routes={sidepanelRoutes} />
)

export default SidepanelRouteShell
