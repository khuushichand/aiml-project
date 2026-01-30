import React, { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Form, Input, Select, Space } from "antd"
import { Globe, Terminal } from "lucide-react"
import { Button } from "@/components/Common/Button"
import type { ACPMCPServerConfig, ACPMCPServerType } from "@/services/acp/types"
import { MCP_SERVER_PRESETS } from "@/services/acp/constants"

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface MCPServerConfigFormProps {
  server?: ACPMCPServerConfig
  onSave: (server: ACPMCPServerConfig) => void
  onCancel: () => void
}

interface FormValues {
  name: string
  type: ACPMCPServerType
  url?: string
  command?: string
  args?: string
}

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------

export const MCPServerConfigForm: React.FC<MCPServerConfigFormProps> = ({
  server,
  onSave,
  onCancel,
}) => {
  const { t } = useTranslation(["playground", "common"])
  const [form] = Form.useForm<FormValues>()
  const serverType = Form.useWatch("type", form)

  const isEditing = !!server

  // Set initial values
  useEffect(() => {
    if (server) {
      form.setFieldsValue({
        name: server.name,
        type: server.type,
        url: server.url,
        command: server.command,
        args: server.args?.join(" "),
      })
    } else {
      form.resetFields()
    }
  }, [server, form])

  const handlePresetSelect = (presetName: string) => {
    const preset = MCP_SERVER_PRESETS.find((p) => p.name === presetName)
    if (preset) {
      form.setFieldsValue({
        name: preset.name,
        type: preset.type,
        url: preset.url,
        command: preset.command,
        args: preset.args?.join(" "),
      })
    }
  }

  const handleSubmit = (values: FormValues) => {
    const config: ACPMCPServerConfig = {
      name: values.name.trim(),
      type: values.type,
    }

    if (values.type === "websocket") {
      config.url = values.url?.trim()
    } else {
      config.command = values.command?.trim()
      if (values.args?.trim()) {
        config.args = values.args.trim().split(/\s+/)
      }
    }

    onSave(config)
  }

  return (
    <div className="rounded-lg border border-border bg-surface2/30 p-4">
      <h4 className="mb-4 text-sm font-medium text-text">
        {isEditing
          ? t("acp.mcp.editServer", "Edit MCP Server")
          : t("acp.mcp.addServer", "Add MCP Server")}
      </h4>

      {/* Presets - only show when adding new */}
      {!isEditing && (
        <div className="mb-4">
          <label className="mb-2 block text-xs text-text-muted">
            {t("acp.mcp.presets", "Quick Presets")}
          </label>
          <Space wrap>
            {MCP_SERVER_PRESETS.map((preset) => (
              <Button
                key={preset.name}
                type="secondary"
                size="small"
                onClick={() => handlePresetSelect(preset.name)}
              >
                {preset.type === "websocket" ? (
                  <Globe className="mr-1 h-3 w-3" />
                ) : (
                  <Terminal className="mr-1 h-3 w-3" />
                )}
                {preset.name}
              </Button>
            ))}
          </Space>
        </div>
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          type: "websocket",
        }}
      >
        {/* Name */}
        <Form.Item
          name="name"
          label={t("acp.mcp.form.name", "Server Name")}
          rules={[
            {
              required: true,
              message: t("acp.mcp.form.nameRequired", "Please enter a server name"),
            },
          ]}
        >
          <Input placeholder="my-mcp-server" />
        </Form.Item>

        {/* Type */}
        <Form.Item
          name="type"
          label={t("acp.mcp.form.type", "Connection Type")}
          rules={[{ required: true }]}
        >
          <Select
            options={[
              {
                value: "websocket",
                label: (
                  <span className="flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    {t("acp.mcp.form.typeWebsocket", "WebSocket")}
                  </span>
                ),
              },
              {
                value: "stdio",
                label: (
                  <span className="flex items-center gap-2">
                    <Terminal className="h-4 w-4" />
                    {t("acp.mcp.form.typeStdio", "Stdio (Local Process)")}
                  </span>
                ),
              },
            ]}
          />
        </Form.Item>

        {/* WebSocket URL */}
        {serverType === "websocket" && (
          <Form.Item
            name="url"
            label={t("acp.mcp.form.url", "WebSocket URL")}
            rules={[
              {
                required: true,
                message: t("acp.mcp.form.urlRequired", "Please enter the WebSocket URL"),
              },
              {
                pattern: /^wss?:\/\//,
                message: t(
                  "acp.mcp.form.urlInvalid",
                  "URL must start with ws:// or wss://"
                ),
              },
            ]}
          >
            <Input placeholder="ws://localhost:8080/mcp" />
          </Form.Item>
        )}

        {/* Stdio Command */}
        {serverType === "stdio" && (
          <>
            <Form.Item
              name="command"
              label={t("acp.mcp.form.command", "Command")}
              rules={[
                {
                  required: true,
                  message: t(
                    "acp.mcp.form.commandRequired",
                    "Please enter the command to run"
                  ),
                },
              ]}
            >
              <Input placeholder="npx" />
            </Form.Item>

            <Form.Item
              name="args"
              label={t("acp.mcp.form.args", "Arguments")}
              extra={t("acp.mcp.form.argsHelp", "Space-separated command arguments")}
            >
              <Input placeholder="-y @modelcontextprotocol/server-filesystem /path" />
            </Form.Item>
          </>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <Button type="secondary" onClick={onCancel}>
            {t("common:cancel", "Cancel")}
          </Button>
          <Button type="primary" htmlType="submit">
            {isEditing
              ? t("common:save", "Save")
              : t("acp.mcp.form.add", "Add Server")}
          </Button>
        </div>
      </Form>
    </div>
  )
}

export default MCPServerConfigForm
