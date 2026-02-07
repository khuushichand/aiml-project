import React from "react"
import { Modal, Select, Empty, Skeleton, Space, Button } from "antd"
import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { FolderOpen } from "lucide-react"
import { getAvailableProjects } from "@/services/prompt-sync"
import { useServerOnline } from "@/hooks/useServerOnline"

interface ProjectSelectorProps {
  open: boolean
  onClose: () => void
  onSelect: (projectId: number) => void
  title?: string
  loading?: boolean
}

export const ProjectSelector: React.FC<ProjectSelectorProps> = ({
  open,
  onClose,
  onSelect,
  title,
  loading = false
}) => {
  const { t } = useTranslation(["settings", "common"])
  const isOnline = useServerOnline()
  const [selectedProjectId, setSelectedProjectId] = React.useState<number | null>(null)

  const { data: projects, isLoading } = useQuery({
    queryKey: ["prompt-studio", "projects-for-sync"],
    queryFn: getAvailableProjects,
    enabled: open && isOnline
  })

  const handleConfirm = () => {
    if (selectedProjectId) {
      onSelect(selectedProjectId)
      setSelectedProjectId(null)
    }
  }

  const handleCancel = () => {
    setSelectedProjectId(null)
    onClose()
  }

  return (
    <Modal
      title={title || t("settings:managePrompts.sync.selectProject", "Select Project")}
      open={open}
      onCancel={handleCancel}
      footer={null}
      destroyOnHidden
    >
      {!isOnline ? (
        <Empty
          description={t("settings:managePrompts.sync.offlineMessage", "Server connection required")}
        />
      ) : isLoading ? (
        <Skeleton active paragraph={{ rows: 3 }} />
      ) : !projects || projects.length === 0 ? (
        <Empty
          description={t("settings:managePrompts.sync.noProjects", "No projects available. Create a project in Prompt Studio first.")}
        />
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            {t("settings:managePrompts.sync.selectProjectDescription",
              "Choose a Prompt Studio project to sync this prompt to."
            )}
          </p>
          <Select
            placeholder={t("settings:managePrompts.sync.selectProjectPlaceholder", "Select a project...")}
            value={selectedProjectId}
            onChange={setSelectedProjectId}
            style={{ width: "100%" }}
            options={projects.map(p => ({
              label: (
                <span className="flex items-center gap-2">
                  <FolderOpen className="size-4 text-text-muted" />
                  <span>{p.name}</span>
                  {p.description && (
                    <span className="text-text-muted text-xs">— {p.description}</span>
                  )}
                </span>
              ),
              value: p.id
            }))}
          />
          <Space className="w-full justify-end">
            <Button onClick={handleCancel}>
              {t("common:cancel", "Cancel")}
            </Button>
            <Button
              type="primary"
              onClick={handleConfirm}
              disabled={!selectedProjectId}
              loading={loading}
            >
              {t("settings:managePrompts.sync.pushToProject", "Push to Project")}
            </Button>
          </Space>
        </div>
      )}
    </Modal>
  )
}

export default ProjectSelector
