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
    <div className="grid min-w-0 gap-4 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
      <div className="min-w-0">
        <SlideRail />
      </div>
      <div className="min-w-0">
        <SlideEditorPane />
      </div>
      <div className="min-w-0">
        <MediaRail canRender={canRender} />
      </div>
    </div>
  )
}
