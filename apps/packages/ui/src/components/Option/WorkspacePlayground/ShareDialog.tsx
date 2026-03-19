import React from "react"
import { Button, Modal } from "antd"
import { useTranslation } from "react-i18next"

type ShareDialogProps = {
  workspaceId: string
  open: boolean
  onClose: () => void
}

export function ShareDialog({ workspaceId, open, onClose }: ShareDialogProps) {
  const { t } = useTranslation()

  return (
    <Modal
      open={open}
      title={t("playground:workspace.shareDialogTitle", "Share workspace")}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          {t("common.close", "Close")}
        </Button>,
      ]}
      destroyOnHidden
    >
      <div className="space-y-3 text-sm text-muted-foreground">
        <p>
          {t(
            "playground:workspace.shareDialogUnavailable",
            "Workspace sharing is not available in this build yet."
          )}
        </p>
        <p>
          {t(
            "playground:workspace.shareDialogWorkspaceId",
            "Workspace ID: {{workspaceId}}",
            { workspaceId }
          )}
        </p>
      </div>
    </Modal>
  )
}

export default ShareDialog
