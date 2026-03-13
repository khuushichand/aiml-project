import React from "react"

import { MediaRail } from "./MediaRail"
import { SlideEditorPane } from "./SlideEditorPane"
import { SlideRail } from "./SlideRail"
import { usePresentationStudioAutosave } from "@/hooks/usePresentationStudioAutosave"

type ProjectWorkspaceProps = {
  canRender: boolean
}

export const ProjectWorkspace: React.FC<ProjectWorkspaceProps> = ({ canRender }) => {
  usePresentationStudioAutosave()

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_280px]">
      <SlideRail />
      <SlideEditorPane />
      <MediaRail canRender={canRender} />
    </div>
  )
}
