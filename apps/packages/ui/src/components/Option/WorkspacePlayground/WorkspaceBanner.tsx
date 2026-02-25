import React from "react"
import type { WorkspaceBanner as WorkspaceBannerModel } from "@/types/workspace"

type WorkspaceBannerProps = {
  banner: WorkspaceBannerModel
  workspaceName: string
  isMobile: boolean
}

const hasBannerContent = (banner: WorkspaceBannerModel): boolean =>
  banner.title.trim().length > 0 ||
  banner.subtitle.trim().length > 0 ||
  Boolean(banner.image?.dataUrl)

export const WorkspaceBanner: React.FC<WorkspaceBannerProps> = ({
  banner,
  workspaceName,
  isMobile
}) => {
  if (!hasBannerContent(banner)) {
    return null
  }

  const title = banner.title.trim() || workspaceName || "Research Workspace"
  const subtitle = banner.subtitle.trim()
  const backgroundImage = banner.image?.dataUrl
    ? `linear-gradient(120deg, rgba(8, 12, 18, 0.72) 0%, rgba(8, 12, 18, 0.24) 100%), url(${banner.image.dataUrl})`
    : "linear-gradient(125deg, color-mix(in oklab, var(--primary) 24%, transparent) 0%, color-mix(in oklab, var(--surface-2) 76%, transparent) 100%)"

  return (
    <section
      data-testid="workspace-banner"
      className={`mx-2 mt-2 overflow-hidden rounded-2xl border border-border/70 shadow-card ${
        isMobile ? "min-h-[108px]" : "min-h-[132px]"
      }`}
      style={{
        backgroundImage,
        backgroundPosition: "center",
        backgroundSize: "cover"
      }}
    >
      <div
        className={`flex h-full flex-col justify-end px-4 py-3 ${
          isMobile ? "gap-1.5" : "gap-2"
        }`}
      >
        <h2
          data-testid="workspace-banner-title"
          className={`line-clamp-2 font-semibold text-white ${
            isMobile ? "text-lg" : "text-xl"
          }`}
        >
          {title}
        </h2>
        {subtitle.length > 0 && (
          <p
            data-testid="workspace-banner-subtitle"
            className="line-clamp-2 max-w-3xl text-sm text-white/90"
          >
            {subtitle}
          </p>
        )}
      </div>
    </section>
  )
}
