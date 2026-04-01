import React, { useCallback, useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Alert, Button, Input, Select, Space, Table, Tag, Tooltip, message } from "antd"
import { Key, Plus, RefreshCw, Trash2, CheckCircle2, XCircle, Loader2 } from "lucide-react"
import { tldwClient } from "@/services/tldw/TldwApiClient"

type ProviderKey = {
  provider: string
  status: string
  api_key_hint: string | null
  has_api_key: boolean
  credential_fields: Record<string, unknown> | null
  created_at: string | null
  updated_at: string | null
}

const PROVIDER_OPTIONS = [
  "openai",
  "anthropic",
  "google",
  "groq",
  "deepseek",
  "mistral",
  "cohere",
  "openrouter",
  "huggingface",
  "moonshot",
  "qwen",
  "together",
  "elevenlabs",
]

export const ProviderKeysSettings = () => {
  const { t } = useTranslation(["settings", "common"])
  const [keys, setKeys] = useState<ProviderKey[]>([])
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [byokUnavailable, setByokUnavailable] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Add form state
  const [showAddForm, setShowAddForm] = useState(false)
  const [addProvider, setAddProvider] = useState<string>("")
  const [addApiKey, setAddApiKey] = useState("")
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [saving, setSaving] = useState(false)

  const loadKeys = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await tldwClient.listUserProviderKeys()
      setKeys(res.keys ?? [])
      setConfiguredProviders(res.configured_providers ?? [])
      setByokUnavailable(false)
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status
      if (status === 403) {
        setByokUnavailable(true)
      } else {
        setError("Failed to load provider keys")
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadKeys()
  }, [loadKeys])

  const handleTest = useCallback(async () => {
    if (!addProvider || !addApiKey) return
    setTesting(true)
    setTestResult(null)
    try {
      const res = await tldwClient.testUserProviderKey(addProvider, addApiKey)
      setTestResult({ success: res.success, message: res.message })
    } catch {
      setTestResult({ success: false, message: "Connection test failed" })
    } finally {
      setTesting(false)
    }
  }, [addProvider, addApiKey])

  const handleSave = useCallback(async () => {
    if (!addProvider || !addApiKey) return
    setSaving(true)
    try {
      await tldwClient.upsertUserProviderKey(addProvider, addApiKey)
      message.success(`${addProvider} key saved`)
      setShowAddForm(false)
      setAddProvider("")
      setAddApiKey("")
      setTestResult(null)
      void loadKeys()
    } catch {
      message.error("Failed to save key")
    } finally {
      setSaving(false)
    }
  }, [addProvider, addApiKey, loadKeys])

  const handleDelete = useCallback(
    async (provider: string) => {
      try {
        await tldwClient.deleteUserProviderKey(provider)
        message.success(`${provider} key removed`)
        void loadKeys()
      } catch {
        message.error("Failed to remove key")
      }
    },
    [loadKeys]
  )

  if (byokUnavailable) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-6">
        <Alert
          type="info"
          showIcon
          message="Provider key management is not available"
          description="Set BYOK_ENCRYPTION_KEY in your server's .env file to enable user-managed provider keys. Docker users: this is auto-generated on first run."
        />
      </div>
    )
  }

  const columns = [
    {
      title: "Provider",
      dataIndex: "provider",
      key: "provider",
      render: (provider: string) => (
        <span className="font-medium capitalize">{provider}</span>
      ),
    },
    {
      title: "Source",
      key: "source",
      render: (_: unknown, record: ProviderKey) =>
        record.has_api_key ? (
          <Tag color="blue">User key</Tag>
        ) : configuredProviders.includes(record.provider) ? (
          <Tag>Server default</Tag>
        ) : (
          <Tag color="default">Not configured</Tag>
        ),
    },
    {
      title: "Key Hint",
      dataIndex: "api_key_hint",
      key: "hint",
      render: (hint: string | null) =>
        hint ? (
          <code className="text-xs text-text-muted">...{hint}</code>
        ) : (
          <span className="text-text-subtle">-</span>
        ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={status === "active" ? "green" : status === "revoked" ? "red" : "default"}>
          {status}
        </Tag>
      ),
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, record: ProviderKey) =>
        record.has_api_key ? (
          <Tooltip title="Remove your key (falls back to server default)">
            <Button
              type="text"
              danger
              size="small"
              icon={<Trash2 className="h-3.5 w-3.5" />}
              onClick={() => void handleDelete(record.provider)}
            />
          </Tooltip>
        ) : null,
    },
  ]

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-text">
          LLM Provider Keys
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Manage API keys for LLM providers. Server-configured keys from .env are used as defaults.
          Add your own key to override.
        </p>
      </div>

      {error && (
        <Alert type="error" message={error} className="mb-4" closable onClose={() => setError(null)} />
      )}

      <div className="mb-4 flex items-center justify-between">
        <Button
          icon={<RefreshCw className="h-4 w-4" />}
          onClick={() => void loadKeys()}
          loading={loading}
          size="small"
        >
          Refresh
        </Button>
        <Button
          type="primary"
          icon={<Plus className="h-4 w-4" />}
          onClick={() => setShowAddForm(true)}
          disabled={showAddForm}
        >
          Add Provider Key
        </Button>
      </div>

      {showAddForm && (
        <div className="mb-6 rounded-xl border border-border bg-surface/80 p-5">
          <h3 className="mb-4 text-sm font-semibold text-text">Add Provider Key</h3>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">Provider</label>
              <Select
                value={addProvider || undefined}
                onChange={(v) => { setAddProvider(v); setTestResult(null) }}
                placeholder="Select provider..."
                className="w-full"
                options={PROVIDER_OPTIONS.map((p) => ({
                  label: <span className="capitalize">{p}</span>,
                  value: p,
                }))}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">API Key</label>
              <Input.Password
                value={addApiKey}
                onChange={(e) => { setAddApiKey(e.target.value); setTestResult(null) }}
                placeholder="sk-..."
                autoComplete="off"
              />
            </div>

            {testResult && (
              <div
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                  testResult.success
                    ? "border border-green-500/30 bg-green-500/5 text-green-700 dark:text-green-400"
                    : "border border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-400"
                }`}
              >
                {testResult.success ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                ) : (
                  <XCircle className="h-4 w-4 shrink-0" />
                )}
                {testResult.message}
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <Button onClick={() => { setShowAddForm(false); setTestResult(null); setAddProvider(""); setAddApiKey("") }}>
                Cancel
              </Button>
              <Button
                onClick={handleTest}
                disabled={!addProvider || !addApiKey}
                loading={testing}
                icon={testing ? <Loader2 className="h-4 w-4 animate-spin" /> : undefined}
              >
                Test Key
              </Button>
              <Button
                type="primary"
                onClick={handleSave}
                disabled={!addProvider || !addApiKey}
                loading={saving}
                icon={<Key className="h-4 w-4" />}
              >
                Save Key
              </Button>
            </div>
          </div>
        </div>
      )}

      <Table
        dataSource={keys}
        columns={columns}
        rowKey="provider"
        loading={loading}
        pagination={false}
        size="small"
        locale={{
          emptyText: loading
            ? "Loading..."
            : "No provider keys configured. Add a key or configure providers in your server's .env file.",
        }}
      />
    </div>
  )
}

export default ProviderKeysSettings
