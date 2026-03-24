import React from "react"
import {
  Typography,
  Card,
  Button,
  List,
  Tag,
  Space,
  Alert,
  Select,
  InputNumber,
  Switch,
  Segmented,
  Input
} from "antd"
import { useTranslation } from "react-i18next"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { PageShell } from "@/components/Common/PageShell"
import {
  buildLlamacppServerArgs,
  type LlamacppServerArgsInput
} from "@/utils/build-llamacpp-server-args"
import { downloadBlob } from "@/utils/download-blob"
import { parseGgufModelMetadata } from "@/utils/gguf-model-metadata"
import { StatusBanner } from "./StatusBanner"
import { CollapsibleSection } from "./CollapsibleSection"
import { ServerArgsEditor } from "./ServerArgsEditor"
import {
  deriveAdminGuardFromError,
  sanitizeAdminErrorMessage
} from "./admin-error-utils"

const { Title, Text } = Typography
const { TextArea } = Input

type LlamacppStatus = {
  backend?: string
  model?: string
  state?: string
  status?: string
  port?: number
  [key: string]: any
}

const CONTEXT_PRESETS = [
  { label: "2K", value: 2048 },
  { label: "4K", value: 4096 },
  { label: "8K", value: 8192 },
  { label: "16K", value: 16384 },
  { label: "32K", value: 32768 },
  { label: "64K", value: 65536 },
  { label: "128K", value: 131072 }
]

const CACHE_TYPE_OPTIONS = [
  "f16",
  "f32",
  "bf16",
  "q8_0",
  "q4_0",
  "q4_1",
  "iq4_nl",
  "q5_0",
  "q5_1"
]

const NUMA_OPTIONS = [
  { label: "Off", value: "off" },
  { label: "Auto", value: "on" },
  { label: "distribute", value: "distribute" },
  { label: "isolate", value: "isolate" },
  { label: "numactl", value: "numactl" }
] as const

type NumaSelectValue = (typeof NUMA_OPTIONS)[number]["value"]

const DEFAULT_LLAMACPP_SETTINGS: LlamacppServerArgsInput = {
  contextSize: 4096,
  gpuLayers: 0,
  cacheType: "f16",
  splitMode: "layer",
  rowSplit: false,
  mlock: false,
  noMmap: false,
  noKvOffload: false,
  streamingLlm: false,
  cpuMoe: false,
  mmprojAuto: true,
  mmprojOffload: true,
  flashAttn: "auto",
  customArgs: {}
}

const LLAMACPP_PRESET_FORMAT_VERSION = 1
const LLAMACPP_PRESET_TYPE = "tldw_llamacpp_settings_preset"

interface LlamacppSettingsPresetV1 {
  type: typeof LLAMACPP_PRESET_TYPE
  version: typeof LLAMACPP_PRESET_FORMAT_VERSION
  createdAt: string
  settings: LlamacppServerArgsInput
}

const isRecord = (value: unknown): value is Record<string, any> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const coerceImportedSettings = (input: unknown): LlamacppServerArgsInput | null => {
  if (!isRecord(input)) return null

  const maybePreset = input as Partial<LlamacppSettingsPresetV1>
  const source = isRecord(maybePreset.settings) ? maybePreset.settings : input
  if (!isRecord(source)) return null

  const merged = {
    ...DEFAULT_LLAMACPP_SETTINGS,
    ...source
  } as LlamacppServerArgsInput

  if (typeof merged.contextSize !== "number" || !Number.isFinite(merged.contextSize)) {
    return null
  }
  if (typeof merged.gpuLayers !== "number" || !Number.isFinite(merged.gpuLayers)) {
    return null
  }

  if (merged.splitMode && !["none", "layer", "row"].includes(merged.splitMode)) {
    merged.splitMode = "layer"
  }
  if (merged.flashAttn && !["auto", "on", "off"].includes(merged.flashAttn)) {
    merged.flashAttn = "auto"
  }
  if (
    merged.numa !== undefined &&
    merged.numa !== true &&
    merged.numa !== false &&
    !["distribute", "isolate", "numactl"].includes(String(merged.numa))
  ) {
    merged.numa = undefined
  }
  if (!isRecord(merged.customArgs)) {
    merged.customArgs = {}
  }

  return merged
}

export const LlamacppAdminPage: React.FC = () => {
  const { t } = useTranslation(["option", "settings", "common"])
  const initialLoadRef = React.useRef(false)

  // Status state
  const [status, setStatus] = React.useState<LlamacppStatus | null>(null)
  const [loadingStatus, setLoadingStatus] = React.useState(false)
  const [statusError, setStatusError] = React.useState<string | null>(null)

  // Models state
  const [models, setModels] = React.useState<string[]>([])
  const [loadingModels, setLoadingModels] = React.useState(false)
  const [selectedModel, setSelectedModel] = React.useState<string | undefined>()
  const presetFileInputRef = React.useRef<HTMLInputElement | null>(null)

  // Structured server args state
  const [settings, setSettings] = React.useState<LlamacppServerArgsInput>(DEFAULT_LLAMACPP_SETTINGS)
  const [presetNotice, setPresetNotice] = React.useState<string | null>(null)

  // Action state
  const [actionLoading, setActionLoading] = React.useState(false)

  // Admin guard
  const [adminGuard, setAdminGuard] = React.useState<"forbidden" | "notFound" | null>(null)

  const markAdminGuardFromError = (err: any) => {
    const guardState = deriveAdminGuardFromError(err)
    if (guardState) {
      setAdminGuard(guardState)
    }
  }

  function updateSetting<K extends keyof LlamacppServerArgsInput>(
    key: K,
    value: LlamacppServerArgsInput[K]
  ) {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }

  const loadStatus = React.useCallback(async () => {
    try {
      setLoadingStatus(true)
      setStatusError(null)
      const data = await tldwClient.getLlamacppStatus()
      setStatus(data as LlamacppStatus)
    } catch (e: any) {
      setStatusError(
        sanitizeAdminErrorMessage(e, "Failed to load Llama.cpp status.")
      )
      markAdminGuardFromError(e)
    } finally {
      setLoadingStatus(false)
    }
  }, [])

  const loadModels = React.useCallback(async () => {
    try {
      setLoadingModels(true)
      const res = await tldwClient.listLlamacppModels()
      const list = Array.isArray(res?.available_models)
        ? (res.available_models as string[])
        : []
      setModels(list)
      if (list.length > 0) {
        setSelectedModel((current) => current ?? list[0])
      } else {
        setSelectedModel(undefined)
      }
    } catch (e: any) {
      setModels([])
      setSelectedModel(undefined)
      setStatusError(
        sanitizeAdminErrorMessage(e, "Failed to load available Llama.cpp models.")
      )
      markAdminGuardFromError(e)
    } finally {
      setLoadingModels(false)
    }
  }, [])

  React.useEffect(() => {
    if (initialLoadRef.current) return
    initialLoadRef.current = true

    const init = async () => {
      await Promise.all([loadStatus(), loadModels()])
    }
    void init()
  }, [loadModels, loadStatus])

  const handleStart = async () => {
    if (!selectedModel) return
    try {
      setActionLoading(true)
      const serverArgs = buildLlamacppServerArgs(settings)
      await tldwClient.startLlamacppServer(selectedModel, serverArgs)
      await loadStatus()
    } catch (e: any) {
      setStatusError(
        sanitizeAdminErrorMessage(e, "Failed to start Llama.cpp server.")
      )
      markAdminGuardFromError(e)
    } finally {
      setActionLoading(false)
    }
  }

  const handleStartWithDefaults = async () => {
    if (!selectedModel) return
    try {
      setActionLoading(true)
      await tldwClient.startLlamacppServer(selectedModel)
      await loadStatus()
    } catch (e: any) {
      setStatusError(
        sanitizeAdminErrorMessage(e, "Failed to start Llama.cpp server.")
      )
      markAdminGuardFromError(e)
    } finally {
      setActionLoading(false)
    }
  }

  const handleStop = async () => {
    try {
      setActionLoading(true)
      await tldwClient.stopLlamacppServer()
      await loadStatus()
    } catch (e: any) {
      setStatusError(
        sanitizeAdminErrorMessage(e, "Failed to stop Llama.cpp server.")
      )
      markAdminGuardFromError(e)
    } finally {
      setActionLoading(false)
    }
  }

  const handleExportPreset = () => {
    const payload: LlamacppSettingsPresetV1 = {
      type: LLAMACPP_PRESET_TYPE,
      version: LLAMACPP_PRESET_FORMAT_VERSION,
      createdAt: new Date().toISOString(),
      settings
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json"
    })
    const date = new Date().toISOString().slice(0, 10)
    downloadBlob(blob, `llamacpp-settings-preset-${date}.json`)
    setPresetNotice(
      t("settings:admin.llamacppPresetExported", "Exported Llama.cpp settings preset.")
    )
  }

  const handleOpenImportPreset = () => {
    presetFileInputRef.current?.click()
  }

  const handleImportPreset = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return

    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      const importedSettings = coerceImportedSettings(parsed)
      if (!importedSettings) {
        throw new Error("Invalid Llama.cpp preset format.")
      }
      setSettings(importedSettings)
      setStatusError(null)
      setPresetNotice(
        t(
          "settings:admin.llamacppPresetImported",
          `Imported preset from ${file.name}.`
        )
      )
    } catch (e: any) {
      setPresetNotice(null)
      setStatusError(
        sanitizeAdminErrorMessage(
          e,
          t(
            "settings:admin.llamacppPresetImportFailed",
            "Failed to import preset."
          )
        )
      )
    }
  }

  const effectiveState =
    status?.state || status?.status || status?.backend || "unknown"
  const isRunning = effectiveState === "running" || effectiveState === "online"
  const statusUnavailable = !status && Boolean(statusError)
  const modelsWithMeta = React.useMemo(
    () => models.map((model) => ({ model, meta: parseGgufModelMetadata(model) })),
    [models]
  )

  const numaValue: NumaSelectValue =
    settings.numa === undefined || settings.numa === false
      ? "off"
      : settings.numa === true
        ? "on"
        : settings.numa

  return (
    <PageShell>
      <Space orientation="vertical" size="large" className="w-full py-6">
        {adminGuard && (
          <Alert
            type="warning"
            showIcon
            title={
              adminGuard === "forbidden"
                ? t("settings:admin.adminGuardForbiddenTitle", "Admin access required")
                : t("settings:admin.adminGuardNotFoundTitle", "Admin APIs not available")
            }
            description={
              <span>
                {adminGuard === "forbidden"
                  ? t(
                      "settings:admin.adminGuardForbiddenBody",
                      "Sign in as an admin user on your tldw server to access these controls."
                    )
                  : t(
                      "settings:admin.adminGuardNotFoundBody",
                      "This tldw server does not expose the admin endpoints."
                    )}{" "}
                <a
                  href="https://github.com/rmusser01/tldw_server#documentation--resources"
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("settings:admin.adminGuardLearnMore", "Learn more")}
                </a>
              </span>
            }
          />
        )}

        <div>
          <Title level={2}>
            {t("option:header.adminLlamacpp", "Llama.cpp Admin")}
          </Title>
          <Text type="secondary">
            {t(
              "settings:admin.llamacppIntro",
              "Manage the Llama.cpp inference server with structured settings similar to llama-server WebUI controls."
            )}
          </Text>
        </div>

        {!adminGuard && (
          <>
            <StatusBanner
              state={effectiveState}
              loading={loadingStatus}
              error={statusError}
              items={[
                { label: t("settings:admin.llamacppActiveModel", "Model"), value: status?.model, code: true },
                { label: t("settings:admin.llamacppPort", "Port"), value: status?.port }
              ]}
              onRefresh={loadStatus}
              quickAction={
                isRunning
                  ? {
                      label: t("settings:admin.llamacppStop", "Stop"),
                      onClick: handleStop,
                      loading: actionLoading,
                      danger: true
                    }
                  : undefined
              }
            />

            <Card
              title={t("settings:admin.llamacppLoadTitle", "Load Model")}
              loading={loadingModels}
            >
              <Space orientation="vertical" size="middle" className="w-full">
                <div>
                  <Text strong className="mb-2 block">
                    {t("settings:admin.llamacppSelectModel", "Select model")}
                  </Text>
                  <Select
                    value={selectedModel}
                    onChange={setSelectedModel}
                    options={models.map((m) => ({ label: m, value: m }))}
                    placeholder={t("settings:admin.llamacppSelectModelPlaceholder", "Choose a GGUF model...")}
                    className="w-full"
                    showSearch
                    filterOption={(input, option) =>
                      (option?.label ?? "").toLowerCase().includes(input.toLowerCase())
                    }
                  />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    onClick={handleExportPreset}
                    disabled={actionLoading}
                  >
                    {t("settings:admin.llamacppExportPreset", "Export preset")}
                  </Button>
                  <Button
                    onClick={handleOpenImportPreset}
                    disabled={actionLoading}
                  >
                    {t("settings:admin.llamacppImportPreset", "Import preset")}
                  </Button>
                  <input
                    ref={presetFileInputRef}
                    type="file"
                    accept=".json,application/json"
                    onChange={handleImportPreset}
                    className="hidden"
                    aria-label={t("settings:admin.llamacppImportPreset", "Import preset")}
                  />
                </div>

                {presetNotice && (
                  <Alert
                    type="success"
                    showIcon
                    title={presetNotice}
                  />
                )}

                <div className="rounded-lg border border-border p-4">
                  <Text strong className="mb-3 block">
                    {t("settings:admin.llamacppMainOptions", "Main Options")}
                  </Text>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <Text>{t("settings:admin.llamacppContextSize", "Context size")}</Text>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <Segmented
                          size="small"
                          options={CONTEXT_PRESETS}
                          value={settings.contextSize}
                          onChange={(value) => updateSetting("contextSize", value as number)}
                        />
                        <InputNumber
                          size="small"
                          value={settings.contextSize}
                          onChange={(value) => updateSetting("contextSize", value ?? 4096)}
                          min={256}
                          max={131072}
                          step={256}
                          style={{ width: 120 }}
                        />
                      </div>
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppGpuLayers", "GPU layers")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.gpuLayers}
                        onChange={(value) => updateSetting("gpuLayers", value ?? 0)}
                        min={-1}
                        max={300}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                      <Text type="secondary" className="text-xs">
                        {t("settings:admin.llamacppGpuLayersHint", "0 = CPU only, -1 = all layers")}
                      </Text>
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppCacheType", "Cache type (K/V)")}</Text>
                      <Select
                        size="small"
                        value={settings.cacheType}
                        onChange={(value) => updateSetting("cacheType", value)}
                        options={CACHE_TYPE_OPTIONS.map((value) => ({ label: value, value }))}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppSplitMode", "Split mode")}</Text>
                      <Select
                        size="small"
                        value={settings.splitMode ?? "layer"}
                        onChange={(value) => updateSetting("splitMode", value)}
                        options={[
                          { label: "none", value: "none" },
                          { label: "layer", value: "layer" },
                          { label: "row", value: "row" }
                        ]}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                      <div className="mt-2 flex items-center justify-between">
                        <Text type="secondary" className="text-xs">
                          {t("settings:admin.llamacppRowSplit", "Force row split")}
                        </Text>
                        <Switch
                          size="small"
                          checked={Boolean(settings.rowSplit)}
                          onChange={(checked) => updateSetting("rowSplit", checked)}
                        />
                      </div>
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppRopeFreqBase", "RoPE freq base")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.ropeFreqBase}
                        onChange={(value) => updateSetting("ropeFreqBase", value ?? undefined)}
                        min={0}
                        step={1000}
                        placeholder="auto"
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppRopeFreqScale", "RoPE freq scale")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.ropeFreqScale}
                        onChange={(value) => updateSetting("ropeFreqScale", value ?? undefined)}
                        min={0}
                        step={0.01}
                        placeholder="auto"
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppCompressPosEmb", "compress_pos_emb")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.compressPosEmb}
                        onChange={(value) => updateSetting("compressPosEmb", value ?? undefined)}
                        min={0.001}
                        step={0.01}
                        placeholder="optional"
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppFlashAttn", "Flash attention")}</Text>
                      <Select
                        size="small"
                        value={settings.flashAttn ?? "auto"}
                        onChange={(value) => updateSetting("flashAttn", value)}
                        options={[
                          { label: "auto", value: "auto" },
                          { label: "on", value: "on" },
                          { label: "off", value: "off" }
                        ]}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppCpuMoe", "cpu-moe")}</Text>
                      <Switch
                        size="small"
                        checked={Boolean(settings.cpuMoe)}
                        onChange={(checked) => updateSetting("cpuMoe", checked)}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppNCpuMoe", "n-cpu-moe")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.nCpuMoe}
                        onChange={(value) => updateSetting("nCpuMoe", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppStreamingLlm", "streaming-llm")}</Text>
                      <Switch
                        size="small"
                        checked={Boolean(settings.streamingLlm)}
                        onChange={(checked) => updateSetting("streamingLlm", checked)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppNoKvOffload", "no-kv-offload")}</Text>
                      <Switch
                        size="small"
                        checked={Boolean(settings.noKvOffload)}
                        onChange={(checked) => updateSetting("noKvOffload", checked)}
                      />
                    </div>
                  </div>
                </div>

                <CollapsibleSection
                  title={t("settings:admin.llamacppOtherOptions", "Other Options")}
                  description={t("settings:admin.llamacppOtherOptionsDesc", "CPU, batching, memory, and extra flags")}
                >
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <Text>{t("settings:admin.llamacppThreads", "Threads")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.threads}
                        onChange={(value) => updateSetting("threads", value ?? undefined)}
                        min={1}
                        max={256}
                        placeholder="auto"
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppThreadsBatch", "threads_batch")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.threadsBatch}
                        onChange={(value) => updateSetting("threadsBatch", value ?? undefined)}
                        min={1}
                        max={256}
                        placeholder="auto"
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppBatchSize", "batch_size")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.batchSize}
                        onChange={(value) => updateSetting("batchSize", value ?? undefined)}
                        min={1}
                        max={8192}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppUbatchSize", "ubatch_size")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.ubatchSize}
                        onChange={(value) => updateSetting("ubatchSize", value ?? undefined)}
                        min={1}
                        max={8192}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppMainGpu", "main-gpu")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.mainGpu}
                        onChange={(value) => updateSetting("mainGpu", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppTensorSplit", "tensor_split")}</Text>
                      <Input
                        size="small"
                        value={settings.tensorSplit}
                        onChange={(e) => updateSetting("tensorSplit", e.target.value || undefined)}
                        placeholder="e.g. 38,62"
                        style={{ marginTop: 4 }}
                      />
                    </div>

                    <div>
                      <Text>{t("settings:admin.llamacppNuma", "numa")}</Text>
                      <Select
                        size="small"
                        value={numaValue}
                        onChange={(value: NumaSelectValue) => {
                          if (value === "off") {
                            updateSetting("numa", undefined)
                          } else if (value === "on") {
                            updateSetting("numa", true)
                          } else {
                            updateSetting("numa", value)
                          }
                        }}
                        options={NUMA_OPTIONS.map((entry) => ({ label: entry.label, value: entry.value }))}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppNoMmap", "no-mmap")}</Text>
                      <Switch
                        size="small"
                        checked={Boolean(settings.noMmap)}
                        onChange={(checked) => updateSetting("noMmap", checked)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppMlock", "mlock")}</Text>
                      <Switch
                        size="small"
                        checked={Boolean(settings.mlock)}
                        onChange={(checked) => updateSetting("mlock", checked)}
                      />
                    </div>

                    <div className="md:col-span-2">
                      <Text>{t("settings:admin.llamacppExtraFlags", "extra-flags")}</Text>
                      <TextArea
                        value={settings.extraFlags}
                        onChange={(e) => updateSetting("extraFlags", e.target.value || undefined)}
                        placeholder="flag, key=value, n-cpu-moe=27"
                        autoSize={{ minRows: 2, maxRows: 6 }}
                        style={{ marginTop: 4 }}
                      />
                      <Text type="secondary" className="text-xs">
                        {t(
                          "settings:admin.llamacppExtraFlagsHint",
                          "Comma or newline separated; these are parsed and merged without requiring JSON."
                        )}
                      </Text>
                    </div>
                  </div>
                </CollapsibleSection>

                <CollapsibleSection
                  title={t("settings:admin.llamacppMultimodal", "Multimodal (vision)")}
                  description={t("settings:admin.llamacppMultimodalDesc", "mmproj and image token controls")}
                >
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <Text>{t("settings:admin.llamacppMmproj", "mmproj file")}</Text>
                      <Input
                        size="small"
                        value={settings.mmproj}
                        onChange={(e) => updateSetting("mmproj", e.target.value || undefined)}
                        placeholder="/absolute/path/to/mmproj.gguf"
                        style={{ marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppMmprojUrl", "mmproj URL")}</Text>
                      <Input
                        size="small"
                        value={settings.mmprojUrl}
                        onChange={(e) => updateSetting("mmprojUrl", e.target.value || undefined)}
                        placeholder="https://..."
                        style={{ marginTop: 4 }}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppMmprojAuto", "mmproj auto")}</Text>
                      <Switch
                        size="small"
                        checked={settings.mmprojAuto !== false}
                        onChange={(checked) => updateSetting("mmprojAuto", checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppMmprojOffload", "mmproj offload")}</Text>
                      <Switch
                        size="small"
                        checked={settings.mmprojOffload !== false}
                        onChange={(checked) => updateSetting("mmprojOffload", checked)}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppImageMinTokens", "image-min-tokens")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.imageMinTokens}
                        onChange={(value) => updateSetting("imageMinTokens", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppImageMaxTokens", "image-max-tokens")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.imageMaxTokens}
                        onChange={(value) => updateSetting("imageMaxTokens", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                  </div>
                </CollapsibleSection>

                <CollapsibleSection
                  title={t("settings:admin.llamacppSpeculative", "Speculative decoding")}
                  description={t("settings:admin.llamacppSpeculativeDesc", "Draft model and draft token controls")}
                >
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="md:col-span-2">
                      <Text>{t("settings:admin.llamacppDraftModel", "model-draft")}</Text>
                      <Input
                        size="small"
                        value={settings.draftModel}
                        onChange={(e) => updateSetting("draftModel", e.target.value || undefined)}
                        placeholder="/absolute/path/to/draft-model.gguf"
                        style={{ marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppDraftMax", "draft-max")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.draftMax}
                        onChange={(value) => updateSetting("draftMax", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppDraftMin", "draft-min")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.draftMin}
                        onChange={(value) => updateSetting("draftMin", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppDraftPMin", "draft-p-min")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.draftPMin}
                        onChange={(value) => updateSetting("draftPMin", value ?? undefined)}
                        min={0}
                        max={1}
                        step={0.01}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppCtxSizeDraft", "ctx-size-draft")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.ctxSizeDraft}
                        onChange={(value) => updateSetting("ctxSizeDraft", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppGpuLayersDraft", "gpu-layers-draft")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.gpuLayersDraft}
                        onChange={(value) => updateSetting("gpuLayersDraft", value ?? undefined)}
                        min={-1}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <Text>{t("settings:admin.llamacppCpuMoeDraft", "cpu-moe-draft")}</Text>
                      <Switch
                        size="small"
                        checked={Boolean(settings.cpuMoeDraft)}
                        onChange={(checked) => updateSetting("cpuMoeDraft", checked)}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppNCpuMoeDraft", "n-cpu-moe-draft")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.nCpuMoeDraft}
                        onChange={(value) => updateSetting("nCpuMoeDraft", value ?? undefined)}
                        min={0}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                  </div>
                </CollapsibleSection>

                <CollapsibleSection
                  title={t("settings:admin.llamacppNetworkAndRuntime", "Network & Runtime")}
                  description={t("settings:admin.llamacppNetworkAndRuntimeDesc", "Host/port and runtime overrides")}
                >
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <Text>{t("settings:admin.llamacppHost", "host")}</Text>
                      <Input
                        size="small"
                        value={settings.host}
                        onChange={(e) => updateSetting("host", e.target.value || undefined)}
                        placeholder="127.0.0.1"
                        style={{ marginTop: 4 }}
                      />
                    </div>
                    <div>
                      <Text>{t("settings:admin.llamacppPort", "port")}</Text>
                      <InputNumber
                        size="small"
                        value={settings.port}
                        onChange={(value) => updateSetting("port", value ?? undefined)}
                        min={1}
                        max={65535}
                        style={{ width: "100%", marginTop: 4 }}
                      />
                    </div>
                  </div>
                </CollapsibleSection>

                <CollapsibleSection
                  title={t("settings:admin.llamacppRawOverrides", "Raw argument overrides")}
                  description={t("settings:admin.llamacppRawOverridesDesc", "Optional key-value overrides on top of structured controls")}
                >
                  <ServerArgsEditor
                    value={settings.customArgs || {}}
                    onChange={(value) => updateSetting("customArgs", value)}
                    placeholder={t("settings:admin.llamacppCustomArgsPlaceholder", "No overrides. Structured controls already cover common options.")}
                  />
                </CollapsibleSection>

                <Space className="mt-2">
                  <Button
                    type="primary"
                    onClick={handleStart}
                    loading={actionLoading}
                    disabled={
                      !selectedModel ||
                      isRunning ||
                      loadingModels ||
                      statusUnavailable
                    }
                  >
                    {t("settings:admin.llamacppStart", "Start Server")}
                  </Button>
                  <Button
                    onClick={handleStartWithDefaults}
                    loading={actionLoading}
                    disabled={
                      !selectedModel ||
                      isRunning ||
                      loadingModels ||
                      statusUnavailable
                    }
                  >
                    {t("settings:admin.llamacppStartDefaults", "Start with Defaults")}
                  </Button>
                </Space>

                {statusUnavailable && (
                  <Alert
                    type="warning"
                    title={t(
                      "settings:admin.llamacppUnavailableHint",
                      "Llama.cpp controls are temporarily unavailable until status checks succeed."
                    )}
                    showIcon
                  />
                )}

                {isRunning && (
                  <Alert
                    type="info"
                    title={t("settings:admin.llamacppAlreadyRunning", "Server is already running. Stop it first to start with new settings.")}
                    showIcon
                  />
                )}
              </Space>
            </Card>

            <CollapsibleSection
              title={t("settings:admin.llamacppModelsTitle", "Available Models")}
              description={t("settings:admin.llamacppModelsDesc", `${models.length} GGUF model(s) detected`)}
            >
              {modelsWithMeta.length > 0 ? (
                <List
                  size="small"
                  bordered
                  dataSource={modelsWithMeta}
                  renderItem={({ model, meta }) => (
                    <List.Item
                      actions={[
                        <Button
                          key="select"
                          size="small"
                          type="link"
                          onClick={() => setSelectedModel(model)}
                          disabled={selectedModel === model}
                        >
                          {selectedModel === model
                            ? t("common:selected", "Selected")
                            : t("common:select", "Select")}
                        </Button>
                      ]}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Text code>{model}</Text>
                        {meta.parameterCount && (
                          <Tag color="geekblue">{meta.parameterCount}</Tag>
                        )}
                        {meta.quantization && (
                          <Tag color="purple">{meta.quantization}</Tag>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary">
                  {t(
                    "settings:admin.llamacppModelsEmpty",
                    "No local GGUF models detected. Configure your Llama.cpp models directory on the server."
                  )}
                </Text>
              )}
            </CollapsibleSection>
          </>
        )}
      </Space>
    </PageShell>
  )
}

export default LlamacppAdminPage
