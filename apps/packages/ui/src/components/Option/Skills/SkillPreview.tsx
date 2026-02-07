import React from "react"
import { useMutation } from "@tanstack/react-query"
import { Button, Input, Modal, Tag } from "antd"
import { useTranslation } from "react-i18next"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import type { SkillExecutionResult } from "@/types/skill"

interface SkillPreviewProps {
  skillName: string | null
  onClose: () => void
}

export const SkillPreview: React.FC<SkillPreviewProps> = ({
  skillName,
  onClose
}) => {
  const { t } = useTranslation(["option", "common"])
  const [args, setArgs] = React.useState("")
  const [result, setResult] = React.useState<SkillExecutionResult | null>(null)

  React.useEffect(() => {
    if (!skillName) {
      setArgs("")
      setResult(null)
    }
  }, [skillName])

  const executeMutation = useMutation({
    mutationFn: () => tldwClient.executeSkill(skillName!, args),
    onSuccess: (data: SkillExecutionResult) => {
      setResult(data)
    }
  })

  const handlePreview = () => {
    if (skillName) {
      executeMutation.mutate()
    }
  }

  return (
    <Modal
      title={t("option:skills.previewTitle", {
        defaultValue: "Preview Skill",
        name: skillName
      })}
      open={Boolean(skillName)}
      onCancel={onClose}
      footer={null}
      width={640}
      destroyOnClose
    >
      <div className="flex flex-col gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium">
            {t("option:skills.previewArgs", {
              defaultValue: "Test Arguments"
            })}
          </label>
          <Input
            value={args}
            onChange={(e) => setArgs(e.target.value)}
            placeholder={t("option:skills.previewArgsPlaceholder", {
              defaultValue: "Enter test arguments..."
            })}
            onPressEnter={handlePreview}
          />
        </div>

        <Button
          type="primary"
          onClick={handlePreview}
          loading={executeMutation.isPending}
        >
          {t("option:skills.previewRun", { defaultValue: "Preview" })}
        </Button>

        {executeMutation.isError && (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {(executeMutation.error as any)?.message || "Execution failed"}
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Tag color={result.execution_mode === "fork" ? "blue" : "green"}>
                {result.execution_mode}
              </Tag>
              {result.model_override && (
                <Tag>{result.model_override}</Tag>
              )}
              {result.allowed_tools?.map((tool) => (
                <Tag key={tool} color="orange">
                  {tool}
                </Tag>
              ))}
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                {t("option:skills.previewRendered", {
                  defaultValue: "Rendered Prompt"
                })}
              </label>
              <Input.TextArea
                value={result.rendered_prompt}
                readOnly
                rows={10}
                className="font-mono text-xs"
              />
            </div>

            {result.fork_output && (
              <div>
                <label className="mb-1 block text-sm font-medium">
                  {t("option:skills.previewForkOutput", {
                    defaultValue: "Fork Output"
                  })}
                </label>
                <Input.TextArea
                  value={result.fork_output}
                  readOnly
                  rows={6}
                  className="font-mono text-xs"
                />
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
