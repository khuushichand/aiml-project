import React from "react"

import { Badge } from "@/components/ui/primitives/Badge"
import { cn } from "@/libs/utils"
import type { PresentationStudioAssetStatus } from "@/store/presentation-studio"

type PresentationStudioStatusBadgeProps = {
  status: PresentationStudioAssetStatus | null | undefined
  className?: string
}

const STATUS_VARIANTS: Record<
  PresentationStudioAssetStatus,
  React.ComponentProps<typeof Badge>["variant"]
> = {
  missing: "secondary",
  ready: "success",
  stale: "warning",
  generating: "info",
  failed: "danger"
}

export const PresentationStudioStatusBadge: React.FC<
  PresentationStudioStatusBadgeProps
> = ({ status, className }) => {
  const normalized = status || "missing"

  return (
    <Badge
      className={cn("capitalize", className)}
      dot
      size="sm"
      variant={STATUS_VARIANTS[normalized]}
    >
      {normalized}
    </Badge>
  )
}
