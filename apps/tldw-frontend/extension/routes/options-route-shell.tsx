import React from "react"
import { ExtensionRouteShell } from "./app-route"
import { optionRoutes } from "./route-registry"

export const OptionsRouteShell = () => (
  <ExtensionRouteShell kind="options" routes={optionRoutes} />
)

export default OptionsRouteShell
