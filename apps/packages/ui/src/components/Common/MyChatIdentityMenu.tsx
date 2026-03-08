import React from "react"

type MyChatIdentityMenuProps = {
  displayNameLabel: string
  imageLabel: string
  promptTemplatesLabel: string
  clearImageLabel?: string
  onDisplayName: () => void
  onImage: () => void
  onPromptTemplates: () => void
  onClearImage?: () => void
  className?: string
}

const stopMenuEvent = (
  event: React.MouseEvent<HTMLButtonElement>,
  action: () => void
) => {
  event.preventDefault()
  event.stopPropagation()
  action()
}

export const MyChatIdentityMenu: React.FC<MyChatIdentityMenuProps> = ({
  displayNameLabel,
  imageLabel,
  promptTemplatesLabel,
  clearImageLabel,
  onDisplayName,
  onImage,
  onPromptTemplates,
  onClearImage,
  className
}) => {
  return (
    <section
      aria-label="My Chat Identity"
      className={`px-3 py-2 ${className ?? ""}`.trim()}
    >
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        My Chat Identity
      </h3>
      <div className="mt-2 flex flex-col gap-1">
        <button
          type="button"
          className="w-full rounded-md px-2 py-1 text-left text-xs font-medium text-text hover:bg-surface2"
          onClick={(event) => stopMenuEvent(event, onDisplayName)}
        >
          {displayNameLabel}
        </button>
        <button
          type="button"
          className="w-full rounded-md px-2 py-1 text-left text-xs font-medium text-text hover:bg-surface2"
          onClick={(event) => stopMenuEvent(event, onImage)}
        >
          {imageLabel}
        </button>
        {clearImageLabel && onClearImage ? (
          <button
            type="button"
            className="w-full rounded-md px-2 py-1 text-left text-xs font-medium text-text hover:bg-surface2"
            onClick={(event) => stopMenuEvent(event, onClearImage)}
          >
            {clearImageLabel}
          </button>
        ) : null}
        <button
          type="button"
          className="w-full rounded-md px-2 py-1 text-left text-xs font-medium text-text hover:bg-surface2"
          onClick={(event) => stopMenuEvent(event, onPromptTemplates)}
        >
          {promptTemplatesLabel}
        </button>
      </div>
    </section>
  )
}
