import React from "react"

import { PageAssistLoader } from "@/components/Common/PageAssistLoader"

const LazyOptionIndex = React.lazy(() => import("./option-index"))

export default function OptionHomeResolver() {
  return (
    <React.Suspense
      fallback={
        <PageAssistLoader
          label="Loading home..."
          description="Preparing your workspace"
        />
      }
    >
      <LazyOptionIndex />
    </React.Suspense>
  )
}
