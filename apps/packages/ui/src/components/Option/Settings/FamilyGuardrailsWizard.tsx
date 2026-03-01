import React, { useMemo, useState } from "react"
import {
  Alert,
  Button,
  Card,
  Divider,
  Form,
  Input,
  Radio,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
  message
} from "antd"
import { DeleteOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons"

import {
  addHouseholdMemberDraft,
  createHouseholdDraft,
  getActivationSummary,
  saveGuardrailPlanDraft,
  saveRelationshipDraft,
  type ActivationSummary,
  type GuardrailPlanDraft,
  type HouseholdDraft,
  type HouseholdMemberDraft,
  type MemberRole,
  type RelationshipDraft,
  type SaveGuardrailPlanDraftBody,
  updateHouseholdDraft
} from "@/services/family-wizard"

const { Title, Text, Paragraph } = Typography

type Mode = "family" | "institutional"
type TemplateId = "default-child-safe" | "teen-balanced" | "school-research"

type MemberInput = {
  key: string
  displayName: string
  userId: string
  email: string
}

type OverrideInput = {
  action: "block" | "redact" | "warn" | "notify"
  notify_context: "topic_only" | "snippet" | "full_message"
}

export interface FamilyGuardrailsWizardProps {
  initialStep?: number
  initialDraft?: HouseholdDraft | null
}

const STEP_TITLES = [
  "Household Basics",
  "Add Guardians",
  "Add Dependents (Accounts)",
  "Relationship Mapping",
  "Templates + Customization",
  "Alert Preferences",
  "Invite + Acceptance Tracker",
  "Review + Activate"
]

const TEMPLATE_OPTIONS: { label: string; value: TemplateId; description: string }[] = [
  {
    value: "default-child-safe",
    label: "Default Child Safe",
    description: "Strict baseline for younger dependents."
  },
  {
    value: "teen-balanced",
    label: "Teen Balanced",
    description: "Balanced guidance with fewer hard blocks."
  },
  {
    value: "school-research",
    label: "School Research",
    description: "Education-focused with expanded research access."
  }
]

const STATUS_COLOR: Record<string, string> = {
  queued: "gold",
  active: "green",
  failed: "red",
  pending: "orange",
  declined: "red",
  revoked: "default"
}

const newMember = (prefix: string): MemberInput => ({
  key: `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
  displayName: "",
  userId: "",
  email: ""
})

const toRoleLabel = (role: MemberRole): string => {
  if (role === "guardian") return "Guardian"
  if (role === "caregiver") return "Caregiver"
  return "Dependent"
}

export function FamilyGuardrailsWizard({
  initialStep = 0,
  initialDraft = null
}: FamilyGuardrailsWizardProps = {}) {
  const [currentStep, setCurrentStep] = useState(initialStep)
  const [submitting, setSubmitting] = useState(false)
  const [draft, setDraft] = useState<HouseholdDraft | null>(initialDraft)
  const [mode, setMode] = useState<Mode>("family")
  const [householdName, setHouseholdName] = useState("My Household")
  const [alertNotifyContext, setAlertNotifyContext] = useState<"topic_only" | "snippet" | "full_message">(
    "snippet"
  )
  const [showAdvancedOverrides, setShowAdvancedOverrides] = useState(false)
  const [activationSummary, setActivationSummary] = useState<ActivationSummary | null>(null)

  const [guardians, setGuardians] = useState<MemberInput[]>([
    {
      key: "guardian-primary",
      displayName: "Primary Guardian",
      userId: "guardian-primary",
      email: ""
    }
  ])
  const [dependents, setDependents] = useState<MemberInput[]>([
    newMember("dependent"),
    newMember("dependent")
  ])

  const [guardianDraftByKey, setGuardianDraftByKey] = useState<Record<string, HouseholdMemberDraft>>({})
  const [dependentDraftByKey, setDependentDraftByKey] = useState<Record<string, HouseholdMemberDraft>>({})
  const [relationshipByDependentKey, setRelationshipByDependentKey] = useState<Record<string, RelationshipDraft>>({})
  const [planByDependentKey, setPlanByDependentKey] = useState<Record<string, GuardrailPlanDraft>>({})
  const [dependentGuardianKey, setDependentGuardianKey] = useState<Record<string, string>>({})
  const [templateByDependentKey, setTemplateByDependentKey] = useState<Record<string, TemplateId>>({})
  const [overridesByDependentKey, setOverridesByDependentKey] = useState<Record<string, OverrideInput>>({})

  const guardianOptions = useMemo(
    () =>
      guardians.map((guardian) => ({
        label: guardian.displayName || guardian.userId || toRoleLabel("guardian"),
        value: guardian.key
      })),
    [guardians]
  )

  const trackerRows = useMemo(() => {
    if (activationSummary?.items?.length) return activationSummary.items
    return dependents.map((dependent) => {
      const relationship = relationshipByDependentKey[dependent.key]
      const plan = planByDependentKey[dependent.key]
      return {
        dependent_user_id: dependent.userId || dependent.displayName || dependent.key,
        relationship_status: relationship?.status ?? "pending",
        plan_status: plan?.status ?? "queued",
        message: plan ? null : "Queued until acceptance"
      }
    })
  }, [activationSummary?.items, dependents, planByDependentKey, relationshipByDependentKey])

  const refreshActivationSummary = React.useCallback(async () => {
    if (!draft?.id) return
    try {
      const summary = await getActivationSummary(draft.id)
      setActivationSummary(summary)
    } catch (error) {
      message.warning(
        error instanceof Error
          ? error.message
          : "Unable to refresh acceptance tracker"
      )
    }
  }, [draft?.id])

  React.useEffect(() => {
    if (currentStep === 6 && draft?.id) {
      void refreshActivationSummary()
    }
  }, [currentStep, draft?.id, refreshActivationSummary])

  const ensureDraft = async (): Promise<HouseholdDraft> => {
    if (!householdName.trim()) {
      throw new Error("Household name is required")
    }
    if (draft) {
      const updated = await updateHouseholdDraft(draft.id, {
        name: householdName.trim(),
        mode
      })
      setDraft(updated)
      return updated
    }
    const created = await createHouseholdDraft({
      name: householdName.trim(),
      mode
    })
    setDraft(created)
    return created
  }

  const persistMembers = async (
    role: MemberRole,
    members: MemberInput[],
    draftId: string,
    existing: Record<string, HouseholdMemberDraft>,
    setExisting: React.Dispatch<React.SetStateAction<Record<string, HouseholdMemberDraft>>>
  ) => {
    const next = { ...existing }
    for (const member of members) {
      if (next[member.key]) continue
      if (!member.displayName.trim() || !member.userId.trim()) {
        throw new Error(`${toRoleLabel(role)} display name and user ID are required`)
      }
      const created = await addHouseholdMemberDraft(draftId, {
        role,
        display_name: member.displayName.trim(),
        user_id: member.userId.trim(),
        email: member.email.trim() || undefined,
        invite_required: role === "dependent"
      })
      next[member.key] = created
    }
    setExisting(next)
  }

  const persistRelationships = async (draftId: string) => {
    const next = { ...relationshipByDependentKey }
    for (const dependent of dependents) {
      if (next[dependent.key]) continue
      const dependentDraft = dependentDraftByKey[dependent.key]
      const preferredGuardianKey = dependentGuardianKey[dependent.key] || guardians[0]?.key
      const guardianDraft = preferredGuardianKey ? guardianDraftByKey[preferredGuardianKey] : null
      if (!dependentDraft || !guardianDraft) {
        throw new Error("Complete guardian and dependent account setup before mapping relationships")
      }
      const created = await saveRelationshipDraft(draftId, {
        guardian_member_draft_id: guardianDraft.id,
        dependent_member_draft_id: dependentDraft.id,
        relationship_type: mode === "institutional" ? "institutional" : "parent",
        dependent_visible: true
      })
      next[dependent.key] = created
    }
    setRelationshipByDependentKey(next)
  }

  const persistPlans = async (draftId: string) => {
    const next = { ...planByDependentKey }
    for (const dependent of dependents) {
      if (next[dependent.key]) continue
      const dependentDraft = dependentDraftByKey[dependent.key]
      const relationshipDraft = relationshipByDependentKey[dependent.key]
      if (!dependentDraft || !relationshipDraft) {
        throw new Error("Relationship mapping is required before plan setup")
      }
      const template = templateByDependentKey[dependent.key] ?? "default-child-safe"
      const overrides = overridesByDependentKey[dependent.key] ?? {
        action: "block",
        notify_context: alertNotifyContext
      }
      const payload: SaveGuardrailPlanDraftBody = {
        dependent_user_id: dependentDraft.user_id || dependent.userId.trim(),
        relationship_draft_id: relationshipDraft.id,
        template_id: template,
        overrides
      }
      const created = await saveGuardrailPlanDraft(draftId, payload)
      next[dependent.key] = created
    }
    setPlanByDependentKey(next)
  }

  const handleNext = async () => {
    try {
      setSubmitting(true)
      const ensuredDraft = await ensureDraft()

      if (currentStep === 1) {
        await persistMembers(
          "guardian",
          guardians,
          ensuredDraft.id,
          guardianDraftByKey,
          setGuardianDraftByKey
        )
      }
      if (currentStep === 2) {
        await persistMembers(
          "dependent",
          dependents,
          ensuredDraft.id,
          dependentDraftByKey,
          setDependentDraftByKey
        )
      }
      if (currentStep === 3) {
        await persistRelationships(ensuredDraft.id)
      }
      if (currentStep === 4) {
        await persistPlans(ensuredDraft.id)
      }
      if (currentStep === 6) {
        await refreshActivationSummary()
      }
      if (currentStep < STEP_TITLES.length - 1) {
        setCurrentStep((step) => step + 1)
      } else {
        message.success("Family guardrails wizard setup saved.")
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Unable to continue wizard")
    } finally {
      setSubmitting(false)
    }
  }

  const handleBack = () => setCurrentStep((step) => Math.max(0, step - 1))

  const applyTemplateToAll = (template: TemplateId) => {
    const next: Record<string, TemplateId> = {}
    dependents.forEach((dependent) => {
      next[dependent.key] = template
    })
    setTemplateByDependentKey(next)
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Paragraph type="secondary">
              Start by choosing your household model. Family mode supports one or two guardians with children.
              Institutional mode supports caregivers and classroom-style setups.
            </Paragraph>
            <Form layout="vertical">
              <Form.Item label="Household Name" required>
                <Input
                  value={householdName}
                  onChange={(event) => setHouseholdName(event.target.value)}
                  placeholder="e.g. Rivera Family"
                />
              </Form.Item>
              <Form.Item label="Household Mode">
                <Radio.Group
                  value={mode}
                  onChange={(event) => setMode(event.target.value as Mode)}
                >
                  <Space direction="vertical">
                    <Radio value="family">Family (one or two guardians)</Radio>
                    <Radio value="institutional">Institutional/Caregiver</Radio>
                  </Space>
                </Radio.Group>
              </Form.Item>
            </Form>
          </Space>
        )
      case 1:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Alert
              showIcon
              type="info"
              message="Add every guardian who can manage alerts and safety settings."
            />
            {guardians.map((guardian, index) => (
              <Card key={guardian.key} size="small">
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Input
                    value={guardian.displayName}
                    onChange={(event) =>
                      setGuardians((prev) =>
                        prev.map((item) =>
                          item.key === guardian.key ? { ...item, displayName: event.target.value } : item
                        )
                      )
                    }
                    placeholder={`Guardian ${index + 1} display name`}
                  />
                  <Input
                    value={guardian.userId}
                    onChange={(event) =>
                      setGuardians((prev) =>
                        prev.map((item) =>
                          item.key === guardian.key ? { ...item, userId: event.target.value } : item
                        )
                      )
                    }
                    placeholder="Guardian account user ID"
                  />
                  <Input
                    value={guardian.email}
                    onChange={(event) =>
                      setGuardians((prev) =>
                        prev.map((item) =>
                          item.key === guardian.key ? { ...item, email: event.target.value } : item
                        )
                      )
                    }
                    placeholder="Guardian email (optional)"
                  />
                  {guardians.length > 1 ? (
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() =>
                        setGuardians((prev) => prev.filter((item) => item.key !== guardian.key))
                      }
                    >
                      Remove Guardian
                    </Button>
                  ) : null}
                </Space>
              </Card>
            ))}
            <Button
              icon={<PlusOutlined />}
              onClick={() => setGuardians((prev) => [...prev, newMember("guardian")])}
            >
              Add Guardian
            </Button>
          </Space>
        )
      case 2:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Alert
              showIcon
              type="info"
              message="Create or link dependent accounts here. User IDs are required for invitation and acceptance."
            />
            {dependents.map((dependent, index) => (
              <Card key={dependent.key} size="small">
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Input
                    value={dependent.displayName}
                    onChange={(event) =>
                      setDependents((prev) =>
                        prev.map((item) =>
                          item.key === dependent.key ? { ...item, displayName: event.target.value } : item
                        )
                      )
                    }
                    placeholder={`Child ${index + 1} display name`}
                  />
                  <Input
                    value={dependent.userId}
                    onChange={(event) =>
                      setDependents((prev) =>
                        prev.map((item) =>
                          item.key === dependent.key ? { ...item, userId: event.target.value } : item
                        )
                      )
                    }
                    placeholder="Child account user ID"
                  />
                  <Input
                    value={dependent.email}
                    onChange={(event) =>
                      setDependents((prev) =>
                        prev.map((item) =>
                          item.key === dependent.key ? { ...item, email: event.target.value } : item
                        )
                      )
                    }
                    placeholder="Child email (optional)"
                  />
                  {dependents.length > 1 ? (
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() =>
                        setDependents((prev) => prev.filter((item) => item.key !== dependent.key))
                      }
                    >
                      Remove Dependent
                    </Button>
                  ) : null}
                </Space>
              </Card>
            ))}
            <Button
              icon={<PlusOutlined />}
              onClick={() => setDependents((prev) => [...prev, newMember("dependent")])}
            >
              Add Dependent
            </Button>
          </Space>
        )
      case 3:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Paragraph type="secondary">
              Map each dependent to a guardian. For shared households, dependents can be mapped to different guardians.
            </Paragraph>
            {dependents.map((dependent) => (
              <Card key={dependent.key} size="small">
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Text strong>{dependent.displayName || dependent.userId || dependent.key}</Text>
                  <Select
                    value={dependentGuardianKey[dependent.key] || guardians[0]?.key}
                    options={guardianOptions}
                    onChange={(value) =>
                      setDependentGuardianKey((prev) => ({
                        ...prev,
                        [dependent.key]: value
                      }))
                    }
                  />
                </Space>
              </Card>
            ))}
          </Space>
        )
      case 4:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Alert
              showIcon
              type="info"
              message="Apply a template first, then customize if needed."
            />
            <Space wrap>
              {TEMPLATE_OPTIONS.map((option) => (
                <Button key={option.value} onClick={() => applyTemplateToAll(option.value)}>
                  Apply "{option.label}" to all
                </Button>
              ))}
              <Button onClick={() => setShowAdvancedOverrides((value) => !value)}>
                {showAdvancedOverrides ? "Hide Advanced Overrides" : "Show Advanced Overrides"}
              </Button>
            </Space>
            {dependents.map((dependent) => {
              const template = templateByDependentKey[dependent.key] || "default-child-safe"
              const override = overridesByDependentKey[dependent.key] || {
                action: "block",
                notify_context: alertNotifyContext
              }
              return (
                <Card key={dependent.key} size="small">
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <Text strong>{dependent.displayName || dependent.userId || dependent.key}</Text>
                    <Select
                      value={template}
                      options={TEMPLATE_OPTIONS.map((option) => ({
                        label: `${option.label} - ${option.description}`,
                        value: option.value
                      }))}
                      onChange={(value) =>
                        setTemplateByDependentKey((prev) => ({
                          ...prev,
                          [dependent.key]: value as TemplateId
                        }))
                      }
                    />
                    {showAdvancedOverrides ? (
                      <Space>
                        <Select
                          value={override.action}
                          options={[
                            { label: "Block", value: "block" },
                            { label: "Redact", value: "redact" },
                            { label: "Warn", value: "warn" },
                            { label: "Notify", value: "notify" }
                          ]}
                          onChange={(value) =>
                            setOverridesByDependentKey((prev) => ({
                              ...prev,
                              [dependent.key]: {
                                ...override,
                                action: value as OverrideInput["action"]
                              }
                            }))
                          }
                        />
                        <Select
                          value={override.notify_context}
                          options={[
                            { label: "Topic only", value: "topic_only" },
                            { label: "Snippet", value: "snippet" },
                            { label: "Full message", value: "full_message" }
                          ]}
                          onChange={(value) =>
                            setOverridesByDependentKey((prev) => ({
                              ...prev,
                              [dependent.key]: {
                                ...override,
                                notify_context: value as OverrideInput["notify_context"]
                              }
                            }))
                          }
                        />
                      </Space>
                    ) : null}
                  </Space>
                </Card>
              )
            })}
          </Space>
        )
      case 5:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Paragraph type="secondary">
              Choose how guardians receive moderation context when alerts trigger.
            </Paragraph>
            <Select
              value={alertNotifyContext}
              options={[
                { label: "Topic only", value: "topic_only" },
                { label: "Snippet", value: "snippet" },
                { label: "Full message", value: "full_message" }
              ]}
              onChange={(value) =>
                setAlertNotifyContext(value as "topic_only" | "snippet" | "full_message")
              }
              style={{ maxWidth: 320 }}
            />
            <Text type="secondary">
              You can fine-tune these settings per dependent using advanced overrides in the templates step.
            </Text>
          </Space>
        )
      case 6:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => void refreshActivationSummary()}>
                Refresh statuses
              </Button>
              <Button disabled>Resend invite (coming soon)</Button>
            </Space>
            <Table
              rowKey={(row) => `${row.dependent_user_id}:${row.relationship_status}:${row.plan_status}`}
              dataSource={trackerRows}
              pagination={false}
              columns={[
                {
                  title: "Dependent",
                  dataIndex: "dependent_user_id"
                },
                {
                  title: "Relationship",
                  dataIndex: "relationship_status",
                  render: (value: string) => <Tag color={STATUS_COLOR[value] || "default"}>{value}</Tag>
                },
                {
                  title: "Guardrail Activation",
                  dataIndex: "plan_status",
                  render: (value: string) => (
                    <Tag color={STATUS_COLOR[value] || "default"}>
                      {value === "queued" ? "Queued until acceptance" : value === "active" ? "Active" : "Failed"}
                    </Tag>
                  )
                },
                {
                  title: "Message",
                  dataIndex: "message",
                  render: (value: string | null) => value || "Active"
                }
              ]}
            />
          </Space>
        )
      case 7:
      default:
        return (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Alert
              showIcon
              type="success"
              message="Review household activation summary"
              description="You can complete setup now and come back anytime to adjust templates or mappings."
            />
            <Card size="small">
              <Space direction="vertical" style={{ width: "100%" }}>
                <Text>
                  <Text strong>Household:</Text> {householdName}
                </Text>
                <Text>
                  <Text strong>Mode:</Text> {mode}
                </Text>
                <Text>
                  <Text strong>Guardians:</Text> {guardians.length}
                </Text>
                <Text>
                  <Text strong>Dependents:</Text> {dependents.length}
                </Text>
                <Text>
                  <Text strong>Activation:</Text>{" "}
                  {activationSummary
                    ? `${activationSummary.active_count} active, ${activationSummary.pending_count} pending, ${activationSummary.failed_count} failed`
                    : "Pending tracker refresh"}
                </Text>
              </Space>
            </Card>
          </Space>
        )
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Title level={4}>Family Guardrails Wizard</Title>
        <Paragraph type="secondary">
          Template-first setup for guardians, dependents, moderation templates, and acceptance tracking.
        </Paragraph>
      </div>

      <Steps
        current={currentStep}
        items={STEP_TITLES.map((title) => ({ title }))}
      />

      <Card>{renderStepContent()}</Card>

      <Divider style={{ margin: "0" }} />

      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <Button disabled={currentStep === 0 || submitting} onClick={handleBack}>
          Back
        </Button>
        <Button type="primary" loading={submitting} onClick={() => void handleNext()}>
          {currentStep === STEP_TITLES.length - 1 ? "Finish Setup" : "Save & Continue"}
        </Button>
      </Space>
    </Space>
  )
}

export default FamilyGuardrailsWizard
