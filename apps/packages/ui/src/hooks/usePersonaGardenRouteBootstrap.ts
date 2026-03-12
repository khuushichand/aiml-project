import React from "react"

import {
  readPersonaGardenSearch,
  type PersonaGardenTabKey
} from "@/utils/persona-garden-route"

type UsePersonaGardenRouteBootstrapArgs = {
  search: string
  setActiveTab: React.Dispatch<React.SetStateAction<PersonaGardenTabKey>>
  setSelectedPersonaId: React.Dispatch<React.SetStateAction<string>>
}

export const usePersonaGardenRouteBootstrap = ({
  search,
  setActiveTab,
  setSelectedPersonaId
}: UsePersonaGardenRouteBootstrapArgs) => {
  const routeBootstrap = React.useMemo(
    () => readPersonaGardenSearch(search),
    [search]
  )

  React.useEffect(() => {
    if (routeBootstrap.tab) {
      setActiveTab(routeBootstrap.tab)
    }
  }, [routeBootstrap.tab, setActiveTab])

  React.useEffect(() => {
    if (routeBootstrap.personaId) {
      setSelectedPersonaId(routeBootstrap.personaId)
    }
  }, [routeBootstrap.personaId, setSelectedPersonaId])

  return routeBootstrap
}
