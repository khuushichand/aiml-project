import React from "react"
import { Button, Input, Modal } from "antd"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RawRequestSnapshot = {
  endpoint: string
  method: string
  mode: string
  sentAt: string | number
  body: unknown
}

export interface PlaygroundRawRequestModalProps {
  open: boolean
  onClose: () => void
  snapshot: RawRequestSnapshot | null
  json: string
  onRefresh: () => void
  onCopy: () => void
  extraFooter?: React.ReactNode
  beforeJson?: React.ReactNode
  t: (key: string, defaultValue?: string, options?: any) => any
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const PlaygroundRawRequestModal: React.FC<PlaygroundRawRequestModalProps> =
  React.memo(function PlaygroundRawRequestModal(props) {
    const {
      open,
      onClose,
      snapshot,
      json,
      onRefresh,
      onCopy,
      extraFooter,
      beforeJson,
      t
    } = props

    return (
      <Modal
        open={open}
        onCancel={onClose}
        title={t(
          "playground:tools.rawChatRequestTitle",
          "Current chat request JSON"
        )}
        width={780}
        destroyOnHidden
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button onClick={onRefresh}>
              {t("common:refresh", "Refresh")}
            </Button>
            {extraFooter}
            <Button onClick={onCopy} disabled={!json}>
              {t("common:copy", "Copy")}
            </Button>
            <Button type="primary" onClick={onClose}>
              {t("common:close", "Close")}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          {snapshot ? (
            <>
              {beforeJson}
              <div className="space-y-1 text-xs text-text-muted">
                <p>
                  {t("playground:tools.rawChatRequestEndpoint", "Endpoint")}:{" "}
                  <span className="font-mono">{snapshot.endpoint}</span>
                </p>
                <p>
                  {t("playground:tools.rawChatRequestMethod", "Method")}:{" "}
                  {snapshot.method}
                </p>
                <p>
                  {t("playground:tools.rawChatRequestMode", "Mode")}:{" "}
                  {snapshot.mode}
                </p>
                <p>
                  {t("playground:tools.rawChatRequestSentAt", "Sent at")}:{" "}
                  {new Date(snapshot.sentAt).toLocaleString()}
                </p>
                <p>
                  {t(
                    "playground:tools.rawChatRequestMessageCount",
                    "Messages"
                  )}
                  :{" "}
                  {Array.isArray((snapshot.body as any)?.messages)
                    ? (snapshot.body as any).messages.length
                    : t(
                        "playground:tools.rawChatRequestMessageCountNa",
                        "n/a"
                      )}
                </p>
              </div>
              <Input.TextArea
                data-testid="raw-chat-request-json"
                readOnly
                value={json}
                autoSize={{ minRows: 14, maxRows: 30 }}
                className="font-mono text-xs"
              />
            </>
          ) : (
            <p className="text-sm text-text-muted">
              {t(
                "playground:tools.rawChatRequestEmpty",
                "Unable to generate a request preview for the current composer state."
              )}
            </p>
          )}
        </div>
      </Modal>
    )
  })
