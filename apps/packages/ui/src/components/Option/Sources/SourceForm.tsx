import React from "react"
import { Alert, Button, Form, Input, Radio, Select, Space, Switch, Typography } from "antd"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import {
  useCreateIngestionSourceMutation,
  useUpdateIngestionSourceMutation
} from "@/hooks/use-ingestion-sources"
import type {
  CreateIngestionSourceRequest,
  IngestionSourceSummary,
  IngestionSourceType
} from "@/types/ingestion-sources"

type SourceFormValues = {
  source_type: IngestionSourceType
  sink_type: "media" | "notes"
  policy: "canonical" | "import_only"
  enabled: boolean
  schedule_enabled: boolean
  path?: string
}

type SourceFormProps = {
  mode: "create" | "edit"
  source?: IngestionSourceSummary | null
}

const hasLockedSourceIdentity = (source?: IngestionSourceSummary | null): boolean => {
  if (!source) {
    return false
  }
  return Boolean(source.last_successful_snapshot_id)
}

const getSourceTypeLabel = (sourceType: IngestionSourceType): string =>
  sourceType === "archive_snapshot" ? "Archive snapshot" : "Local directory"

const getSinkTypeLabel = (sinkType: IngestionSourceSummary["sink_type"] | "media" | "notes"): string =>
  sinkType === "media" ? "Media" : "Notes"

export const SourceForm: React.FC<SourceFormProps> = ({ mode, source }) => {
  const { t } = useTranslation(["sources", "common"])
  const navigate = useNavigate()
  const [form] = Form.useForm<SourceFormValues>()
  const initialSourceType = source?.source_type ?? "local_directory"
  const identityLocked = mode === "edit" && hasLockedSourceIdentity(source)
  const [sourceType, setSourceType] = React.useState<IngestionSourceType>(initialSourceType)
  const [submitError, setSubmitError] = React.useState<string | null>(null)

  const createMutation = useCreateIngestionSourceMutation()
  const updateMutation = useUpdateIngestionSourceMutation(source?.id ?? "")
  const activeMutation = mode === "edit" ? updateMutation : createMutation

  React.useEffect(() => {
    setSourceType(initialSourceType)
    form.setFieldsValue({
      source_type: initialSourceType,
      sink_type: source?.sink_type ?? "notes",
      policy: source?.policy ?? "canonical",
      enabled: source?.enabled ?? true,
      schedule_enabled: source?.schedule_enabled ?? false,
      path: typeof source?.config?.path === "string" ? source.config.path : ""
    })
  }, [
    form,
    initialSourceType,
    source?.config,
    source?.enabled,
    source?.policy,
    source?.schedule_enabled,
    source?.sink_type
  ])

  const handleFinish = async (values: SourceFormValues) => {
    setSubmitError(null)

    const payload: CreateIngestionSourceRequest = {
      source_type: identityLocked && source ? source.source_type : sourceType,
      sink_type: identityLocked && source ? source.sink_type : values.sink_type,
      policy: values.policy,
      enabled: values.enabled,
      schedule_enabled: values.schedule_enabled,
      schedule: {},
      config:
        (identityLocked && source ? source.source_type : sourceType) === "local_directory"
          ? {
              path:
                identityLocked && typeof source?.config?.path === "string"
                  ? source.config.path
                  : (values.path || "").trim()
            }
          : {}
    }

    try {
      const result =
        mode === "edit" && source
          ? await updateMutation.mutateAsync(payload)
          : await createMutation.mutateAsync(payload)

      if (mode === "create") {
        navigate(`/sources/${result.id}`)
      }
    } catch (error: any) {
      setSubmitError(error?.message || "Failed to save source")
    }
  }

  return (
    <div className="space-y-4">
      {submitError ? <Alert type="error" title={submitError} /> : null}

      <Form<SourceFormValues>
        form={form}
        layout="vertical"
        initialValues={{
          source_type: initialSourceType,
          sink_type: source?.sink_type ?? "notes",
          policy: source?.policy ?? "canonical",
          enabled: source?.enabled ?? true,
          schedule_enabled: source?.schedule_enabled ?? false,
          path: typeof source?.config?.path === "string" ? source.config.path : ""
        }}
        onFinish={(values) => {
          void handleFinish(values)
        }}>
        {identityLocked && source ? (
          <Alert
            type="info"
            title="Locked after first successful sync"
            description={
              <div className="space-y-2">
                <div>
                  <Typography.Text strong>
                    {t("sources:form.sourceType", "Source type")}
                  </Typography.Text>
                  <div>{getSourceTypeLabel(source.source_type)}</div>
                </div>
                <div>
                  <Typography.Text strong>Current destination</Typography.Text>
                  <div>{getSinkTypeLabel(source.sink_type)}</div>
                </div>
                {typeof source.config?.path === "string" && source.config.path.trim().length > 0 ? (
                  <div>
                    <Typography.Text strong>
                      {t("sources:form.path", "Server directory path")}
                    </Typography.Text>
                    <div>{source.config.path}</div>
                  </div>
                ) : null}
              </div>
            }
          />
        ) : (
          <>
            <Form.Item
              name="source_type"
              label={t("sources:form.sourceType", "Source type")}>
              <Radio.Group
                onChange={(event) => setSourceType(event.target.value as IngestionSourceType)}>
                <Space orientation="vertical">
                  <Radio value="local_directory">
                    {t("sources:form.localDirectory", "Local directory")}
                  </Radio>
                  <Radio value="archive_snapshot">
                    {t("sources:form.archiveSnapshot", "Archive snapshot")}
                  </Radio>
                </Space>
              </Radio.Group>
            </Form.Item>

            <Form.Item name="sink_type" label="Destination">
              <Select
                options={[
                  { value: "notes", label: "Notes" },
                  { value: "media", label: "Media" }
                ]}
              />
            </Form.Item>
          </>
        )}

        <Form.Item name="policy" label="Lifecycle policy">
          <Select
            options={[
              { value: "canonical", label: "Canonical" },
              { value: "import_only", label: "Import only" }
            ]}
          />
        </Form.Item>

        <Form.Item name="enabled" label="Enabled" valuePropName="checked">
          <Switch />
        </Form.Item>

        {(identityLocked && source ? source.source_type : sourceType) === "local_directory" && !identityLocked ? (
          <>
            <Form.Item
              name="path"
              label={t("sources:form.path", "Server directory path")}
              rules={[
                {
                  required: true,
                  message: t("sources:form.path", "Server directory path")
                }
              ]}>
              <Input />
            </Form.Item>
            <Typography.Text type="secondary">
              {t(
                "sources:form.pathHelp",
                "This is a path on the tldw server host, not a local browser or extension folder."
              )}
            </Typography.Text>
          </>
        ) : (
          <Alert
            type="info"
            title={t("sources:form.archiveHint", "Upload archive after creation")}
          />
        )}

        <div className="pt-4">
          <Button
            type="primary"
            htmlType="submit"
            loading={Boolean((activeMutation as { isPending?: boolean }).isPending)}>
            {mode === "create" ? "Create source" : "Save changes"}
          </Button>
        </div>
      </Form>
    </div>
  )
}
