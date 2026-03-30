import React from "react"
import { ExtensionRouteShell } from "./app-route"
import { sidepanelRoutes } from "./sidepanel-route-registry"

export const SidepanelRouteShell = () => (
  <ExtensionRouteShell kind="sidepanel" routes={sidepanelRoutes} />
)

export default SidepanelRouteShell
