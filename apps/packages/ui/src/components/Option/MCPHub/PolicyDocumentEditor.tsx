import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Card, Checkbox, Empty, Space, Tag, Typography } from "antd"

import type {
  McpHubPermissionPolicyDocument,
  McpHubToolRegistryEntry,
  McpHubToolRegistryModule
} from "@/services/tldw/mcp-hub"

import {
  buildSimplePolicyDocument,
  createPresetSelection,
  getAdvancedPolicyKeys,
  getDerivedCapabilities,
  getKnownRegistryCapabilities,
  getPolicyAllowedToolSelection,
  getToolEntriesByModule,
  joinList,
  parseLineList
} from "./policyHelpers"

type EditorMode = "simple" | "advanced"

type PolicyDocumentEditorProps = {
  formId: string
  policy: McpHubPermissionPolicyDocument
  onChange: (next: McpHubPermissionPolicyDocument) => void
  registryEntries: McpHubToolRegistryEntry[]
  registryModules: McpHubToolRegistryModule[]
}

const PRESET_OPTIONS = [
  { key: "none", label: "No Additional Restrictions" },
  { key: "read_only", label: "Read Only" },
  { key: "write_manage", label: "Write And Manage" },
  { key: "process_execution", label: "Process Execution" },
  { key: "external_services", label: "External Services" }
] as const

export const PolicyDocumentEditor = ({
  formId,
  policy,
  onChange,
  registryEntries,
  registryModules
}: PolicyDocumentEditorProps) => {
  const [editorMode, setEditorMode] = useState<EditorMode>("simple")
  const [advancedText, setAdvancedText] = useState("{}")
  const [advancedError, setAdvancedError] = useState<string | null>(null)

  const modules = useMemo(
    () => getToolEntriesByModule(registryEntries, registryModules),
    [registryEntries, registryModules]
  )
  const knownCapabilities = useMemo(() => getKnownRegistryCapabilities(registryEntries), [registryEntries])
  const selection = useMemo(
    () => getPolicyAllowedToolSelection(policy.allowed_tools, registryEntries),
    [policy.allowed_tools, registryEntries]
  )
  const derivedCapabilities = useMemo(
    () => getDerivedCapabilities(selection.selectedTools, registryEntries, policy.capabilities),
    [policy.capabilities, registryEntries, selection.selectedTools]
  )
  const advancedKeys = useMemo(() => getAdvancedPolicyKeys(policy), [policy])
  const deniedToolsText = useMemo(() => joinList(policy.denied_tools), [policy.denied_tools])

  useEffect(() => {
    setAdvancedText(JSON.stringify(policy, null, 2))
    setAdvancedError(null)
  }, [policy])

  const applySimpleSelection = (selectedTools: string[], deniedToolsValue: string) => {
    onChange(
      buildSimplePolicyDocument({
        currentPolicy: policy,
        selectedTools,
        deniedTools: parseLineList(deniedToolsValue),
        registryEntries
      })
    )
  }

  const handlePreset = (presetId: (typeof PRESET_OPTIONS)[number]["key"]) => {
    const preset = createPresetSelection(presetId, registryEntries)
    applySimpleSelection(preset.selectedTools, deniedToolsText)
  }

  const toggleTool = (toolName: string, checked: boolean) => {
    const next = new Set(selection.selectedTools)
    if (checked) next.add(toolName)
    else next.delete(toolName)
    applySimpleSelection(Array.from(next), deniedToolsText)
  }

  const toggleModule = (toolNames: string[], checked: boolean) => {
    const next = new Set(selection.selectedTools)
    for (const toolName of toolNames) {
      if (checked) next.add(toolName)
      else next.delete(toolName)
    }
    applySimpleSelection(Array.from(next), deniedToolsText)
  }

  const handleDeniedToolsChange = (value: string) => {
    applySimpleSelection(selection.selectedTools, value)
  }

  const handleAdvancedChange = (value: string) => {
    setAdvancedText(value)
    try {
      const parsed = JSON.parse(value) as McpHubPermissionPolicyDocument
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Policy JSON must decode to an object")
      }
      setAdvancedError(null)
      onChange(parsed)
    } catch {
      setAdvancedError("Policy JSON must be valid before it can be saved.")
    }
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Space wrap>
        <Button
          type={editorMode === "simple" ? "primary" : "default"}
          onClick={() => setEditorMode("simple")}
        >
          Guided
        </Button>
        <Button
          type={editorMode === "advanced" ? "primary" : "default"}
          onClick={() => setEditorMode("advanced")}
        >
          Advanced JSON
        </Button>
      </Space>

      {editorMode === "simple" ? (
        <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
          {advancedKeys.length > 0 || selection.preservedPatterns.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              title="Advanced policy fields are present and will be preserved."
              description={[
                advancedKeys.length > 0 ? `Advanced keys: ${advancedKeys.join(", ")}` : null,
                selection.preservedPatterns.length > 0
                  ? `Non-registry allow rules: ${selection.preservedPatterns.join(", ")}`
                  : null
              ]
                .filter(Boolean)
                .join(" ")}
            />
          ) : null}

          <Card size="small" title="Presets">
            <Space wrap>
              {PRESET_OPTIONS.map((preset) => (
                <Button key={preset.key} size="small" onClick={() => handlePreset(preset.key)}>
                  {preset.label}
                </Button>
              ))}
            </Space>
          </Card>

          <Card size="small" title="Derived Capabilities">
            {derivedCapabilities.length > 0 ? (
              <Space wrap>
                {derivedCapabilities.map((capability) => (
                  <Tag key={capability} color={knownCapabilities.includes(capability) ? "blue" : "default"}>
                    {capability}
                  </Tag>
                ))}
              </Space>
            ) : (
              <Typography.Text type="secondary">
                No additional capability metadata will be written. With no allowed tools selected, the
                resulting policy does not add MCP Hub allowlist restrictions.
              </Typography.Text>
            )}
          </Card>

          <Card size="small" title="Allowed Modules And Tools">
            {modules.length > 0 ? (
              <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
                {modules.map((moduleGroup) => {
                  const moduleToolNames = moduleGroup.tools.map((tool) => tool.tool_name)
                  const allSelected =
                    moduleToolNames.length > 0 &&
                    moduleToolNames.every((toolName) => selection.selectedTools.includes(toolName))
                  return (
                    <Card
                      key={moduleGroup.module}
                      size="small"
                      title={
                        <Space wrap>
                          <Checkbox
                            checked={allSelected}
                            onChange={(event) => toggleModule(moduleToolNames, event.target.checked)}
                          >
                            {moduleGroup.display_name}
                          </Checkbox>
                          <Tag>{`${moduleGroup.tool_count} tools`}</Tag>
                          {Object.entries(moduleGroup.risk_summary)
                            .filter(([, count]) => Number(count) > 0)
                            .map(([riskClass, count]) => (
                              <Tag key={`${moduleGroup.module}-${riskClass}`}>{`${riskClass}:${count}`}</Tag>
                            ))}
                        </Space>
                      }
                    >
                      <Space wrap>
                        {moduleGroup.tools.map((tool) => (
                          <Checkbox
                            key={tool.tool_name}
                            checked={selection.selectedTools.includes(tool.tool_name)}
                            onChange={(event) => toggleTool(tool.tool_name, event.target.checked)}
                          >
                            <Space size={4}>
                              <span>{tool.display_name}</span>
                              <Tag>{tool.category}</Tag>
                              <Tag color={tool.risk_class === "high" ? "red" : tool.risk_class === "medium" ? "gold" : "green"}>
                                {tool.risk_class}
                              </Tag>
                            </Space>
                          </Checkbox>
                        ))}
                      </Space>
                    </Card>
                  )
                })}
              </Space>
            ) : (
              <Empty description="No registry metadata available yet" />
            )}
          </Card>

          <Space orientation="vertical" style={{ width: "100%" }}>
            <label htmlFor={`${formId}-denied-tools`}>Denied Tools</label>
            <textarea
              id={`${formId}-denied-tools`}
              aria-label="Denied Tools"
              value={deniedToolsText}
              onChange={(event) => handleDeniedToolsChange(event.target.value)}
              rows={4}
            />
          </Space>
        </Space>
      ) : (
        <Space orientation="vertical" style={{ width: "100%" }}>
          {advancedError ? <Alert type="error" showIcon title={advancedError} /> : null}
          <label htmlFor={`${formId}-advanced-policy`}>Policy JSON</label>
          <textarea
            id={`${formId}-advanced-policy`}
            aria-label="Policy JSON"
            value={advancedText}
            onChange={(event) => handleAdvancedChange(event.target.value)}
            rows={16}
          />
        </Space>
      )}
    </Space>
  )
}
