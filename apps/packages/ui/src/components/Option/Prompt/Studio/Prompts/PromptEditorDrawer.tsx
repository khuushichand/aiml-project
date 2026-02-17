import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Drawer, Form, Input, notification, Skeleton, Collapse, Alert } from "antd"
import { Plus, Trash2 } from "lucide-react"
import React, { useEffect } from "react"
import { useTranslation } from "react-i18next"
import {
  createPrompt,
  updatePrompt,
  getPrompt,
  type PromptCreatePayload,
  type PromptUpdatePayload,
  type FewShotExample,
  type PromptModule
} from "@/services/prompt-studio"
import { Button } from "@/components/Common/Button"

type PromptEditorDrawerProps = {
  open: boolean
  promptId: number | null
  projectId: number
  onClose: () => void
}

type FormValues = {
  name: string
  system_prompt?: string
  user_prompt?: string
  change_description?: string
  few_shot_examples?: string // JSON string for few-shot examples
  modules_config?: string // JSON string for modules config
}

export const PromptEditorDrawer: React.FC<PromptEditorDrawerProps> = ({
  open,
  promptId,
  projectId,
  onClose
}) => {
  const { t } = useTranslation(["settings", "common"])
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()

  const isEditing = promptId !== null

  // Fetch existing prompt for editing
  const { data: promptResponse, isLoading: isLoadingPrompt } = useQuery({
    queryKey: ["prompt-studio", "prompt", promptId],
    queryFn: () => getPrompt(promptId!),
    enabled: open && isEditing
  })

  const existingPrompt = (promptResponse as any)?.data?.data

  // Set form values when editing
  useEffect(() => {
    if (open && isEditing && existingPrompt) {
      form.setFieldsValue({
        name: existingPrompt.name,
        system_prompt: existingPrompt.system_prompt || "",
        user_prompt: existingPrompt.user_prompt || "",
        change_description: "",
        few_shot_examples: existingPrompt.few_shot_examples
          ? JSON.stringify(existingPrompt.few_shot_examples, null, 2)
          : "",
        modules_config: existingPrompt.modules_config
          ? JSON.stringify(existingPrompt.modules_config, null, 2)
          : ""
      })
    } else if (open && !isEditing) {
      form.resetFields()
    }
  }, [open, isEditing, existingPrompt, form])

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (values: PromptCreatePayload) =>
      createPrompt(values, crypto.randomUUID()),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["prompt-studio", "prompts", projectId]
      })
      notification.success({
        message: t("managePrompts.studio.prompts.createSuccess", {
          defaultValue: "Prompt created"
        })
      })
      onClose()
    },
    onError: (error: any) => {
      notification.error({
        message: t("common:error", { defaultValue: "Error" }),
        description: error?.message || t("common:unknownError")
      })
    }
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (values: PromptUpdatePayload) =>
      updatePrompt(promptId!, values),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["prompt-studio", "prompts", projectId]
      })
      queryClient.invalidateQueries({
        queryKey: ["prompt-studio", "prompt", promptId]
      })
      notification.success({
        message: t("managePrompts.studio.prompts.updateSuccess", {
          defaultValue: "Prompt updated"
        }),
        description: t("managePrompts.studio.prompts.newVersionCreated", {
          defaultValue: "A new version has been created."
        })
      })
      onClose()
    },
    onError: (error: any) => {
      notification.error({
        message: t("common:error", { defaultValue: "Error" }),
        description: error?.message || t("common:unknownError")
      })
    }
  })

  const parseJsonField = <T,>(value: string | undefined, defaultValue: T): T => {
    if (!value?.trim()) return defaultValue
    try {
      return JSON.parse(value)
    } catch {
      return defaultValue
    }
  }

  const handleSubmit = (values: FormValues) => {
    const fewShotExamples = parseJsonField<FewShotExample[] | null>(
      values.few_shot_examples,
      null
    )
    const modulesConfig = parseJsonField<PromptModule[] | null>(
      values.modules_config,
      null
    )

    if (isEditing) {
      const payload: PromptUpdatePayload = {
        name: values.name.trim(),
        system_prompt: values.system_prompt?.trim() || null,
        user_prompt: values.user_prompt?.trim() || null,
        change_description:
          values.change_description?.trim() || "Updated prompt",
        few_shot_examples: fewShotExamples,
        modules_config: modulesConfig
      }
      updateMutation.mutate(payload)
    } else {
      const payload: PromptCreatePayload = {
        project_id: projectId,
        name: values.name.trim(),
        system_prompt: values.system_prompt?.trim() || null,
        user_prompt: values.user_prompt?.trim() || null,
        change_description: values.change_description?.trim() || "Initial version",
        few_shot_examples: fewShotExamples,
        modules_config: modulesConfig
      }
      createMutation.mutate(payload)
    }
  }

  const validateJson = (_: any, value: string) => {
    if (!value?.trim()) return Promise.resolve()
    try {
      JSON.parse(value)
      return Promise.resolve()
    } catch (e) {
      return Promise.reject(
        new Error(
          t("managePrompts.studio.prompts.invalidJson", {
            defaultValue: "Invalid JSON format"
          })
        )
      )
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={
        isEditing
          ? t("managePrompts.studio.prompts.editTitle", {
              defaultValue: "Edit Prompt"
            })
          : t("managePrompts.studio.prompts.createTitle", {
              defaultValue: "Create Prompt"
            })
      }
      styles={{ wrapper: { width: 640 } }}
      destroyOnHidden
      footer={
        <div className="flex justify-end gap-2">
          <Button type="secondary" onClick={onClose} disabled={isPending}>
            {t("common:cancel", { defaultValue: "Cancel" })}
          </Button>
          <Button
            type="primary"
            onClick={() => form.submit()}
            loading={isPending}
          >
            {isEditing
              ? t("common:save", { defaultValue: "Save" })
              : t("managePrompts.studio.prompts.createBtn", {
                  defaultValue: "Create Prompt"
                })}
          </Button>
        </div>
      }
    >
      {isEditing && isLoadingPrompt ? (
        <Skeleton paragraph={{ rows: 8 }} />
      ) : (
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="name"
            label={t("managePrompts.studio.prompts.form.name", {
              defaultValue: "Prompt Name"
            })}
            rules={[
              {
                required: true,
                message: t("managePrompts.studio.prompts.form.nameRequired", {
                  defaultValue: "Please enter a prompt name"
                })
              }
            ]}
          >
            <Input
              placeholder={t(
                "managePrompts.studio.prompts.form.namePlaceholder",
                {
                  defaultValue: "e.g., Customer Support Response"
                }
              )}
              autoFocus
            />
          </Form.Item>

          <Form.Item
            name="system_prompt"
            label={t("managePrompts.studio.prompts.form.systemPrompt", {
              defaultValue: "System Prompt"
            })}
            tooltip={t("managePrompts.studio.prompts.form.systemPromptHelp", {
              defaultValue:
                "Instructions that set the behavior and context for the AI"
            })}
          >
            <Input.TextArea
              placeholder={t(
                "managePrompts.studio.prompts.form.systemPromptPlaceholder",
                {
                  defaultValue:
                    "You are a helpful customer support agent..."
                }
              )}
              rows={5}
              showCount
              maxLength={10000}
            />
          </Form.Item>

          <Form.Item
            name="user_prompt"
            label={t("managePrompts.studio.prompts.form.userPrompt", {
              defaultValue: "User Prompt Template"
            })}
            tooltip={t("managePrompts.studio.prompts.form.userPromptHelp", {
              defaultValue:
                "Template for user messages. Use {{variable}} for inputs."
            })}
          >
            <Input.TextArea
              placeholder={t(
                "managePrompts.studio.prompts.form.userPromptPlaceholder",
                {
                  defaultValue:
                    "Please help the customer with: {{customer_query}}"
                }
              )}
              rows={5}
              showCount
              maxLength={10000}
            />
          </Form.Item>

          {isEditing && (
            <Form.Item
              name="change_description"
              label={t("managePrompts.studio.prompts.form.changeDescription", {
                defaultValue: "Change Description"
              })}
              rules={[
                {
                  required: true,
                  message: t(
                    "managePrompts.studio.prompts.form.changeDescriptionRequired",
                    {
                      defaultValue:
                        "Please describe what you changed (required for version history)"
                    }
                  )
                }
              ]}
            >
              <Input
                placeholder={t(
                  "managePrompts.studio.prompts.form.changeDescriptionPlaceholder",
                  {
                    defaultValue: "e.g., Improved tone for friendlier responses"
                  }
                )}
              />
            </Form.Item>
          )}

          <Collapse
            ghost
            items={[
              {
                key: "advanced",
                label: t("managePrompts.studio.prompts.form.advancedOptions", {
                  defaultValue: "Advanced Options"
                }),
                children: (
                  <div className="space-y-4">
                    <Alert
                      type="info"
                      showIcon
                      title={t(
                        "managePrompts.studio.prompts.form.advancedInfo",
                        {
                          defaultValue:
                            "These fields accept JSON. Few-shot examples help the model learn from examples."
                        }
                      )}
                    />

                    <Form.Item
                      name="few_shot_examples"
                      label={t(
                        "managePrompts.studio.prompts.form.fewShotExamples",
                        {
                          defaultValue: "Few-Shot Examples (JSON)"
                        }
                      )}
                      rules={[{ validator: validateJson }]}
                      tooltip={t(
                        "managePrompts.studio.prompts.form.fewShotHelp",
                        {
                          defaultValue:
                            'Array of {inputs: {...}, outputs: {...}, explanation?: "..."}'
                        }
                      )}
                    >
                      <Input.TextArea
                        placeholder={`[
  {
    "inputs": {"query": "How do I reset my password?"},
    "outputs": {"response": "To reset your password..."},
    "explanation": "Shows helpful step-by-step response"
  }
]`}
                        rows={6}
                        className="font-mono text-sm"
                      />
                    </Form.Item>

                    <Form.Item
                      name="modules_config"
                      label={t(
                        "managePrompts.studio.prompts.form.modulesConfig",
                        {
                          defaultValue: "Modules Configuration (JSON)"
                        }
                      )}
                      rules={[{ validator: validateJson }]}
                      tooltip={t(
                        "managePrompts.studio.prompts.form.modulesHelp",
                        {
                          defaultValue:
                            "Configure special modules like Chain-of-Thought, ReAct, etc."
                        }
                      )}
                    >
                      <Input.TextArea
                        placeholder={`[
  {
    "type": "chain_of_thought",
    "enabled": true,
    "config": {"style": "step_by_step"}
  }
]`}
                        rows={6}
                        className="font-mono text-sm"
                      />
                    </Form.Item>
                  </div>
                )
              }
            ]}
          />
        </Form>
      )}
    </Drawer>
  )
}
