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

type GitRepositoryMode = "local_repo" | "remote_github_repo"

type SourceFormValues = {
  source_type: IngestionSourceType
  sink_type: "media" | "notes"
  policy: "canonical" | "import_only"
  enabled: boolean
  schedule_enabled: boolean
  path?: string
  git_repository_mode?: GitRepositoryMode
  repo_path?: string
  repo_url?: string
  ref?: string
  root_subpath?: string
  account_id?: string
  respect_gitignore?: boolean
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

const getSourceTypeLabel = (sourceType: IngestionSourceType): string => {
  if (sourceType === "archive_snapshot") {
    return "Archive snapshot"
  }
  if (sourceType === "git_repository") {
    return "Git repository"
  }
  return "Local directory"
}

const getSinkTypeLabel = (sinkType: IngestionSourceSummary["sink_type"] | "media" | "notes"): string =>
  sinkType === "media" ? "Media" : "Notes"

const getInitialGitRepositoryMode = (source?: IngestionSourceSummary | null): GitRepositoryMode =>
  source?.source_type === "git_repository" && source.config?.mode === "remote_github_repo"
    ? "remote_github_repo"
    : "local_repo"

export const SourceForm: React.FC<SourceFormProps> = ({ mode, source }) => {
  const { t } = useTranslation(["sources", "common"])
  const navigate = useNavigate()
  const [form] = Form.useForm<SourceFormValues>()
  const initialSourceType = source?.source_type ?? "local_directory"
  const initialGitRepositoryMode = getInitialGitRepositoryMode(source)
  const identityLocked = mode === "edit" && hasLockedSourceIdentity(source)
  const [sourceType, setSourceType] = React.useState<IngestionSourceType>(initialSourceType)
  const [gitRepositoryMode, setGitRepositoryMode] =
    React.useState<GitRepositoryMode>(initialGitRepositoryMode)
  const [submitError, setSubmitError] = React.useState<string | null>(null)

  const createMutation = useCreateIngestionSourceMutation()
  const updateMutation = useUpdateIngestionSourceMutation(source?.id ?? "")
  const activeMutation = mode === "edit" ? updateMutation : createMutation

  React.useEffect(() => {
    setSourceType(initialSourceType)
    setGitRepositoryMode(initialGitRepositoryMode)
    form.setFieldsValue({
      source_type: initialSourceType,
      sink_type: source?.sink_type ?? "notes",
      policy: source?.policy ?? "canonical",
      enabled: source?.enabled ?? true,
      schedule_enabled: source?.schedule_enabled ?? false,
      path: typeof source?.config?.path === "string" ? source.config.path : "",
      git_repository_mode: initialGitRepositoryMode,
      repo_path:
        source?.source_type === "git_repository" && typeof source?.config?.path === "string"
          ? source.config.path
          : "",
      repo_url:
        source?.source_type === "git_repository" && typeof source?.config?.repo_url === "string"
          ? source.config.repo_url
          : "",
      ref:
        source?.source_type === "git_repository" && typeof source?.config?.ref === "string"
          ? source.config.ref
          : "",
      root_subpath:
        source?.source_type === "git_repository" && typeof source?.config?.root_subpath === "string"
          ? source.config.root_subpath
          : "",
      account_id:
        source?.source_type === "git_repository" && source?.config?.account_id != null
          ? String(source.config.account_id)
          : "",
      respect_gitignore:
        source?.source_type === "git_repository"
          ? source.config?.respect_gitignore !== false
          : true
    })
  }, [
    form,
    initialGitRepositoryMode,
    initialSourceType,
    source?.config,
    source?.enabled,
    source?.policy,
    source?.schedule_enabled,
    source?.sink_type
  ])

  const handleFinish = async (values: SourceFormValues) => {
    setSubmitError(null)

    const effectiveSourceType = identityLocked && source ? source.source_type : sourceType
    const effectiveGitRepositoryMode =
      effectiveSourceType === "git_repository"
        ? identityLocked && source && source.config?.mode === "remote_github_repo"
          ? "remote_github_repo"
          : values.git_repository_mode ?? gitRepositoryMode
        : "local_repo"

    const payload: CreateIngestionSourceRequest = {
      source_type: effectiveSourceType,
      sink_type: identityLocked && source ? source.sink_type : values.sink_type,
      policy: values.policy,
      enabled: values.enabled,
      schedule_enabled: values.schedule_enabled ?? false,
      schedule: {},
      config: (() => {
        if (effectiveSourceType === "local_directory") {
          return {
            path:
              identityLocked && typeof source?.config?.path === "string"
                ? source.config.path
                : (values.path || "").trim()
          }
        }
        if (effectiveSourceType === "git_repository") {
          const ref = (values.ref || "").trim()
          const rootSubpath = (values.root_subpath || "").trim()
          const accountId = (values.account_id || "").trim()
          if (effectiveGitRepositoryMode === "remote_github_repo") {
            return {
              mode: "remote_github_repo",
              repo_url:
                identityLocked && typeof source?.config?.repo_url === "string"
                  ? source.config.repo_url
                  : (values.repo_url || "").trim(),
              ...(accountId ? { account_id: Number(accountId) } : {}),
              ...(ref ? { ref } : {}),
              ...(rootSubpath ? { root_subpath: rootSubpath } : {})
            }
          }
          return {
            mode: "local_repo",
            path:
              identityLocked && typeof source?.config?.path === "string"
                ? source.config.path
                : (values.repo_path || "").trim(),
            ...(ref ? { ref } : {}),
            ...(rootSubpath ? { root_subpath: rootSubpath } : {}),
            respect_gitignore: values.respect_gitignore !== false
          }
        }
        return {}
      })()
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
          path: typeof source?.config?.path === "string" ? source.config.path : "",
          git_repository_mode: initialGitRepositoryMode,
          repo_path:
            source?.source_type === "git_repository" && typeof source?.config?.path === "string"
              ? source.config.path
              : "",
          repo_url:
            source?.source_type === "git_repository" && typeof source?.config?.repo_url === "string"
              ? source.config.repo_url
              : "",
          ref:
            source?.source_type === "git_repository" && typeof source?.config?.ref === "string"
              ? source.config.ref
              : "",
          root_subpath:
            source?.source_type === "git_repository" && typeof source?.config?.root_subpath === "string"
              ? source.config.root_subpath
              : "",
          account_id:
            source?.source_type === "git_repository" && source?.config?.account_id != null
              ? String(source.config.account_id)
              : "",
          respect_gitignore:
            source?.source_type === "git_repository"
              ? source.config?.respect_gitignore !== false
              : true
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
                {source.source_type === "git_repository" && typeof source.config?.repo_url === "string" ? (
                  <div>
                    <Typography.Text strong>
                      {t("sources:form.repoUrl", "GitHub repository URL")}
                    </Typography.Text>
                    <div>{source.config.repo_url}</div>
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
                  <Radio value="git_repository">
                    {t("sources:form.gitRepository", "Git repository")}
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
        ) : (identityLocked && source ? source.source_type : sourceType) === "git_repository" && !identityLocked ? (
          <>
            <Form.Item
              name="git_repository_mode"
              label={t("sources:form.gitRepositoryMode", "Repository mode")}>
              <Radio.Group
                onChange={(event) => setGitRepositoryMode(event.target.value as GitRepositoryMode)}>
                <Space orientation="vertical">
                  <Radio value="local_repo">
                    {t("sources:form.localGitRepository", "Local checked-out repository")}
                  </Radio>
                  <Radio value="remote_github_repo">
                    {t("sources:form.remoteGitRepository", "Remote GitHub repository")}
                  </Radio>
                </Space>
              </Radio.Group>
            </Form.Item>

            {gitRepositoryMode === "local_repo" ? (
              <>
                <Form.Item
                  name="repo_path"
                  label={t("sources:form.repoPath", "Repository path")}
                  rules={[
                    {
                      required: true,
                      message: t("sources:form.repoPath", "Repository path")
                    }
                  ]}>
                  <Input />
                </Form.Item>
                <Typography.Text type="secondary">
                  {t(
                    "sources:form.repoPathHelp",
                    "Use a checked-out repository path on the tldw server host."
                  )}
                </Typography.Text>
                <Form.Item
                  name="respect_gitignore"
                  label={t("sources:form.respectGitignore", "Respect .gitignore")}
                  valuePropName="checked">
                  <Switch />
                </Form.Item>
              </>
            ) : (
              <>
                <Form.Item
                  name="repo_url"
                  label={t("sources:form.repoUrl", "GitHub repository URL")}
                  rules={[
                    {
                      required: true,
                      message: t("sources:form.repoUrl", "GitHub repository URL")
                    }
                  ]}>
                  <Input />
                </Form.Item>
                <Form.Item
                  name="account_id"
                  label={t("sources:form.accountId", "Linked account ID")}>
                  <Input />
                </Form.Item>
              </>
            )}

            <Form.Item
              name="ref"
              label={t("sources:form.ref", "Branch, tag, or ref")}>
              <Input />
            </Form.Item>
            <Form.Item
              name="root_subpath"
              label={t("sources:form.rootSubpath", "Root subpath")}>
              <Input />
            </Form.Item>
          </>
        ) : (identityLocked && source ? source.source_type : sourceType) === "archive_snapshot" ? (
          <Alert
            type="info"
            title={t("sources:form.archiveHint", "Upload archive after creation")}
          />
        ) : (
          <Alert
            type="info"
            title={t("sources:form.gitRepositoryHint", "Git repository details are configured below.")}
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
