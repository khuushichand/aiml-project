import React from "react"
import { Card, Progress, Steps, Tag, Typography } from "antd"

const { Text } = Typography

export type TtsJobProgressStep = {
  key: string
  label: string
  description?: string
}

export type TtsJobProgressMetric = {
  label: string
  value: string
}

type TtsJobProgressProps = {
  title?: string
  steps: TtsJobProgressStep[]
  currentStep: number
  percent?: number | null
  message?: string | null
  status?: "idle" | "running" | "success" | "error"
  etaSeconds?: number | null
  metrics?: TtsJobProgressMetric[]
}

const formatEta = (value?: number | null) => {
  if (!value || value <= 0) return "—"
  const total = Math.round(value)
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  if (minutes <= 0) return `${seconds}s`
  return `${minutes}m ${seconds}s`
}

export const TtsJobProgress: React.FC<TtsJobProgressProps> = ({
  title = "Long-form TTS progress",
  steps,
  currentStep,
  percent,
  message,
  status = "running",
  etaSeconds,
  metrics = []
}) => {
  const progressPercent = Math.max(0, Math.min(100, Math.round(percent ?? 0)))
  const progressStatus =
    status === "error" ? "exception" : status === "success" ? "success" : "active"

  return (
    <Card size="small" className="bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Text strong className="text-sm">
          {title}
        </Text>
        <Tag color={status === "error" ? "red" : status === "success" ? "green" : "blue"}>
          {status === "error" ? "Issue" : status === "success" ? "Complete" : "Running"}
        </Tag>
      </div>
      <div className="mt-2 space-y-2">
        <Progress percent={progressPercent} status={progressStatus as any} size="small" />
        <Steps
          size="small"
          current={Math.max(0, Math.min(currentStep, steps.length - 1))}
          items={steps.map((step) => ({
            title: step.label,
            description: step.description
          }))}
        />
        <div className="flex flex-wrap gap-3 text-xs text-text-subtle">
          <span>
            ETA: <Text>{formatEta(etaSeconds)}</Text>
          </span>
          {message ? (
            <span>
              Status: <Text>{message.replace(/_/g, " ")}</Text>
            </span>
          ) : null}
          {metrics.map((metric) => (
            <span key={metric.label}>
              {metric.label}: <Text>{metric.value}</Text>
            </span>
          ))}
        </div>
      </div>
    </Card>
  )
}
