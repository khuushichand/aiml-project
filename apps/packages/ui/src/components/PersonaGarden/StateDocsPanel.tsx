import React from "react"

type StateDocsPanelProps = {
  children: React.ReactNode
}

export const StateDocsPanel: React.FC<StateDocsPanelProps> = ({ children }) => {
  return <div className="flex flex-1 flex-col gap-3">{children}</div>
}
