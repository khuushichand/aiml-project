import React from "react"
import { Drawer, Modal } from "antd"

type DictionaryEntryEditPanelProps = {
  open: boolean
  isMobileViewport: boolean
  onClose: () => void
  children: React.ReactNode
}

export const DictionaryEntryEditPanel: React.FC<DictionaryEntryEditPanelProps> = ({
  open,
  isMobileViewport,
  onClose,
  children,
}) => {
  if (isMobileViewport) {
    return (
      <Drawer
        title="Edit Entry"
        open={open}
        onClose={onClose}
        placement="right"
        destroyOnClose
        size="100vw">
        {children}
      </Drawer>
    )
  }

  return (
    <Modal
      title="Edit Entry"
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnHidden>
      {children}
    </Modal>
  )
}
