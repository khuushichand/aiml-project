import { Spin } from "antd"
import { FileIcon, Loader2, XIcon } from "lucide-react"
import { useTranslation } from "react-i18next"

type Props = {
  name: string
  onRemove: () => void
  loading?: boolean
}

export const DocumentCard: React.FC<Props> = ({ name, onRemove, loading }) => {
  const { t } = useTranslation("common")

  return (
    <div
      className="relative group p-1.5 w-60 flex items-center gap-1 bg-surface border border-border rounded-2xl text-left"
      role="button"
      tabIndex={loading ? -1 : 0}
      aria-disabled={loading}
      aria-label={name}
      onKeyDown={(event) => {
        if (loading) return
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          event.currentTarget.click()
        }
      }}>
      <div className="p-3 bg-surface2 text-text rounded-xl">
        {loading ? <Spin size="small" /> : <FileIcon className="w-6 h-6" />}
      </div>
      <div className="flex flex-col justify-center -space-y-0.5 px-2.5 w-full">
        <div className="text-text text-sm font-medium line-clamp-1 mb-1">
          {name}
        </div>
      </div>
      <div className="absolute -top-1 -right-1">
        <button
          onClick={onRemove}
          aria-label={t("documentCard.removeAria", {
            defaultValue: "Remove {{name}}",
            name
          })}
          className="bg-surface text-text-muted border border-border rounded-full group-hover:visible group-focus-within:visible focus:visible focus-visible:visible invisible transition hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          type="button">
          <XIcon className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}
