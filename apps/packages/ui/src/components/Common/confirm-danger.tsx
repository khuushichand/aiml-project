import React, { useState } from "react"
import { ExclamationCircleFilled } from "@ant-design/icons"
import { Input } from "antd"
import { useAntdModal } from "@/hooks/useAntdModal"

export type ConfirmDangerOptions = {
  title?: string
  content: React.ReactNode
  okText?: string
  cancelText?: string
  /** Defaults to true for destructive actions */
  danger?: boolean
  /** Which button receives autofocus */
  autoFocusButton?: "ok" | "cancel"
  /** Optional exact text the user must type before confirm is enabled */
  requireExactText?: string
  /** Optional helper label shown above the confirm input */
  requireExactTextLabel?: React.ReactNode
  /** Optional placeholder for the confirm input */
  requireExactTextPlaceholder?: string
}

function ConfirmDangerContent({
  content,
  requireExactText,
  requireExactTextLabel,
  requireExactTextPlaceholder,
  onConfirmTextChange
}: {
  content: React.ReactNode
  requireExactText?: string
  requireExactTextLabel?: React.ReactNode
  requireExactTextPlaceholder?: string
  onConfirmTextChange: (value: string) => void
}) {
  const [confirmValue, setConfirmValue] = useState("")

  if (!requireExactText) {
    return <>{content}</>
  }

  return (
    <div className="space-y-3">
      <div>{content}</div>
      <div className="space-y-1">
        <p className="text-sm text-text-muted">
          {requireExactTextLabel ?? `Type ${requireExactText} to confirm:`}
        </p>
        <Input
          value={confirmValue}
          placeholder={requireExactTextPlaceholder ?? requireExactText}
          autoFocus
          onChange={(event) => {
            const nextValue = event.target.value
            setConfirmValue(nextValue)
            onConfirmTextChange(nextValue)
          }}
        />
      </div>
    </div>
  )
}

/**
 * Show a consistent, accessible confirm dialog for destructive actions.
 * Returns a function that resolves to true if user confirmed, false otherwise.
 */
export function useConfirmDanger() {
  const modal = useAntdModal()

  return (options: ConfirmDangerOptions): Promise<boolean> => {
    const {
      title = "Please confirm",
      content,
      okText = "OK",
      cancelText = "Cancel",
      danger = true,
      autoFocusButton = "cancel",
      requireExactText,
      requireExactTextLabel,
      requireExactTextPlaceholder
    } = options

    return new Promise((resolve) => {
      let settled = false
      let confirmValue = ""
      let instance: ReturnType<typeof modal.confirm> | null = null

      const updateConfirmState = (value: string) => {
        confirmValue = value
        instance?.update({
          okButtonProps: {
            danger,
            disabled: value !== requireExactText
          }
        })
      }

      instance = modal.confirm({
        title,
        icon: <ExclamationCircleFilled />,
        content: (
          <ConfirmDangerContent
            content={content}
            requireExactText={requireExactText}
            requireExactTextLabel={requireExactTextLabel}
            requireExactTextPlaceholder={requireExactTextPlaceholder}
            onConfirmTextChange={updateConfirmState}
          />
        ),
        centered: true,
        okText,
        cancelText,
        okButtonProps: {
          danger,
          disabled: Boolean(requireExactText)
        },
        maskClosable: false,
        keyboard: true,
        autoFocusButton,
        onOk: () => {
          if (requireExactText && confirmValue !== requireExactText) {
            return Promise.reject(new Error("Confirmation text does not match"))
          }
          if (!settled) {
            settled = true
            resolve(true)
          }
        },
        onCancel: () => {
          if (!settled) {
            settled = true
            resolve(false)
          }
        }
      })

      void instance
    })
  }
}
