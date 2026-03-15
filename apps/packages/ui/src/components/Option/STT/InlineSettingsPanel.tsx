import React, { useCallback, useEffect, useRef, useState } from "react"
import { Button, Input, InputNumber, Select, Switch, Typography } from "antd"
import { useStorage } from "@plasmohq/storage/hook"
import { useTranslation } from "react-i18next"

const { Text } = Typography

export interface SttLocalSettings {
  language: string
  task: string
  responseFormat: string
  temperature: number
  prompt: string
  useSegmentation: boolean
  segK: number
  segMinSegmentSize: number
  segLambdaBalance: number
  segUtteranceExpansionWidth: number
  segEmbeddingsProvider: string
  segEmbeddingsModel: string
}

interface InlineSettingsPanelProps {
  onChange: (settings: SttLocalSettings) => void
}

const TASK_OPTIONS = [
  { label: "Transcribe", value: "transcribe" },
  { label: "Translate", value: "translate" }
]

const FORMAT_OPTIONS = [
  { label: "JSON", value: "json" },
  { label: "Text", value: "text" },
  { label: "SRT", value: "srt" },
  { label: "VTT", value: "vtt" },
  { label: "Verbose JSON", value: "verbose_json" }
]

export const InlineSettingsPanel: React.FC<InlineSettingsPanelProps> = ({
  onChange
}) => {
  const { t } = useTranslation(["playground", "settings"])

  // Read global defaults
  const [globalLanguage] = useStorage("speechToTextLanguage", "en-US")
  const [globalTask] = useStorage("sttTask", "transcribe")
  const [globalFormat] = useStorage("sttResponseFormat", "json")
  const [globalTemperature] = useStorage("sttTemperature", 0)
  const [globalPrompt] = useStorage("sttPrompt", "")
  const [globalUseSegmentation] = useStorage("sttUseSegmentation", false)
  const [globalSegK] = useStorage("sttSegK", 6)
  const [globalSegMinSegmentSize] = useStorage("sttSegMinSegmentSize", 5)
  const [globalSegLambdaBalance] = useStorage("sttSegLambdaBalance", 0.01)
  const [globalSegUtteranceExpansionWidth] = useStorage(
    "sttSegUtteranceExpansionWidth",
    2
  )
  const [globalSegEmbeddingsProvider] = useStorage(
    "sttSegEmbeddingsProvider",
    ""
  )
  const [globalSegEmbeddingsModel] = useStorage("sttSegEmbeddingsModel", "")

  const buildDefaults = useCallback(
    (): SttLocalSettings => ({
      language: globalLanguage,
      task: globalTask,
      responseFormat: globalFormat,
      temperature: globalTemperature,
      prompt: globalPrompt,
      useSegmentation: globalUseSegmentation,
      segK: globalSegK,
      segMinSegmentSize: globalSegMinSegmentSize,
      segLambdaBalance: globalSegLambdaBalance,
      segUtteranceExpansionWidth: globalSegUtteranceExpansionWidth,
      segEmbeddingsProvider: globalSegEmbeddingsProvider,
      segEmbeddingsModel: globalSegEmbeddingsModel
    }),
    [
      globalLanguage,
      globalTask,
      globalFormat,
      globalTemperature,
      globalPrompt,
      globalUseSegmentation,
      globalSegK,
      globalSegMinSegmentSize,
      globalSegLambdaBalance,
      globalSegUtteranceExpansionWidth,
      globalSegEmbeddingsProvider,
      globalSegEmbeddingsModel
    ]
  )

  const [settings, setSettings] = useState<SttLocalSettings>(buildDefaults)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const update = useCallback(
    (patch: Partial<SttLocalSettings>) => {
      setSettings((prev) => {
        const next = { ...prev, ...patch }
        // Defer onChange to avoid calling during render
        queueMicrotask(() => onChangeRef.current(next))
        return next
      })
    },
    []
  )

  // Fire initial onChange once on mount
  const mountedRef = useRef(false)
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true
      onChange(settings)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const resetToDefaults = useCallback(() => {
    const defaults = buildDefaults()
    setSettings(defaults)
    queueMicrotask(() => onChangeRef.current(defaults))
  }, [buildDefaults])

  return (
    <div style={{ padding: "8px 0" }}>
      {/* Main settings grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
          gap: 12
        }}
      >
        <div>
          <label htmlFor="stt-language">
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t("stt.language", "Language")}
            </Text>
          </label>
          <Input
            id="stt-language"
            aria-label="Language"
            size="small"
            value={settings.language}
            onChange={(e) => update({ language: e.target.value })}
          />
        </div>

        <div>
          <label htmlFor="stt-task">
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t("stt.task", "Task")}
            </Text>
          </label>
          <Select
            id="stt-task"
            aria-label="Task"
            size="small"
            style={{ width: "100%" }}
            value={settings.task}
            options={TASK_OPTIONS}
            onChange={(value) => update({ task: value })}
          />
        </div>

        <div>
          <label htmlFor="stt-format">
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t("stt.format", "Format")}
            </Text>
          </label>
          <Select
            id="stt-format"
            aria-label="Format"
            size="small"
            style={{ width: "100%" }}
            value={settings.responseFormat}
            options={FORMAT_OPTIONS}
            onChange={(value) => update({ responseFormat: value })}
          />
        </div>

        <div>
          <label htmlFor="stt-temperature">
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t("stt.temperature", "Temperature")}
            </Text>
          </label>
          <InputNumber
            id="stt-temperature"
            aria-label="Temperature"
            size="small"
            style={{ width: "100%" }}
            min={0}
            max={1}
            step={0.1}
            value={settings.temperature}
            onChange={(value) =>
              update({ temperature: value ?? 0 })
            }
          />
        </div>

        <div>
          <label htmlFor="stt-prompt">
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t("stt.prompt", "Prompt")}
            </Text>
          </label>
          <Input
            id="stt-prompt"
            aria-label="Prompt"
            size="small"
            value={settings.prompt}
            onChange={(e) => update({ prompt: e.target.value })}
          />
        </div>
      </div>

      {/* Segmentation toggle */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
        <Switch
          size="small"
          checked={settings.useSegmentation}
          onChange={(checked) => update({ useSegmentation: checked })}
        />
        <Text>{t("stt.useSegmentation", "Use segmentation")}</Text>
      </div>

      {/* Segmentation params (only when enabled) */}
      {settings.useSegmentation && (
        <div
          style={{
            marginTop: 8,
            paddingLeft: 12,
            borderLeft: "2px solid var(--ant-color-border, #d9d9d9)"
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
              gap: 12
            }}
          >
            <div>
              <label htmlFor="stt-seg-k">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("stt.segK", "K")}
                </Text>
              </label>
              <InputNumber
                id="stt-seg-k"
                aria-label="K"
                size="small"
                style={{ width: "100%" }}
                min={1}
                value={settings.segK}
                onChange={(value) => update({ segK: value ?? 6 })}
              />
            </div>

            <div>
              <label htmlFor="stt-seg-min">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("stt.segMinSegmentSize", "Min segment size")}
                </Text>
              </label>
              <InputNumber
                id="stt-seg-min"
                aria-label="Min segment size"
                size="small"
                style={{ width: "100%" }}
                min={1}
                value={settings.segMinSegmentSize}
                onChange={(value) =>
                  update({ segMinSegmentSize: value ?? 5 })
                }
              />
            </div>

            <div>
              <label htmlFor="stt-seg-lambda">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("stt.segLambdaBalance", "Lambda balance")}
                </Text>
              </label>
              <InputNumber
                id="stt-seg-lambda"
                aria-label="Lambda balance"
                size="small"
                style={{ width: "100%" }}
                min={0}
                max={1}
                step={0.01}
                value={settings.segLambdaBalance}
                onChange={(value) =>
                  update({ segLambdaBalance: value ?? 0.01 })
                }
              />
            </div>

            <div>
              <label htmlFor="stt-seg-expansion">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("stt.segExpansionWidth", "Expansion width")}
                </Text>
              </label>
              <InputNumber
                id="stt-seg-expansion"
                aria-label="Expansion width"
                size="small"
                style={{ width: "100%" }}
                min={0}
                value={settings.segUtteranceExpansionWidth}
                onChange={(value) =>
                  update({ segUtteranceExpansionWidth: value ?? 2 })
                }
              />
            </div>

            <div>
              <label htmlFor="stt-seg-emb-provider">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("stt.segEmbeddingsProvider", "Embeddings provider")}
                </Text>
              </label>
              <Input
                id="stt-seg-emb-provider"
                aria-label="Embeddings provider"
                size="small"
                value={settings.segEmbeddingsProvider}
                onChange={(e) =>
                  update({ segEmbeddingsProvider: e.target.value })
                }
              />
            </div>

            <div>
              <label htmlFor="stt-seg-emb-model">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("stt.segEmbeddingsModel", "Embeddings model")}
                </Text>
              </label>
              <Input
                id="stt-seg-emb-model"
                aria-label="Embeddings model"
                size="small"
                value={settings.segEmbeddingsModel}
                onChange={(e) =>
                  update({ segEmbeddingsModel: e.target.value })
                }
              />
            </div>
          </div>
        </div>
      )}

      {/* Reset button */}
      <div style={{ marginTop: 12 }}>
        <Button size="small" onClick={resetToDefaults}>
          {t("stt.resetToDefaults", "Reset to defaults")}
        </Button>
      </div>
    </div>
  )
}
