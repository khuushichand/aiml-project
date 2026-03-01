import { UserCircle2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useEffect, useMemo, useState } from "react"
import { createImageDataUrl } from "@/utils/image-utils"

interface CharacterPreviewProps {
  name?: string
  description?: string
  avatar_url?: string
  image_base64?: string
  system_prompt?: string
  greeting?: string
  tags?: string[]
  expandedMetadata?: boolean
  onAvatarClick?: (src: string) => void
  avatarClickAriaLabel?: string
  avatarTriggerTestId?: string
}


export function CharacterPreview({
  name,
  description,
  avatar_url,
  image_base64,
  system_prompt,
  greeting,
  tags,
  expandedMetadata = false,
  onAvatarClick,
  avatarClickAriaLabel,
  avatarTriggerTestId
}: CharacterPreviewProps) {
  const { t } = useTranslation(["settings", "common"])
  const [avatarImgError, setAvatarImgError] = useState(false)

  const avatarSrc = useMemo(() => {
    if (avatar_url) return avatar_url
    if (image_base64) return createImageDataUrl(image_base64)
    return null
  }, [avatar_url, image_base64])

  useEffect(() => {
    setAvatarImgError(false)
  }, [avatarSrc])

  const displayName = name || t("settings:manageCharacters.preview.untitled", {
    defaultValue: "Untitled character"
  })
  const canOpenAvatar = Boolean(avatarSrc && !avatarImgError && onAvatarClick)

  return (
    <div className="rounded-lg border border-border bg-surface2 p-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wide text-text-subtle">
        {t("settings:manageCharacters.preview.title", {
          defaultValue: "Preview"
        })}
      </div>

      {/* Character Card */}
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="flex-shrink-0">
          {canOpenAvatar ? (
            <button
              type="button"
              className="rounded-full focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-surface2"
              aria-label={
                avatarClickAriaLabel ||
                t("settings:manageCharacters.preview.openFullImage", {
                  defaultValue: "Open full size image for {{name}}",
                  name: displayName
                })
              }
              data-testid={avatarTriggerTestId}
              onClick={() => onAvatarClick?.(avatarSrc as string)}
            >
              <img
                src={avatarSrc as string}
                alt={displayName}
                className="h-12 w-12 rounded-full object-cover ring-2 ring-border cursor-zoom-in"
                onError={() => {
                  setAvatarImgError(true)
                }}
              />
            </button>
          ) : avatarSrc && !avatarImgError ? (
            <img
              src={avatarSrc}
              alt={displayName}
              className="h-12 w-12 rounded-full object-cover ring-2 ring-border"
              onError={() => {
                setAvatarImgError(true)
              }}
            />
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface2 ring-2 ring-border">
              <UserCircle2 className="h-8 w-8 text-text-subtle" />
            </div>
          )}
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1 space-y-1">
          <div className="font-semibold text-text truncate">
            {displayName}
          </div>
          {description && (
            <div
              className={`text-sm ${
                expandedMetadata
                  ? "text-text whitespace-pre-wrap break-words"
                  : "text-text-muted line-clamp-2"
              }`}
            >
              {description}
            </div>
          )}
          {tags && tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {(expandedMetadata ? tags : tags.slice(0, 4)).map((tag, i) => (
                <span
                  key={`${tag}-${i}`}
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${
                    expandedMetadata
                      ? "border border-border bg-surface text-text"
                      : "bg-surface2 text-text-muted"
                  }`}>
                  {tag}
                </span>
              ))}
              {!expandedMetadata && tags.length > 4 && (
                <span className="text-xs text-text-subtle">
                  +{tags.length - 4}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Greeting Preview */}
      {greeting && (
        <div className="mt-4 rounded-md bg-surface p-3 shadow-sm">
          <div className="mb-1 text-xs font-medium text-text-subtle">
            {t("settings:manageCharacters.preview.greeting", {
              defaultValue: "Greeting"
            })}
          </div>
          <div className="text-sm text-text-muted line-clamp-3 italic">
            "{greeting}"
          </div>
        </div>
      )}

      {/* System Prompt Preview */}
      {system_prompt && (
        <div className="mt-3 rounded-md bg-surface p-3 shadow-sm">
          <div className="mb-1 text-xs font-medium text-text-subtle">
            {t("settings:manageCharacters.preview.behavior", {
              defaultValue: "Behavior"
            })}
          </div>
          <div className="text-sm text-text-muted line-clamp-3">
            {system_prompt}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!name && !description && !system_prompt && !greeting && (
        <div className="mt-3 text-center text-sm text-text-subtle">
          {t("settings:manageCharacters.preview.empty", {
            defaultValue: "Fill in the form to see a preview"
          })}
        </div>
      )}
    </div>
  )
}
