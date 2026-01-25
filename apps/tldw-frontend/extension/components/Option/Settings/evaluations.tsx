import React from "react"
import { Button, Card, Form, Input, Select, Space, Alert, Skeleton } from "antd"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"

import { useServerOnline } from "@/hooks/useServerOnline"
import { getRateLimits } from "@/services/evaluations"
import {
  getEvaluationDefaults,
  setEvaluationDefaults,
  setDefaultSpecForType
} from "@/services/evaluations-settings"

const EVAL_TYPES = [
  "model_graded",
  "response_quality",
  "rag",
  "rag_pipeline",
  "geval",
  "exact_match",
  "includes",
  "fuzzy_match",
  "proposition_extraction",
  "qa3",
  "label_choice",
  "nli_factcheck",
  "ocr"
]

type EvaluationDefaultsFormValues = {
  defaultEvalType: string
  defaultTargetModel: string
  defaultRunConfig?: string
  defaultDatasetId?: string
  specJson?: string
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

const getErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : typeof error === "string" ? error : ""

export const EvaluationsSettings = () => {
  const { t } = useTranslation(["settings", "common"])
  const isOnline = useServerOnline()

  const [form] = Form.useForm()
  const [specType, setSpecType] = React.useState<string>("response_quality")
  const defaultsAppliedRef = React.useRef(false)
  const [testResult, setTestResult] = React.useState<
    | null
    | { ok: boolean; message: string; details?: string; rate?: string }
  >(null)

  const { data: defaultsResp, isLoading: defaultsLoading } = useQuery({
    queryKey: ["evaluations", "defaults"],
    queryFn: () => getEvaluationDefaults()
  })

  React.useEffect(() => {
    if (!defaultsResp || defaultsAppliedRef.current) return
    defaultsAppliedRef.current = true
    const nextSpecType = defaultsResp.defaultEvalType || "response_quality"
    form.setFieldsValue({
      defaultEvalType: defaultsResp.defaultEvalType,
      defaultTargetModel: defaultsResp.defaultTargetModel,
      defaultRunConfig: defaultsResp.defaultRunConfig,
      defaultDatasetId: defaultsResp.defaultDatasetId || undefined,
      specJson:
        defaultsResp.defaultSpecByType?.[nextSpecType] ||
        defaultsResp.defaultSpecByType?.[defaultsResp.defaultEvalType || ""] ||
        ""
    })
    setSpecType(nextSpecType)
  }, [defaultsResp, form])

  const { mutateAsync: saveDefaults, isPending: saving } = useMutation({
    mutationFn: async (values: EvaluationDefaultsFormValues) => {
      const updates = {
        defaultEvalType: values.defaultEvalType,
        defaultTargetModel: values.defaultTargetModel,
        defaultRunConfig: values.defaultRunConfig,
        defaultDatasetId: values.defaultDatasetId || null
      }
      await setEvaluationDefaults(updates)
      if (values.specJson) {
        await setDefaultSpecForType(specType, values.specJson)
      }
      return await getEvaluationDefaults()
    },
    onSuccess: (next) => {
      form.setFieldsValue({
        defaultEvalType: next.defaultEvalType,
        defaultTargetModel: next.defaultTargetModel,
        defaultRunConfig: next.defaultRunConfig,
        defaultDatasetId: next.defaultDatasetId || undefined,
        specJson: next.defaultSpecByType?.[specType] || ""
      })
    }
  })

  const { mutateAsync: testEvalApi, isPending: testing } = useMutation({
    mutationFn: async () => getRateLimits(),
    onSuccess: (resp) => {
      if (resp?.ok && resp.data) {
        const d = isRecord(resp.data) ? resp.data : {}
        const usage = isRecord(d.usage) ? d.usage : null
        const limits = isRecord(d.limits) ? d.limits : null
        const evaluationsToday =
          usage && typeof usage.evaluations_today === "number"
            ? usage.evaluations_today
            : 0
        const evaluationsPerDay =
          limits && typeof limits.evaluations_per_day === "number"
            ? limits.evaluations_per_day
            : "?"
        const tier = typeof d.tier === "string" ? d.tier : ""
        setTestResult({
          ok: true,
          message:
            t("settings:evaluationsSettings.testOk", {
              defaultValue: "Evaluations API reachable"
            }) as string,
          rate: `${tier} · ${evaluationsToday}/${evaluationsPerDay} today`
        })
      } else {
        setTestResult({
          ok: false,
          message:
            resp?.error ||
            (t("settings:evaluationsSettings.testFail", {
              defaultValue: "Unable to reach Evaluations API"
            }) as string)
        })
      }
    },
    onError: (error: unknown) => {
      setTestResult({
        ok: false,
        message:
          getErrorMessage(error) ||
          (t("settings:evaluationsSettings.testFail", {
            defaultValue: "Unable to reach Evaluations API"
          }) as string)
      })
    }
  })

  const defaults = defaultsResp || {}

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold leading-7 text-text">
          {t("settings:evaluationsSettings.title", {
            defaultValue: "Evaluations defaults"
          })}
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          {t("settings:evaluationsSettings.subtitle", {
            defaultValue:
              "Configure default eval type, target model, and spec snippets used by the Evaluations playground."
          })}
        </p>
      </div>

      {!isOnline && (
        <Alert
          type="warning"
          showIcon
          message={t("settings:evaluationsSettings.offline", {
            defaultValue: "Connect to your tldw server to test Evaluations."
          })}
        />
      )}

      {defaultsLoading && <Skeleton active paragraph={{ rows: 6 }} />}

      {!defaultsLoading && <Card>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            defaultEvalType: defaults.defaultEvalType || "response_quality",
            defaultTargetModel: defaults.defaultTargetModel || "gpt-3.5-turbo",
            defaultRunConfig: defaults.defaultRunConfig,
            defaultDatasetId: defaults.defaultDatasetId || undefined,
            specJson:
              defaults.defaultSpecByType?.[specType] ||
              defaults.defaultSpecByType?.[
                defaults.defaultEvalType || "response_quality"
              ] ||
              ""
          }}>
          <Form.Item
            label={t("settings:evaluationsSettings.defaultType", {
              defaultValue: "Default evaluation type"
            })}
            name="defaultEvalType"
            rules={[{ required: true }]}>
            <Select
              loading={defaultsLoading}
              options={EVAL_TYPES.map((value) => ({ value, label: value }))}
              onChange={(val) => {
                setSpecType(val)
                const spec =
                  defaults.defaultSpecByType?.[val] ||
                  form.getFieldValue("specJson") ||
                  ""
                form.setFieldsValue({ specJson: spec })
              }}
            />
          </Form.Item>

          <Form.Item
            label={t("settings:evaluationsSettings.defaultModel", {
              defaultValue: "Default target model"
            })}
            name="defaultTargetModel"
            rules={[{ required: true }]}>
            <Input placeholder="gpt-3.5-turbo" />
          </Form.Item>

          <Form.Item
            label={t("settings:evaluationsSettings.defaultRunConfig", {
              defaultValue: "Default run config (JSON)"
            })}
            name="defaultRunConfig">
            <Input.TextArea rows={3} />
          </Form.Item>

          <Form.Item
            label={t("settings:evaluationsSettings.defaultDataset", {
              defaultValue: "Default dataset id (optional)"
            })}
            name="defaultDatasetId">
            <Input placeholder="dataset_123 (optional)" />
          </Form.Item>

          <Form.Item
            label={t("settings:evaluationsSettings.specForType", {
              defaultValue: "Spec preset for selected type"
            })}
            name="specJson">
            <Input.TextArea
              rows={6}
              placeholder='{"metrics":["coherence"]}'
            />
          </Form.Item>

          <Space size="small">
            <Button
              type="primary"
              loading={saving}
              onClick={() =>
                void form.validateFields().then((vals) => saveDefaults(vals))
              }>
              {t("common:save", { defaultValue: "Save" })}
            </Button>
            <Button
              type="default"
              loading={testing}
              onClick={() => void testEvalApi()}
              disabled={!isOnline}>
              {t("settings:evaluationsSettings.testCta", {
                defaultValue: "Test Evaluations API"
              })}
            </Button>
          </Space>
          {testResult && (
            <Alert
              className="mt-3"
              type={testResult.ok ? "success" : "error"}
              message={testResult.message}
              description={testResult.rate || testResult.details}
              showIcon
            />
          )}
        </Form>
      </Card>}
    </div>
  )
}
