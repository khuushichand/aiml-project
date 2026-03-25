import React from "react"
import { RouteShell } from "./app-route"
import { DeferredOptionsRoute } from "./deferred-options-route"
import { optionStartupRoutes } from "./option-startup-routes"

export const OptionsRouteShell = () => (
  <RouteShell
    kind="options"
    routes={optionStartupRoutes}
    renderUnmatchedRoute={(props) => <DeferredOptionsRoute {...props} />}
  />
)

export default OptionsRouteShell
