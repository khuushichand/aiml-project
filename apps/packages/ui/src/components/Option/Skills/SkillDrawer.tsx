import React from "react"
import { useMutation } from "@tanstack/react-query"
import { Button, Drawer, Form, Input, Space } from "antd"
import { useTranslation } from "react-i18next"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import type { SkillResponse } from "@/types/skill"

const SKILL_NAME_REGEX = /^[a-z][a-z0-9-]{0,63}$/

interface SkillDrawerProps {
  open: boolean
  skill: SkillResponse | null
  onClose: () => void
  onSaved: () => void
}

export const SkillDrawer: React.FC<SkillDrawerProps> = ({
  open,
  skill,
  onClose,
  onSaved
}) => {
  const { t } = useTranslation(["option", "common"])
  const notification = useAntdNotification()
  const [form] = Form.useForm()
  const isEdit = Boolean(skill)

  React.useEffect(() => {
    if (open) {
      if (skill) {
        form.setFieldsValue({
          name: skill.name,
          content: skill.content
        })
      } else {
        form.resetFields()
      }
    }
  }, [open, skill, form])

  const createMutation = useMutation({
    mutationFn: (values: { name: string; content: string }) =>
      tldwClient.createSkill(values),
    onSuccess: () => {
      notification.success({
        message: t("option:skills.createSuccess", { defaultValue: "Skill created" })
      })
      onSaved()
    },
    onError: (err: any) => {
      const desc =
        err?.message?.includes("409") || err?.status === 409
          ? t("option:skills.duplicateError", {
              defaultValue: "A skill with this name already exists."
            })
          : err?.message
      notification.error({
        message: t("option:skills.createError", { defaultValue: "Failed to create skill" }),
        description: desc
      })
    }
  })

  const updateMutation = useMutation({
    mutationFn: (values: { content: string }) =>
      tldwClient.updateSkill(skill!.name, values, skill!.version),
    onSuccess: () => {
      notification.success({
        message: t("option:skills.updateSuccess", { defaultValue: "Skill updated" })
      })
      onSaved()
    },
    onError: (err: any) => {
      const desc =
        err?.message?.includes("409") || err?.status === 409
          ? t("option:skills.versionConflict", {
              defaultValue:
                "Version conflict: the skill was modified elsewhere. Please reload and try again."
            })
          : err?.message
      notification.error({
        message: t("option:skills.updateError", { defaultValue: "Failed to update skill" }),
        description: desc
      })
    }
  })

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (isEdit) {
        updateMutation.mutate({ content: values.content })
      } else {
        createMutation.mutate({ name: values.name, content: values.content })
      }
    } catch {
      // validation errors handled by antd
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  return (
    <Drawer
      title={
        isEdit
          ? t("option:skills.editTitle", { defaultValue: "Edit Skill" })
          : t("option:skills.newTitle", { defaultValue: "New Skill" })
      }
      open={open}
      onClose={onClose}
      width={640}
      destroyOnClose
      extra={
        <Space>
          <Button onClick={onClose}>
            {t("common:cancel", { defaultValue: "Cancel" })}
          </Button>
          <Button type="primary" onClick={handleSubmit} loading={isSaving}>
            {t("common:save", { defaultValue: "Save" })}
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item
          name="name"
          label={t("option:skills.nameLabel", { defaultValue: "Name" })}
          rules={[
            {
              required: true,
              message: t("option:skills.nameRequired", {
                defaultValue: "Skill name is required"
              })
            },
            {
              pattern: SKILL_NAME_REGEX,
              message: t("option:skills.nameInvalid", {
                defaultValue:
                  "Must start with a letter, use only lowercase letters, numbers, and hyphens (max 64 chars)"
              })
            }
          ]}
        >
          <Input
            placeholder="my-skill-name"
            disabled={isEdit}
            maxLength={64}
            className="font-mono"
          />
        </Form.Item>

        <Form.Item
          name="content"
          label={t("option:skills.contentLabel", {
            defaultValue: "SKILL.md Content"
          })}
          rules={[
            {
              required: true,
              message: t("option:skills.contentRequired", {
                defaultValue: "Content is required"
              })
            }
          ]}
          extra={t("option:skills.contentHelp", {
            defaultValue:
              "Write YAML frontmatter (---) at the top for metadata (description, context, allowed-tools). Use $ARGUMENTS for argument substitution."
          })}
        >
          <Input.TextArea
            rows={20}
            className="font-mono text-xs"
            placeholder={`---
description: What this skill does
argument-hint: "[text]"
context: inline
---

Process the following: $ARGUMENTS`}
          />
        </Form.Item>
      </Form>
    </Drawer>
  )
}
