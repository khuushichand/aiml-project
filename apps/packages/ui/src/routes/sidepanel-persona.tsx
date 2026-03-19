import React from "react"
import { Button, Checkbox, Input, Select, Tag, Typography } from "antd"
import { CheckCircle2, Send, XCircle } from "lucide-react"
import {
  UNSAFE_DataRouterContext,
  useBlocker,
  useLocation,
  useNavigate
} from "react-router-dom"
import { useTranslation } from "react-i18next"

import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { PersonaPolicySummary } from "@/components/Option/MCPHub"
import {
  type PersonaVoiceAnalytics
} from "@/components/PersonaGarden/CommandAnalyticsSummary"
import type { PersonaSetupAnalyticsResponse } from "@/components/PersonaGarden/PersonaSetupAnalyticsCard"
import type { PersonaTurnDetectionValues } from "@/components/PersonaGarden/PersonaTurnDetectionControls"
import { AssistantVoiceCard } from "@/components/PersonaGarden/AssistantVoiceCard"
import { AssistantDefaultsPanel } from "@/components/PersonaGarden/AssistantDefaultsPanel"
import {
  PersonaSetupHandoffCard,
  type SetupHandoffRecommendedAction,
  type SetupReviewSummary
} from "@/components/PersonaGarden/PersonaSetupHandoffCard"
import { AssistantSetupWizard } from "@/components/PersonaGarden/AssistantSetupWizard"
import {
  CommandsPanel,
  type CommandDraftSource
} from "@/components/PersonaGarden/CommandsPanel"
import { ConnectionsPanel } from "@/components/PersonaGarden/ConnectionsPanel"
import { LiveSessionPanel } from "@/components/PersonaGarden/LiveSessionPanel"
import { PersonaGardenTabs } from "@/components/PersonaGarden/PersonaGardenTabs"
import { PoliciesPanel } from "@/components/PersonaGarden/PoliciesPanel"
import { ProfilePanel } from "@/components/PersonaGarden/ProfilePanel"
import { ScopesPanel } from "@/components/PersonaGarden/ScopesPanel"
import {
  SetupSafetyConnectionsStep,
  type SetupSafetyConnectionDraft
} from "@/components/PersonaGarden/SetupSafetyConnectionsStep"
import { SetupStarterCommandsStep } from "@/components/PersonaGarden/SetupStarterCommandsStep"
import {
  SetupTestAndFinishStep,
  type SetupTestOutcome
} from "@/components/PersonaGarden/SetupTestAndFinishStep"
import { StateDocsPanel } from "@/components/PersonaGarden/StateDocsPanel"
import {
  TestLabPanel,
  type TestLabDryRunCompletedResult,
} from "@/components/PersonaGarden/TestLabPanel"
import { VoiceExamplesPanel } from "@/components/PersonaGarden/VoiceExamplesPanel"
import {
  getPersonaStarterCommandTemplate,
  PERSONA_STARTER_COMMAND_TEMPLATES
} from "@/components/PersonaGarden/personaStarterCommandTemplates"
import { buildPersonaSetupProgress } from "@/components/PersonaGarden/personaSetupProgress"
import { useConnectionUxState } from "@/hooks/useConnectionState"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import {
  fetchCompanionConversationPrompts,
  isCompanionConsentRequiredResponse
} from "@/services/companion"
import {
  buildSetupEventKey,
  postPersonaSetupEvent,
  type PersonaSetupAnalyticsEvent,
  type PersonaSetupAnalyticsEventType
} from "@/services/tldw/persona-setup-analytics"
import { toAllowedPath } from "@/services/tldw/path-utils"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { buildPersonaWebSocketUrl } from "@/services/persona-stream"
import {
  type PersonaGardenTabKey
} from "@/utils/persona-garden-route"
import { usePersonaGardenRouteBootstrap } from "@/hooks/usePersonaGardenRouteBootstrap"
import {
  usePersonaLiveVoiceController
} from "@/hooks/usePersonaLiveVoiceController"
import {
  useResolvedPersonaVoiceDefaults,
  type PersonaConfirmationMode,
  type PersonaVoiceDefaults
} from "@/hooks/useResolvedPersonaVoiceDefaults"
import {
  usePersonaSetupWizard,
  type PersonaSetupState,
  type PersonaSetupStep
} from "@/hooks/usePersonaSetupWizard"
import { SidepanelHeaderSimple } from "~/components/Sidepanel/Chat/SidepanelHeaderSimple"

type PersonaInfo = {
  id: string
  name: string
  description?: string | null
  voice?: string | null
}

type PersonaPlanStep = {
  idx: number
  tool: string
  args?: Record<string, unknown>
  description?: string
  why?: string
  policy?: PersonaToolPolicy
}

type PendingPlan = {
  planId: string
  steps: PersonaPlanStep[]
  memory?: PersonaMemoryUsage
  companion?: PersonaCompanionUsage
}

type PersonaLogEntry = {
  id: string
  kind: "user" | "assistant" | "tool" | "notice"
  text: string
}

type PersonaToolPolicy = {
  allow?: boolean
  requires_confirmation?: boolean
  required_scope?: string | null
  reason_code?: string | null
  reason?: string | null
  action?: string | null
}

type PersonaMemoryUsage = {
  enabled?: boolean
  requested_top_k?: number
  applied_count?: number
}

type PersonaCompanionUsage = {
  enabled?: boolean
  requested_enabled?: boolean
  applied_card_count?: number
  applied_activity_count?: number
}

type PersonaRuntimeApprovalPayload = {
  approval_policy_id?: number | null
  mode?: string | null
  tool_name?: string | null
  context_key?: string | null
  conversation_id?: string | null
  scope_key?: string | null
  reason?: string | null
  duration_options?: string[]
  arguments_summary?: Record<string, unknown>
  scope_context?: PersonaGovernanceScopeContext | null
}

type PersonaRuntimeApprovalDuration = "once" | "session" | "conversation"

type PersonaRuntimeApprovalRequest = {
  key: string
  approval_policy_id?: number | null
  mode?: string | null
  tool_name: string
  context_key: string
  conversation_id?: string | null
  scope_key: string
  reason?: string | null
  duration_options: PersonaRuntimeApprovalDuration[]
  arguments_summary: Record<string, unknown>
  scope_context?: PersonaGovernanceScopeContext | null
  selected_duration: PersonaRuntimeApprovalDuration
  session_id?: string | null
  plan_id?: string | null
  step_idx?: number
  step_type?: string | null
  tool?: string | null
  args?: Record<string, unknown>
  why?: string | null
  description?: string | null
}

type PersonaGovernanceScopeContext = {
  server_id?: string | null
  server_name?: string | null
  requested_slots?: string[]
  bound_slots?: string[]
  missing_bound_slots?: string[]
  missing_secret_slots?: string[]
  workspace_id?: string | null
  workspace_bundle_ids?: string[]
  workspace_bundle_roots?: string[]
  normalized_paths?: string[]
  selected_workspace_trust_source?: string | null
  selected_assignment_id?: number | null
  blocked_reason?: string | null
  reason?: string | null
}

type PersonaSessionSummary = {
  session_id: string
  persona_id?: string
  created_at?: string
  updated_at?: string
  turn_count?: number
  pending_plan_count?: number
}

type PersonaSessionPreferences = {
  use_memory_context?: boolean
  use_companion_context?: boolean
  use_persona_state_context?: boolean
  memory_top_k?: number
}

type PersonaSessionDetailResponse = {
  preferences?: PersonaSessionPreferences
  turns?: Array<Record<string, unknown>>
}

type PersonaProfileResponse = {
  id?: string
  version?: number
  use_persona_state_context_default?: boolean
  voice_defaults?: PersonaVoiceDefaults | null
  setup?: PersonaSetupState | null
}

type SetupStepErrors = {
  persona?: string | null
  voice?: string | null
  commands?: string | null
  safety?: string | null
  test?: string | null
}

type SetupHandoffState = {
  runId: string
  targetTab: PersonaGardenTabKey
  completionType: "dry_run" | "live_session"
  reviewSummary: SetupReviewSummary
  recommendedAction: SetupHandoffRecommendedAction
  consumedAction: SetupHandoffConsumedAction | null
  compact: boolean
}

type SetupHandoffSectionTarget =
  | { tab: "commands"; section: "command_form" | "command_list" }
  | {
      tab: "connections"
      section: "connection_form" | "saved_connections"
      connectionId?: string | null
      connectionName?: string | null
    }
  | { tab: "profiles"; section: "assistant_defaults" | "confirmation_mode" }
  | { tab: "test-lab"; section: "dry_run_form" }

type SetupHandoffFocusRequest = {
  tab: SetupHandoffSectionTarget["tab"]
  section: SetupHandoffSectionTarget["section"]
  token: number
  connectionId?: string | null
  connectionName?: string | null
}

type SetupHandoffConsumedAction =
  | "command_saved"
  | "connection_saved"
  | "connection_test_succeeded"
  | "voice_defaults_saved"
  | "dry_run_match"
  | "live_response_received"

type SetupCommandDetourState = {
  phrase: string
  returnStep: "test"
}

type SetupLiveDetourState = {
  source: "live_unavailable" | "live_failure"
  lastText: string
}

const DEFAULT_SETUP_REVIEW_SUMMARY: SetupReviewSummary = {
  starterCommands: { mode: "skipped" },
  confirmationMode: null,
  connection: { mode: "skipped" }
}

const SETUP_STARTER_COMMAND_DESCRIPTIONS = new Set(
  PERSONA_STARTER_COMMAND_TEMPLATES.map((template) => template.commandDescription)
)

const isSetupCreatedStarterCommand = (value: unknown): boolean => {
  if (!value || typeof value !== "object") return false
  const record = value as Record<string, unknown>
  const description = String(record.description || "").trim()
  if (!description) return false
  return (
    SETUP_STARTER_COMMAND_DESCRIPTIONS.has(description) ||
    / from assistant setup$/i.test(description)
  )
}

const pickAvailableConnectionName = (value: unknown): string | null => {
  if (!Array.isArray(value)) return null
  const names = value
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null
      const record = entry as Record<string, unknown>
      const name = String(record.name || "").trim()
      const createdAt = String(record.created_at || record.last_modified || "").trim()
      if (!name) return null
      return {
        name,
        createdAt
      }
    })
    .filter((entry): entry is { name: string; createdAt: string } => Boolean(entry))

  if (names.length === 0) return null

  return names
    .slice()
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0]?.name || null
}

const summarizeFallbackStarterCommands = (value: unknown): SetupReviewSummary["starterCommands"] => {
  const commands = Array.isArray((value as { commands?: unknown[] } | null | undefined)?.commands)
    ? ((value as { commands: unknown[] }).commands)
    : []
  const setupCreatedCount = commands.filter(isSetupCreatedStarterCommand).length

  if (setupCreatedCount > 0) {
    return {
      mode: "configured",
      count: setupCreatedCount
    }
  }

  return { mode: "skipped" }
}

const deriveSetupHandoffRecommendedAction = ({
  completionType,
  reviewSummary
}: {
  completionType: "dry_run" | "live_session"
  reviewSummary: SetupReviewSummary
}): SetupHandoffRecommendedAction => {
  if (reviewSummary.starterCommands.mode === "skipped") {
    return "add_command"
  }
  if (reviewSummary.connection.mode === "skipped") {
    return "add_connection"
  }
  if (completionType === "dry_run") {
    return "try_live"
  }
  return "review_commands"
}

const toSetupHandoffActionTarget = (
  action: SetupHandoffConsumedAction
): PersonaGardenTabKey => {
  if (action === "command_saved") return "commands"
  if (action === "connection_saved" || action === "connection_test_succeeded") {
    return "connections"
  }
  if (action === "voice_defaults_saved") return "profiles"
  if (action === "live_response_received") return "live"
  return "test-lab"
}

type PersonaStateDocsResponse = {
  persona_id?: string
  soul_md?: string | null
  identity_md?: string | null
  heartbeat_md?: string | null
  last_modified?: string | null
}

type PersonaStateHistoryEntry = {
  entry_id: string
  field: "soul_md" | "identity_md" | "heartbeat_md"
  content: string
  is_active?: boolean
  created_at?: string | null
  last_modified?: string | null
  version?: number
}

type PersonaStateHistoryResponse = {
  persona_id?: string
  entries?: PersonaStateHistoryEntry[]
}

type UnsavedStateDiscardReason =
  | "generic"
  | "connect"
  | "disconnect"
  | "reload_state"
  | "persona_switch"
  | "session_switch"
  | "restore_state"
  | "route_transition"
  | "before_unload"

const formatMemoryResultsLabel = (count: number) => `Memory results: ${count}`
const MAX_MEMORY_TOP_K = 10
const MEMORY_TOP_K_OPTIONS = Array.from(
  { length: MAX_MEMORY_TOP_K },
  (_, index) => index + 1
)
const _normalizeMemoryTopK = (value: unknown, fallback: number): number => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.max(1, Math.min(MAX_MEMORY_TOP_K, Math.trunc(parsed)))
}
const _historyEntrySortEpoch = (entry: PersonaStateHistoryEntry): number => {
  const candidate = String(entry.created_at || entry.last_modified || "").trim()
  if (!candidate) return 0
  const parsed = Date.parse(candidate)
  return Number.isFinite(parsed) ? parsed : 0
}
const PERSONA_STATE_EDITOR_EXPANDED_PREF_KEY =
  "sidepanel:persona:state-editor-expanded"
const PERSONA_STATE_HISTORY_ORDER_PREF_KEY = "sidepanel:persona:state-history-order"
const RESOLVED_RUNTIME_APPROVAL_FADE_MS = 1500
const APPROVAL_HIGHLIGHT_PRIMARY_MS = 900
const APPROVAL_HIGHLIGHT_SECONDARY_MS = 650

const hasExplicitTurnDetectionDefaults = (
  voiceDefaults?: PersonaVoiceDefaults | null
): boolean =>
  typeof voiceDefaults?.auto_commit_enabled === "boolean" &&
  typeof voiceDefaults?.vad_threshold === "number" &&
  typeof voiceDefaults?.min_silence_ms === "number" &&
  typeof voiceDefaults?.turn_stop_secs === "number" &&
  typeof voiceDefaults?.min_utterance_secs === "number"

const buildTurnDetectionValuesFromSavedDefaults = (
  voiceDefaults?: PersonaVoiceDefaults | null
): PersonaTurnDetectionValues | null => {
  if (!hasExplicitTurnDetectionDefaults(voiceDefaults)) return null
  return {
    autoCommitEnabled: Boolean(voiceDefaults?.auto_commit_enabled),
    vadThreshold: Number(voiceDefaults?.vad_threshold),
    minSilenceMs: Number(voiceDefaults?.min_silence_ms),
    turnStopSecs: Number(voiceDefaults?.turn_stop_secs),
    minUtteranceSecs: Number(voiceDefaults?.min_utterance_secs)
  }
}

const areTurnDetectionValuesEqual = (
  left: PersonaTurnDetectionValues,
  right: PersonaTurnDetectionValues
): boolean =>
  left.autoCommitEnabled === right.autoCommitEnabled &&
  left.vadThreshold === right.vadThreshold &&
  left.minSilenceMs === right.minSilenceMs &&
  left.turnStopSecs === right.turnStopSecs &&
  left.minUtteranceSecs === right.minUtteranceSecs

type ApprovalHighlightPhase =
  | "none"
  | "landing_primary"
  | "landing_secondary"
  | "steady"

const _approvalRequestKey = (
  approval: PersonaRuntimeApprovalPayload,
  payload: Record<string, unknown>
): string =>
  [
    String(approval.conversation_id || payload.session_id || "").trim(),
    String(approval.scope_key || "").trim(),
    String(approval.tool_name || payload.tool || "").trim(),
    String(payload.plan_id || "").trim(),
    String(payload.step_idx ?? "").trim()
  ].join("|")

const _approvalDecisionPayload = (
  decision: "approved" | "denied",
  duration: string
): { duration: PersonaRuntimeApprovalDuration } => {
  const normalized = String(duration || "").trim().toLowerCase()
  if (decision !== "approved") {
    return { duration: "once" }
  }
  if (normalized === "conversation") {
    return { duration: "conversation" }
  }
  if (normalized === "session") {
    return { duration: "session" }
  }
  return { duration: "once" }
}

const _normalizeStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => String(entry || "").trim())
    .filter((entry) => entry.length > 0)
}

const _coerceGovernanceContext = (value: unknown): PersonaGovernanceScopeContext | null => {
  if (!value || typeof value !== "object") return null
  const raw = value as Record<string, unknown>
  const context: PersonaGovernanceScopeContext = {
    server_id: raw.server_id ? String(raw.server_id) : null,
    server_name: raw.server_name ? String(raw.server_name) : null,
    requested_slots: _normalizeStringList(raw.requested_slots),
    bound_slots: _normalizeStringList(raw.bound_slots),
    missing_bound_slots: _normalizeStringList(raw.missing_bound_slots),
    missing_secret_slots: _normalizeStringList(raw.missing_secret_slots),
    workspace_id: raw.workspace_id ? String(raw.workspace_id) : null,
    workspace_bundle_ids: _normalizeStringList(raw.workspace_bundle_ids),
    workspace_bundle_roots: _normalizeStringList(raw.workspace_bundle_roots),
    normalized_paths: _normalizeStringList(raw.normalized_paths),
    selected_workspace_trust_source: raw.selected_workspace_trust_source
      ? String(raw.selected_workspace_trust_source)
      : null,
    selected_assignment_id:
      typeof raw.selected_assignment_id === "number"
        ? raw.selected_assignment_id
        : Number.isFinite(Number(raw.selected_assignment_id))
          ? Number(raw.selected_assignment_id)
          : null,
    blocked_reason: raw.blocked_reason ? String(raw.blocked_reason) : null,
    reason: raw.reason ? String(raw.reason) : null
  }
  const hasContent =
    Boolean(
      context.server_id ||
      context.server_name ||
      context.workspace_id ||
      context.selected_workspace_trust_source ||
      context.blocked_reason ||
      context.reason
    ) ||
    Boolean(context.workspace_bundle_ids?.length) ||
    Boolean(context.workspace_bundle_roots?.length) ||
    Boolean(context.normalized_paths?.length) ||
    Boolean(context.requested_slots?.length) ||
    Boolean(context.bound_slots?.length) ||
    Boolean(context.missing_bound_slots?.length) ||
    Boolean(context.missing_secret_slots?.length)
  return hasContent ? context : null
}

const _formatGovernanceDenyMessage = (
  context: PersonaGovernanceScopeContext | null,
  reasonCode: string | null
): string | null => {
  const normalizedReason = String(reasonCode || context?.blocked_reason || "")
    .trim()
    .toLowerCase()
  if (normalizedReason === "required_slot_not_granted") {
    const slots = context?.missing_bound_slots?.length
      ? context.missing_bound_slots
      : context?.requested_slots || []
    return slots.length ? `Credential slots not granted: ${slots.join(", ")}` : null
  }
  if (normalizedReason === "required_slot_secret_missing") {
    const slots = context?.missing_secret_slots?.length
      ? context.missing_secret_slots
      : context?.requested_slots || []
    return slots.length ? `Credential secrets missing: ${slots.join(", ")}` : null
  }
  if (normalizedReason === "workspace_unresolvable_for_trust_source") {
    return "Blocked: workspace is not resolvable through the required trust source."
  }
  if (normalizedReason === "path_matches_multiple_workspace_roots") {
    return "Blocked: path matched multiple trusted workspace roots."
  }
  if (normalizedReason === "path_outside_workspace_bundle") {
    return "Blocked: path falls outside the allowed workspace bundle."
  }
  return null
}

const _readBoolPreference = (key: string, fallback: boolean): boolean => {
  if (typeof window === "undefined") return fallback
  try {
    const raw = window.localStorage.getItem(key)
    if (raw == null) return fallback
    const normalized = raw.trim().toLowerCase()
    if (normalized === "true") return true
    if (normalized === "false") return false
  } catch {
    // ignore storage access errors
  }
  return fallback
}

const _readHistoryOrderPreference = (): "newest" | "oldest" => {
  if (typeof window === "undefined") return "newest"
  try {
    const raw = window.localStorage
      .getItem(PERSONA_STATE_HISTORY_ORDER_PREF_KEY)
      ?.trim()
      .toLowerCase()
    if (raw === "oldest") return "oldest"
  } catch {
    // ignore storage access errors
  }
  return "newest"
}

const _confirmWithBrowserPrompt = (message: string): boolean => {
  if (typeof window === "undefined" || typeof window.confirm !== "function") return true
  try {
    return window.confirm(message)
  } catch {
      return true
  }
}

const IDLE_ROUTE_BLOCKER: ReturnType<typeof useBlocker> = {
  state: "unblocked",
  proceed: undefined,
  reset: undefined
} as ReturnType<typeof useBlocker>

const useCompatibleRouteBlocker = (
  when: boolean
): ReturnType<typeof useBlocker> => {
  const dataRouterContext = React.useContext(UNSAFE_DataRouterContext)
  if (!dataRouterContext) return IDLE_ROUTE_BLOCKER
  return useBlocker(when)
}

type PersonaRouteMode = "persona" | "companion"
type PersonaRouteShell = "sidepanel" | "options"

type SidepanelPersonaProps = {
  mode?: PersonaRouteMode
  shell?: PersonaRouteShell
}

const DEFAULT_PERSONA_ID = "research_assistant"
const DEFAULT_COMPANION_PROMPT_QUERY = "resume recent companion work"

const SidepanelPersona = ({
  mode = "persona",
  shell = "sidepanel"
}: SidepanelPersonaProps) => {
  const { t } = useTranslation(["sidepanel", "common", "option"])
  const navigate = useNavigate()
  const location = useLocation()
  const isOnline = useServerOnline()
  const { uxState, hasCompletedFirstRun } = useConnectionUxState()
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const isCompanionMode = mode === "companion"
  const routeTitle = isCompanionMode
    ? t("option:header.companion", "Companion")
    : t("sidepanel:persona.title", "Persona Garden")
  const routeRootClassName =
    shell === "sidepanel"
      ? "flex bg-bg flex-col min-h-screen mx-auto max-w-7xl"
      : "flex bg-bg flex-col gap-3 mx-auto max-w-7xl"

  const wsRef = React.useRef<WebSocket | null>(null)
  const manuallyClosingRef = React.useRef(false)
  const liveVoiceAnalyticsSnapshotRef = React.useRef<{
    personaId: string
    sessionId: string
    listeningRecoveryCount: number
    thinkingRecoveryCount: number
  }>({
    personaId: "",
    sessionId: "",
    listeningRecoveryCount: 0,
    thinkingRecoveryCount: 0
  })
  const runtimeApprovalCardRef = React.useRef<HTMLDivElement | null>(null)
  const runtimeApprovalRowRefs = React.useRef<Map<string, HTMLDivElement | null>>(
    new Map()
  )
  const setupHandoffFocusTokenRef = React.useRef(0)
  const emittedSetupEventKeysRef = React.useRef<Set<string>>(new Set())
  const setupLiveDetourRef = React.useRef<SetupLiveDetourState | null>(null)
  const setupHandoffRef = React.useRef<SetupHandoffState | null>(null)
  const setupHandoffFocusRequestRef = React.useRef<SetupHandoffFocusRequest | null>(null)
  const activeTabRef = React.useRef<PersonaGardenTabKey>("live")
  const resolvedApprovalFadeTimerRef = React.useRef<number | null>(null)
  const approvalHighlightPhaseTimerRef = React.useRef<number | null>(null)
  const handleIncomingPayloadRef = React.useRef<(payload: any) => void>(() => {})
  const liveVoiceControllerRef = React.useRef<any>(null)

  const [catalog, setCatalog] = React.useState<PersonaInfo[]>([])
  const [selectedPersonaId, setSelectedPersonaId] =
    React.useState<string>(DEFAULT_PERSONA_ID)
  const [savedPersonaVoiceDefaults, setSavedPersonaVoiceDefaults] =
    React.useState<PersonaVoiceDefaults | null>(null)
  const [savedPersonaSetup, setSavedPersonaSetup] =
    React.useState<PersonaSetupState | null>(null)
  const [savedPersonaProfileVersion, setSavedPersonaProfileVersion] = React.useState<
    number | null
  >(null)
  const [personaProfileLoading, setPersonaProfileLoading] = React.useState(false)
  const [setupWizardSaving, setSetupWizardSaving] = React.useState(false)
  const [setupStepErrors, setSetupStepErrors] = React.useState<SetupStepErrors>({})
  const [setupWizardDryRunLoading, setSetupWizardDryRunLoading] = React.useState(false)
  const [setupTestOutcome, setSetupTestOutcome] = React.useState<SetupTestOutcome | null>(
    null
  )
  const setupWizardAwaitingLiveResponseRef = React.useRef(false)
  const setupWizardLastLiveTextRef = React.useRef("")
  const [setupHandoff, setSetupHandoff] = React.useState<SetupHandoffState | null>(null)
  const [setupHandoffFocusRequest, setSetupHandoffFocusRequest] =
    React.useState<SetupHandoffFocusRequest | null>(null)
  const [setupReviewSummaryDraft, setSetupReviewSummaryDraft] =
    React.useState<SetupReviewSummary>(DEFAULT_SETUP_REVIEW_SUMMARY)
  const [liveSessionVoiceDefaultsBaseline, setLiveSessionVoiceDefaultsBaseline] =
    React.useState<PersonaVoiceDefaults | null>(null)
  const [activeTab, setActiveTab] = React.useState<PersonaGardenTabKey>("live")
  const [openCommandId, setOpenCommandId] = React.useState<string | null>(null)
  const [draftCommandPhrase, setDraftCommandPhrase] = React.useState<string | null>(null)
  const [draftCommandSource, setDraftCommandSource] =
    React.useState<CommandDraftSource | null>(null)
  const [rerunAfterSaveCommandId, setRerunAfterSaveCommandId] =
    React.useState<string | null>(null)
  const [lastTestLabPhrase, setLastTestLabPhrase] = React.useState("")
  const [setupCommandDetour, setSetupCommandDetour] =
    React.useState<SetupCommandDetourState | null>(null)
  const [setupLiveDetour, setSetupLiveDetour] =
    React.useState<SetupLiveDetourState | null>(null)
  const [setupNoMatchPhrase, setSetupNoMatchPhrase] = React.useState<string | null>(null)
  const [setupTestResumeNote, setSetupTestResumeNote] = React.useState<string | null>(null)
  const [testLabRerunToken, setTestLabRerunToken] = React.useState(0)
  const [pendingRecoveryReconnectToken, setPendingRecoveryReconnectToken] =
    React.useState(0)
  const [voiceAnalytics, setVoiceAnalytics] = React.useState<PersonaVoiceAnalytics | null>(
    null
  )
  const [voiceAnalyticsLoading, setVoiceAnalyticsLoading] = React.useState(false)
  const [setupAnalytics, setSetupAnalytics] =
    React.useState<PersonaSetupAnalyticsResponse | null>(null)
  const [setupAnalyticsLoading, setSetupAnalyticsLoading] = React.useState(false)
  const [savingLiveVoiceDefaults, setSavingLiveVoiceDefaults] = React.useState(false)
  const [setupIntentTargetTab, setSetupIntentTargetTab] =
    React.useState<PersonaGardenTabKey | null>(null)
  const [setupIntentPersonaId, setSetupIntentPersonaId] = React.useState("")
  const [sessionId, setSessionId] = React.useState<string | null>(null)
  const [sessionHistory, setSessionHistory] = React.useState<PersonaSessionSummary[]>([])
  const [resumeSessionId, setResumeSessionId] = React.useState<string>("")
  const [memoryEnabled, setMemoryEnabled] = React.useState(true)
  const [memoryTopK, setMemoryTopK] = React.useState<number>(3)
  const [companionContextEnabled, setCompanionContextEnabled] = React.useState(true)
  const [personaStateContextEnabled, setPersonaStateContextEnabled] =
    React.useState(!isCompanionMode)
  const [personaStateContextProfileDefault, setPersonaStateContextProfileDefault] =
    React.useState(!isCompanionMode)
  const [updatingPersonaStateContextDefault, setUpdatingPersonaStateContextDefault] =
    React.useState(false)
  const [soulMd, setSoulMd] = React.useState("")
  const [identityMd, setIdentityMd] = React.useState("")
  const [heartbeatMd, setHeartbeatMd] = React.useState("")
  const [savedSoulMd, setSavedSoulMd] = React.useState("")
  const [savedIdentityMd, setSavedIdentityMd] = React.useState("")
  const [savedHeartbeatMd, setSavedHeartbeatMd] = React.useState("")
  const [stateLastModified, setStateLastModified] = React.useState<string | null>(null)
  const [personaStateLoading, setPersonaStateLoading] = React.useState(false)
  const [personaStateSaving, setPersonaStateSaving] = React.useState(false)
  const [personaStateHistoryLoading, setPersonaStateHistoryLoading] =
    React.useState(false)
  const [personaStateHistoryLoaded, setPersonaStateHistoryLoaded] =
    React.useState(false)
  const [personaStateHistoryOrder, setPersonaStateHistoryOrder] =
    React.useState<"newest" | "oldest">(_readHistoryOrderPreference)
  const [personaStateEditorExpanded, setPersonaStateEditorExpanded] =
    React.useState(() =>
      _readBoolPreference(PERSONA_STATE_EDITOR_EXPANDED_PREF_KEY, true)
    )
  const [personaStateHistory, setPersonaStateHistory] = React.useState<
    PersonaStateHistoryEntry[]
  >([])
  const [restoringStateEntryId, setRestoringStateEntryId] = React.useState<
    string | null
  >(null)
  const [connected, setConnected] = React.useState(false)
  const [connecting, setConnecting] = React.useState(false)
  const [savingCompanionCheckIn, setSavingCompanionCheckIn] = React.useState(false)
  const [companionPrompts, setCompanionPrompts] = React.useState<
    Array<{ prompt_id: string; label: string; prompt_text: string }>
  >([])
  const [error, setError] = React.useState<string | null>(null)
  const [input, setInput] = React.useState("")
  const [logs, setLogs] = React.useState<PersonaLogEntry[]>([])
  const [pendingPlan, setPendingPlan] = React.useState<PendingPlan | null>(null)
  const [pendingApprovals, setPendingApprovals] = React.useState<
    PersonaRuntimeApprovalRequest[]
  >([])
  const [activeApprovalKey, setActiveApprovalKey] = React.useState<string | null>(null)
  const [approvalHighlightPhase, setApprovalHighlightPhase] =
    React.useState<ApprovalHighlightPhase>("none")
  const [approvalHighlightSequence, setApprovalHighlightSequence] = React.useState(0)
  const [resolvedApprovalSnapshot, setResolvedApprovalSnapshot] = React.useState<{
    key: string
    toolName: string
  } | null>(null)
  const [approvedStepMap, setApprovedStepMap] = React.useState<
    Record<number, boolean>
  >({})
  const [submittingApprovalKey, setSubmittingApprovalKey] = React.useState<string | null>(
    null
  )
  const [activeSessionPersonaId, setActiveSessionPersonaId] = React.useState<string | null>(
    null
  )
  const routeBootstrap = usePersonaGardenRouteBootstrap({
    search: location.search,
    setActiveTab,
    setSelectedPersonaId
  })

  React.useEffect(() => {
    setupLiveDetourRef.current = setupLiveDetour
  }, [setupLiveDetour])

  React.useEffect(() => {
    setupHandoffRef.current = setupHandoff
  }, [setupHandoff])

  React.useEffect(() => {
    setupHandoffFocusRequestRef.current = setupHandoffFocusRequest
  }, [setupHandoffFocusRequest])

  React.useEffect(() => {
    activeTabRef.current = activeTab
  }, [activeTab])

  React.useEffect(() => {
    if (!isCompanionMode) return
    setCompanionContextEnabled(true)
    setPersonaStateContextEnabled(false)
    setPersonaStateContextProfileDefault(false)
  }, [isCompanionMode])

  const clearResolvedApprovalFadeTimer = React.useCallback(() => {
    if (resolvedApprovalFadeTimerRef.current == null) return
    window.clearTimeout(resolvedApprovalFadeTimerRef.current)
    resolvedApprovalFadeTimerRef.current = null
  }, [])

  const clearApprovalHighlightPhaseTimer = React.useCallback(() => {
    if (approvalHighlightPhaseTimerRef.current == null) return
    window.clearTimeout(approvalHighlightPhaseTimerRef.current)
    approvalHighlightPhaseTimerRef.current = null
  }, [])

  const resetApprovalHighlightMotion = React.useCallback(() => {
    clearApprovalHighlightPhaseTimer()
    setApprovalHighlightPhase("none")
  }, [clearApprovalHighlightPhaseTimer])

  const triggerApprovalHighlightPhase = React.useCallback(
    (phase: Extract<ApprovalHighlightPhase, "landing_primary" | "landing_secondary">) => {
      const durationMs =
        phase === "landing_primary"
          ? APPROVAL_HIGHLIGHT_PRIMARY_MS
          : APPROVAL_HIGHLIGHT_SECONDARY_MS
      clearApprovalHighlightPhaseTimer()
      setApprovalHighlightPhase(phase)
      setApprovalHighlightSequence((prev) => prev + 1)
      approvalHighlightPhaseTimerRef.current = window.setTimeout(() => {
        approvalHighlightPhaseTimerRef.current = null
        setApprovalHighlightPhase("steady")
      }, durationMs)
    },
    [clearApprovalHighlightPhaseTimer]
  )

  React.useEffect(() => {
    if (!activeApprovalKey) return
    if (pendingApprovals.some((approval) => approval.key === activeApprovalKey)) return
    const nextApprovalKey = pendingApprovals.length ? pendingApprovals[0]?.key || null : null
    setActiveApprovalKey(nextApprovalKey)
    if (nextApprovalKey) {
      triggerApprovalHighlightPhase("landing_secondary")
      return
    }
    resetApprovalHighlightMotion()
  }, [
    activeApprovalKey,
    pendingApprovals,
    resetApprovalHighlightMotion,
    triggerApprovalHighlightPhase
  ])

  React.useEffect(() => {
    if (!resolvedApprovalSnapshot) {
      clearResolvedApprovalFadeTimer()
      return
    }
    if (
      pendingApprovals.length > 0 ||
      pendingApprovals.some((approval) => approval.key === resolvedApprovalSnapshot.key)
    ) {
      clearResolvedApprovalFadeTimer()
      setResolvedApprovalSnapshot(null)
      return
    }
    clearResolvedApprovalFadeTimer()
    resolvedApprovalFadeTimerRef.current = window.setTimeout(() => {
      resolvedApprovalFadeTimerRef.current = null
      setResolvedApprovalSnapshot(null)
    }, RESOLVED_RUNTIME_APPROVAL_FADE_MS)
    return () => {
      clearResolvedApprovalFadeTimer()
    }
  }, [clearResolvedApprovalFadeTimer, pendingApprovals, resolvedApprovalSnapshot])

  React.useEffect(() => {
    return () => {
      clearResolvedApprovalFadeTimer()
    }
  }, [clearResolvedApprovalFadeTimer])

  React.useEffect(() => {
    return () => {
      clearApprovalHighlightPhaseTimer()
    }
  }, [clearApprovalHighlightPhaseTimer])

  React.useEffect(() => {
    const normalizedPersonaId = String(selectedPersonaId || "").trim()
    if (!normalizedPersonaId || isCompanionMode) {
      setSavedPersonaVoiceDefaults(null)
      setSavedPersonaSetup(null)
      setSavedPersonaProfileVersion(null)
      setPersonaProfileLoading(false)
      if (!connected) {
        setLiveSessionVoiceDefaultsBaseline(null)
      }
      return
    }

    let cancelled = false
    setPersonaProfileLoading(true)
    ;(async () => {
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(normalizedPersonaId)}` as any,
          { method: "GET" }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to load persona profile")
        }
        const payload = (await response.json()) as PersonaProfileResponse
        if (!cancelled) {
          setSavedPersonaVoiceDefaults(payload?.voice_defaults || null)
          setSavedPersonaSetup(payload?.setup || null)
          setSavedPersonaProfileVersion(
            typeof payload?.version === "number" ? payload.version : null
          )
        }
      } catch {
        if (!cancelled) {
          setSavedPersonaVoiceDefaults(null)
          setSavedPersonaSetup(null)
          setSavedPersonaProfileVersion(null)
        }
      } finally {
        if (!cancelled) {
          setPersonaProfileLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [connected, isCompanionMode, selectedPersonaId])

  const personaSetupWizard = usePersonaSetupWizard({
    selectedPersonaId,
    isCompanionMode,
    loading: personaProfileLoading,
    setup: savedPersonaSetup
  })
  React.useEffect(() => {
    if (isCompanionMode || !personaSetupWizard.isSetupRequired || catalog.length > 0) {
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const response = await tldwClient.fetchWithAuth("/api/v1/persona/catalog" as any, {
          method: "GET"
        })
        if (!response.ok) return
        const payload = await response.json()
        if (!cancelled) {
          setCatalog(Array.isArray(payload) ? (payload as PersonaInfo[]) : [])
        }
      } catch {
        // Best-effort only for setup persona choice.
      }
    })()

    return () => {
      cancelled = true
    }
  }, [catalog.length, isCompanionMode, personaSetupWizard.isSetupRequired])
  const assistantSetupProgressItems = React.useMemo(
    () =>
      buildPersonaSetupProgress({
        ...(savedPersonaSetup || {}),
        status:
          savedPersonaSetup?.status ||
          (personaSetupWizard.isSetupRequired ? "in_progress" : "not_started"),
        current_step: personaSetupWizard.currentStep,
        completed_steps: Array.isArray(savedPersonaSetup?.completed_steps)
          ? savedPersonaSetup.completed_steps
          : []
      }),
    [
      personaSetupWizard.currentStep,
      personaSetupWizard.isSetupRequired,
      savedPersonaSetup
    ]
  )
  const createSetupRunId = React.useCallback(() => {
    if (
      typeof globalThis !== "undefined" &&
      typeof globalThis.crypto?.randomUUID === "function"
    ) {
      return `setup-run-${globalThis.crypto.randomUUID()}`
    }
    return `setup-run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  }, [])
  const currentSetupRunId = React.useMemo(() => {
    const normalized = String(savedPersonaSetup?.run_id || "").trim()
    return normalized || null
  }, [savedPersonaSetup?.run_id])
  const emitSetupAnalyticsEvent = React.useCallback(
    (event: Omit<PersonaSetupAnalyticsEvent, "runId"> & { runId?: string; personaId?: string }) => {
      const personaId = String(event.personaId || selectedPersonaId || "").trim()
      const runId = String(event.runId || currentSetupRunId || "").trim()
      if (!personaId || !runId) return

      const eventType = event.eventType as PersonaSetupAnalyticsEventType
      const eventKey = buildSetupEventKey({
        eventType,
        step: event.step,
        detourSource: event.detourSource || undefined,
        actionTarget: event.actionTarget || undefined,
        metadata: event.metadata
      })
      if (eventKey) {
        const dedupeKey = `${personaId}:${runId}:${eventKey}`
        if (emittedSetupEventKeysRef.current.has(dedupeKey)) return
        emittedSetupEventKeysRef.current.add(dedupeKey)
      }

      void postPersonaSetupEvent(personaId, {
        runId,
        eventType,
        step: event.step,
        completionType: event.completionType,
        detourSource: event.detourSource || undefined,
        actionTarget: event.actionTarget || undefined,
        metadata: event.metadata
      })
    },
    [currentSetupRunId, selectedPersonaId]
  )
  const setSetupStepError = React.useCallback(
    (step: PersonaSetupStep, message: string | null) => {
      setSetupStepErrors((current) => ({
        ...current,
        [step]: message
      }))
      if (message) {
        emitSetupAnalyticsEvent({
          eventType: "step_error",
          step,
          metadata: { message }
        })
      }
    },
    [emitSetupAnalyticsEvent]
  )
  const clearSetupStepError = React.useCallback(
    (step: PersonaSetupStep) => {
      setSetupStepErrors((current) => {
        if (!current[step]) return current
        return {
          ...current,
          [step]: null
        }
      })
    },
    []
  )
  const clearAllSetupStepErrors = React.useCallback(() => {
    setSetupStepErrors({})
  }, [])
  const currentSetupWizardError =
    personaSetupWizard.currentStep === "commands" ||
    personaSetupWizard.currentStep === "safety" ||
    personaSetupWizard.currentStep === "test"
      ? null
      : setupStepErrors[personaSetupWizard.currentStep] || null
  const resolveSetupReviewSummary = React.useCallback(
    async (personaId: string): Promise<SetupReviewSummary> => {
      if (setupReviewSummaryDraft.confirmationMode !== null) {
        return setupReviewSummaryDraft
      }

      const fallbackSummary: SetupReviewSummary = {
        starterCommands: { mode: "skipped" },
        confirmationMode: savedPersonaVoiceDefaults?.confirmation_mode || null,
        connection: { mode: "skipped" }
      }

      try {
        const [commandsResult, connectionsResult] = await Promise.allSettled([
          tldwClient.fetchWithAuth(
            `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/voice-commands` as any,
            { method: "GET" }
          ),
          tldwClient.fetchWithAuth(
            `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/connections` as any,
            { method: "GET" }
          )
        ])

        if (commandsResult.status === "fulfilled" && commandsResult.value.ok) {
          fallbackSummary.starterCommands = summarizeFallbackStarterCommands(
            await commandsResult.value.json()
          )
        }

        if (connectionsResult.status === "fulfilled" && connectionsResult.value.ok) {
          const connectionName = pickAvailableConnectionName(await connectionsResult.value.json())
          fallbackSummary.connection = connectionName
            ? { mode: "available", name: connectionName }
            : { mode: "skipped" }
        }
      } catch {
        // Handoff summary enrichment is best-effort and should not block setup completion.
      }

      return fallbackSummary
    },
    [savedPersonaVoiceDefaults?.confirmation_mode, setupReviewSummaryDraft]
  )

  React.useEffect(() => {
    const normalizedPersonaId = String(selectedPersonaId || "").trim()
    if (!personaSetupWizard.isSetupRequired || !normalizedPersonaId) {
      return
    }
    if (setupIntentPersonaId !== normalizedPersonaId) {
      setSetupIntentPersonaId(normalizedPersonaId)
      setSetupIntentTargetTab(activeTab)
      setSetupReviewSummaryDraft(DEFAULT_SETUP_REVIEW_SUMMARY)
      return
    }
    if (!setupIntentTargetTab) {
      setSetupIntentTargetTab(activeTab)
    }
  }, [
    activeTab,
    personaSetupWizard.isSetupRequired,
    selectedPersonaId,
    setupIntentPersonaId,
    setupIntentTargetTab
  ])

  React.useEffect(() => {
    if (!personaSetupWizard.isSetupRequired || personaSetupWizard.currentStep === "test") {
      return
    }
    setSetupWizardDryRunLoading(false)
    setSetupTestOutcome(null)
    setSetupTestResumeNote(null)
    setSetupCommandDetour(null)
    setSetupLiveDetour(null)
    setSetupNoMatchPhrase(null)
    setupWizardLastLiveTextRef.current = ""
    setupWizardAwaitingLiveResponseRef.current = false
  }, [personaSetupWizard.currentStep, personaSetupWizard.isSetupRequired])

  React.useEffect(() => {
    if (!personaSetupWizard.isSetupRequired) return
    if (!currentSetupRunId) return
    void emitSetupAnalyticsEvent({
      eventType: "step_viewed",
      step: personaSetupWizard.currentStep,
      runId: currentSetupRunId
    })
  }, [
    currentSetupRunId,
    emitSetupAnalyticsEvent,
    personaSetupWizard.currentStep,
    personaSetupWizard.isSetupRequired
  ])

  const buildPersonaSetupInProgress = React.useCallback(
    (
      step: PersonaSetupState["current_step"] = "voice",
      completedSteps: PersonaSetupStep[] = [],
      options?: { runId?: string | null }
    ): PersonaSetupState => ({
      status: "in_progress",
      version: 1,
      run_id:
        String(options?.runId || savedPersonaSetup?.run_id || "").trim() ||
        createSetupRunId(),
      current_step: step || "voice",
      completed_steps: completedSteps,
      completed_at: null,
      last_test_type: null
    }),
    [createSetupRunId, savedPersonaSetup?.run_id]
  )

  const mergeCompletedSetupSteps = React.useCallback(
    (...steps: Array<PersonaSetupStep | null | undefined>) => {
      const next = new Set<PersonaSetupStep>(
        Array.isArray(savedPersonaSetup?.completed_steps)
          ? savedPersonaSetup.completed_steps
          : []
      )
      for (const step of steps) {
        if (!step) continue
        next.add(step)
      }
      return Array.from(next)
    },
    [savedPersonaSetup?.completed_steps]
  )

  const buildSetupProfileUpdatePath = React.useCallback(
    (personaId: string) => {
      const normalizedPersonaId = String(personaId || "").trim()
      const basePath = `/api/v1/persona/profiles/${encodeURIComponent(normalizedPersonaId)}`
      if (!normalizedPersonaId || !savedPersonaProfileVersion) {
        return basePath
      }
      return `${basePath}?expected_version=${encodeURIComponent(
        String(savedPersonaProfileVersion)
      )}`
    },
    [savedPersonaProfileVersion]
  )

  const applyPersonaProfileResponse = React.useCallback(
    (
      payload: PersonaProfileResponse | null | undefined,
      fallback?: {
        voiceDefaults?: PersonaVoiceDefaults | null
        setup?: PersonaSetupState | null
      }
    ) => {
      if (payload && typeof payload.version === "number") {
        setSavedPersonaProfileVersion(payload.version)
      }
      if (payload?.voice_defaults !== undefined) {
        setSavedPersonaVoiceDefaults(payload.voice_defaults || null)
      } else if (fallback?.voiceDefaults !== undefined) {
        setSavedPersonaVoiceDefaults(fallback.voiceDefaults || null)
      }
      if (payload?.setup !== undefined) {
        setSavedPersonaSetup(payload.setup || null)
      } else if (fallback?.setup !== undefined) {
        setSavedPersonaSetup(fallback.setup || null)
      }
    },
    []
  )

  const handleSetupVoiceDefaultsSaved = React.useCallback(
    async () => {
      const personaId = String(selectedPersonaId || "").trim()
      if (!personaId) return
      setSetupWizardSaving(true)
      clearSetupStepError("voice")
      const nextSetup = buildPersonaSetupInProgress(
        "commands",
        mergeCompletedSetupSteps("voice")
      )
      try {
        const response = await tldwClient.fetchWithAuth(
          buildSetupProfileUpdatePath(personaId) as any,
          {
            method: "PATCH",
            body: {
              setup: nextSetup
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to advance assistant setup")
        }
        const payload = (await response.json()) as PersonaProfileResponse
        applyPersonaProfileResponse(payload, { setup: nextSetup })
        void emitSetupAnalyticsEvent({
          personaId,
          runId: nextSetup.run_id || undefined,
          eventType: "step_completed",
          step: "voice"
        })
      } catch (setupError: any) {
        setSetupStepError(
          "voice",
          String(setupError?.message || "Failed to advance assistant setup")
        )
      } finally {
        setSetupWizardSaving(false)
      }
    },
    [
      applyPersonaProfileResponse,
      buildPersonaSetupInProgress,
      buildSetupProfileUpdatePath,
      clearSetupStepError,
      emitSetupAnalyticsEvent,
      mergeCompletedSetupSteps,
      setSetupStepError,
      selectedPersonaId
    ]
  )

  const advancePersonaSetupStep = React.useCallback(
    async (
      step: PersonaSetupState["current_step"],
      errorMessage: string,
      completedStep?: PersonaSetupStep,
      errorStep: PersonaSetupStep = step || "persona"
    ) => {
      const personaId = String(selectedPersonaId || "").trim()
      if (!personaId) return
      setSetupWizardSaving(true)
      clearSetupStepError(errorStep)
      const nextSetup = buildPersonaSetupInProgress(
        step,
        mergeCompletedSetupSteps(completedStep)
      )
      try {
        const response = await tldwClient.fetchWithAuth(
          buildSetupProfileUpdatePath(personaId) as any,
          {
            method: "PATCH",
            body: {
              setup: nextSetup
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || errorMessage)
        }
        const payload = (await response.json()) as PersonaProfileResponse
        applyPersonaProfileResponse(payload, { setup: nextSetup })
        if (completedStep) {
          void emitSetupAnalyticsEvent({
            personaId,
            runId: nextSetup.run_id || undefined,
            eventType: "step_completed",
            step: completedStep
          })
        }
      } catch (setupError: any) {
        setSetupStepError(errorStep, String(setupError?.message || errorMessage))
      } finally {
        setSetupWizardSaving(false)
      }
    },
    [
      applyPersonaProfileResponse,
      buildPersonaSetupInProgress,
      buildSetupProfileUpdatePath,
      clearSetupStepError,
      emitSetupAnalyticsEvent,
      mergeCompletedSetupSteps,
      setSetupStepError,
      selectedPersonaId
    ]
  )

  const resolvedLivePersonaVoiceDefaults = useResolvedPersonaVoiceDefaults(
    connected ? liveSessionVoiceDefaultsBaseline : savedPersonaVoiceDefaults
  )
  const livePersonaId = connected ? activeSessionPersonaId || selectedPersonaId : selectedPersonaId
  const liveVoiceController = usePersonaLiveVoiceController({
    ws: wsRef.current,
    connected,
    sessionId: sessionId || "",
    personaId: String(livePersonaId || "").trim(),
    resolvedDefaults: resolvedLivePersonaVoiceDefaults,
    canUseServerStt: Boolean(capabilities?.hasAudio)
  })
  liveVoiceControllerRef.current = liveVoiceController

  React.useEffect(() => {
    liveVoiceAnalyticsSnapshotRef.current = {
      personaId: String(livePersonaId || "").trim(),
      sessionId: String(sessionId || "").trim(),
      listeningRecoveryCount: liveVoiceController.listeningRecoveryCount,
      thinkingRecoveryCount: liveVoiceController.thinkingRecoveryCount
    }
  }, [
    livePersonaId,
    liveVoiceController.listeningRecoveryCount,
    liveVoiceController.thinkingRecoveryCount,
    sessionId
  ])

  const flushLiveVoiceSessionAnalytics = React.useCallback(
    (options?: { finalize?: boolean }) => {
      const snapshot = liveVoiceAnalyticsSnapshotRef.current
      const personaId = String(snapshot.personaId || "").trim()
      const activeSessionId = String(snapshot.sessionId || "").trim()
      if (!personaId || !activeSessionId) return
      void tldwClient
        .fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/voice-analytics/live-sessions/${encodeURIComponent(activeSessionId)}` as any,
          {
            method: "PUT",
            body: {
              listening_recovery_count: snapshot.listeningRecoveryCount,
              thinking_recovery_count: snapshot.thinkingRecoveryCount,
              finalize: options?.finalize === true
            }
          }
        )
        .catch(() => {
          // Best-effort flush only; live-session teardown should not be blocked by analytics writes.
        })
    },
    []
  )

  const handleOpenCommandFromTestLab = React.useCallback((
    commandId: string,
    heardText: string
  ) => {
    const normalizedCommandId = String(commandId || "").trim()
    const normalizedHeardText = String(heardText || "").trim()
    if (!normalizedCommandId) return
    setDraftCommandPhrase(null)
    setDraftCommandSource(null)
    setOpenCommandId(normalizedCommandId)
    setRerunAfterSaveCommandId(normalizedCommandId)
    setLastTestLabPhrase(normalizedHeardText)
    setActiveTab("commands")
  }, [])

  const handleCreateCommandFromTestLab = React.useCallback((heardText: string) => {
    const normalizedHeardText = String(heardText || "").trim()
    if (!normalizedHeardText) return
    setOpenCommandId(null)
    setRerunAfterSaveCommandId(null)
    setDraftCommandPhrase(normalizedHeardText)
    setDraftCommandSource("test_lab")
    setLastTestLabPhrase(normalizedHeardText)
    setActiveTab("commands")
  }, [])

  const handleCreateCommandFromSetupNoMatch = React.useCallback((heardText: string) => {
    const normalizedHeardText = String(heardText || "").trim()
    if (!normalizedHeardText) return
    setOpenCommandId(null)
    setRerunAfterSaveCommandId(null)
    setDraftCommandPhrase(normalizedHeardText)
    setDraftCommandSource("setup_no_match")
    setSetupNoMatchPhrase(normalizedHeardText)
    setSetupTestResumeNote(null)
    setSetupCommandDetour({
      phrase: normalizedHeardText,
      returnStep: "test"
    })
    setActiveTab("commands")
    void emitSetupAnalyticsEvent({
      eventType: "detour_started",
      step: "test",
      detourSource: "dry_run_no_match"
    })
  }, [emitSetupAnalyticsEvent])

  const handleRecoverSetupInLiveSession = React.useCallback(
    (context: { source: "live_unavailable" | "live_failure"; text: string }) => {
      setSetupLiveDetour({
        source: context.source,
        lastText: String(context.text || "").trim()
      })
      setSetupTestResumeNote(null)
      setActiveTab("live")
      void emitSetupAnalyticsEvent({
        eventType: "detour_started",
        step: "test",
        detourSource: context.source
      })
      if (context.source === "live_unavailable" && !connected && !connecting) {
        setPendingRecoveryReconnectToken((current) => current + 1)
      }
    },
    [connected, connecting, emitSetupAnalyticsEvent]
  )

  const handleReturnToSetupFromLiveDetour = React.useCallback(() => {
    const detourSource = setupLiveDetour?.source || null
    setSetupLiveDetour(null)
    setupWizardAwaitingLiveResponseRef.current = false
    setSetupTestResumeNote("Live session is still available if you want to retry.")
    if (detourSource) {
      void emitSetupAnalyticsEvent({
        eventType: "detour_returned",
        step: "test",
        detourSource
      })
    }
  }, [emitSetupAnalyticsEvent, setupLiveDetour?.source])

  const handleOpenCommandHandled = React.useCallback((commandId: string) => {
    const normalizedCommandId = String(commandId || "").trim()
    if (!normalizedCommandId) return
    setOpenCommandId((current) =>
      current === normalizedCommandId ? null : current
    )
  }, [])

  const handleDraftCommandPhraseHandled = React.useCallback((heardText: string) => {
    const normalizedHeardText = String(heardText || "").trim()
    if (!normalizedHeardText) return
    setDraftCommandPhrase((current) =>
      current === normalizedHeardText ? null : current
    )
    setDraftCommandSource(null)
  }, [])

  const handleRerunAfterCommandSave = React.useCallback((commandId: string) => {
    const normalizedCommandId = String(commandId || "").trim()
    if (!normalizedCommandId) return
    if (rerunAfterSaveCommandId !== normalizedCommandId) return
    if (String(lastTestLabPhrase || "").trim()) {
      setActiveTab("test-lab")
      setTestLabRerunToken((previous) => previous + 1)
    }
    setRerunAfterSaveCommandId(null)
  }, [lastTestLabPhrase, rerunAfterSaveCommandId])

  const consumeSetupHandoffAction = React.useCallback(
    (action: SetupHandoffConsumedAction) => {
      const currentHandoff = setupHandoffRef.current
      if (!currentHandoff || currentHandoff.compact || currentHandoff.consumedAction) {
        return
      }
      void emitSetupAnalyticsEvent({
        runId: currentHandoff.runId,
        eventType: "first_post_setup_action",
        actionTarget: toSetupHandoffActionTarget(action)
      })
      setSetupHandoff((existing) => {
        if (
          !existing ||
          existing.runId !== currentHandoff.runId ||
          existing.compact ||
          existing.consumedAction
        ) {
          return existing
        }
        return {
          ...existing,
          compact: true,
          consumedAction: action
        }
      })
    },
    [emitSetupAnalyticsEvent]
  )

  const handleSetupDetourCommandSaved = React.useCallback(
    (_commandId: string, context: { fromDraft: boolean }) => {
      if (!setupCommandDetour || !context.fromDraft) return
      if (setupCommandDetour.returnStep !== "test") return
      void emitSetupAnalyticsEvent({
        eventType: "detour_returned",
        step: "test",
        detourSource: "dry_run_no_match"
      })
      setSetupCommandDetour(null)
      setDraftCommandPhrase(null)
      setDraftCommandSource(null)
      setOpenCommandId(null)
      setRerunAfterSaveCommandId(null)
      setSetupTestOutcome(null)
      setSetupWizardDryRunLoading(false)
      setSetupTestResumeNote(
        "Command saved. Run the same phrase again to confirm setup."
      )
      setActiveTab(setupIntentTargetTab || "live")
    },
    [emitSetupAnalyticsEvent, setupCommandDetour, setupIntentTargetTab]
  )

  const handleCommandSaved = React.useCallback(
    (commandId: string, context: { fromDraft: boolean }) => {
      handleSetupDetourCommandSaved(commandId, context)
      consumeSetupHandoffAction("command_saved")
    },
    [consumeSetupHandoffAction, handleSetupDetourCommandSaved]
  )

  React.useEffect(() => {
    let cancelled = false
    const normalizedPersonaId = String(selectedPersonaId || "").trim()
    const shouldLoad =
      normalizedPersonaId.length > 0 &&
      (activeTab === "commands" || activeTab === "test-lab" || activeTab === "profiles")

    if (!normalizedPersonaId) {
      setVoiceAnalytics(null)
      setVoiceAnalyticsLoading(false)
      return
    }
    if (!shouldLoad) return

    if (voiceAnalytics?.persona_id !== normalizedPersonaId) {
      setVoiceAnalytics(null)
    }
    setVoiceAnalyticsLoading(true)

    const loadVoiceAnalytics = async () => {
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(normalizedPersonaId)}/voice-analytics?days=7` as any,
          { method: "GET" }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to load persona voice analytics.")
        }
        const payload = (await response.json()) as PersonaVoiceAnalytics
        if (!cancelled) {
          setVoiceAnalytics(payload)
        }
      } catch {
        if (!cancelled) {
          setVoiceAnalytics(null)
        }
      } finally {
        if (!cancelled) {
          setVoiceAnalyticsLoading(false)
        }
      }
    }

    void loadVoiceAnalytics()
    return () => {
      cancelled = true
    }
  }, [activeTab, selectedPersonaId])

  React.useEffect(() => {
    let cancelled = false
    const normalizedPersonaId = String(selectedPersonaId || "").trim()

    if (!normalizedPersonaId) {
      setSetupAnalytics(null)
      setSetupAnalyticsLoading(false)
      return
    }

    if (setupAnalytics?.persona_id !== normalizedPersonaId) {
      setSetupAnalytics(null)
    }

    if (activeTab !== "profiles") {
      setSetupAnalyticsLoading(false)
      return
    }

    setSetupAnalyticsLoading(true)

    const loadSetupAnalytics = async () => {
      try {
        const response = await tldwClient.fetchWithAuth(
          toAllowedPath(
            `/api/v1/persona/profiles/${encodeURIComponent(normalizedPersonaId)}/setup-analytics?days=30&limit=5`
          ),
          { method: "GET" }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to load persona setup analytics.")
        }
        const payload = (await response.json()) as PersonaSetupAnalyticsResponse
        if (!cancelled) {
          setSetupAnalytics(payload)
        }
      } catch (fetchError) {
        console.warn("tldw_server: failed to load persona setup analytics", {
          personaId: normalizedPersonaId,
          error: fetchError
        })
        if (!cancelled) {
          setSetupAnalytics(null)
        }
      } finally {
        if (!cancelled) {
          setSetupAnalyticsLoading(false)
        }
      }
    }

    void loadSetupAnalytics()
    return () => {
      cancelled = true
    }
  }, [activeTab, selectedPersonaId])

  React.useEffect(() => {
    if (!isCompanionMode || capsLoading || !capabilities?.hasPersonalization) {
      setCompanionPrompts([])
      return
    }

    const promptQuery = input.trim() || DEFAULT_COMPANION_PROMPT_QUERY
    let cancelled = false
    const timeoutId = window.setTimeout(() => {
      fetchCompanionConversationPrompts(promptQuery)
        .then((payload) => {
          if (cancelled) return
          setCompanionPrompts(
            Array.isArray(payload.prompts)
              ? payload.prompts
                  .filter(
                    (item) =>
                      item &&
                      typeof item.prompt_text === "string" &&
                      item.prompt_text.trim().length > 0
                  )
                  .slice(0, 3)
                  .map((item) => ({
                    prompt_id: item.prompt_id,
                    label: item.label,
                    prompt_text: item.prompt_text
                  }))
              : []
          )
        })
        .catch(() => {
          if (!cancelled) {
            setCompanionPrompts([])
          }
        })
    }, input.trim() ? 200 : 0)

    return () => {
      cancelled = true
      window.clearTimeout(timeoutId)
    }
  }, [
    capabilities?.hasPersonalization,
    capsLoading,
    input,
    isCompanionMode
  ])

  const applySessionPreferences = React.useCallback(
    (preferences?: PersonaSessionPreferences | null) => {
      if (!preferences || typeof preferences !== "object") return
      if (typeof preferences.use_memory_context === "boolean") {
        setMemoryEnabled(preferences.use_memory_context)
      }
      if (typeof preferences.memory_top_k !== "undefined") {
        setMemoryTopK((current) =>
          _normalizeMemoryTopK(preferences.memory_top_k, current)
        )
      }
      if (!isCompanionMode && typeof preferences.use_companion_context === "boolean") {
        setCompanionContextEnabled(preferences.use_companion_context)
      }
      if (
        !isCompanionMode &&
        typeof preferences.use_persona_state_context === "boolean"
      ) {
        setPersonaStateContextEnabled(preferences.use_persona_state_context)
      }
    },
    [isCompanionMode]
  )

  const getUnsavedStateDiscardPrompt = React.useCallback(
    (reason: UnsavedStateDiscardReason): string => {
      switch (reason) {
        case "connect":
          return t(
            "sidepanel:persona.unsavedStateDiscardPromptConnect",
            "You have unsaved state-doc changes. Connect and discard local drafts?"
          )
        case "disconnect":
          return t(
            "sidepanel:persona.unsavedStateDiscardPromptDisconnect",
            "You have unsaved state-doc changes. Disconnect and discard local drafts?"
          )
        case "reload_state":
          return t(
            "sidepanel:persona.unsavedStateDiscardPromptReloadState",
            "You have unsaved state-doc changes. Load state and discard local drafts?"
          )
        case "persona_switch":
          return t(
            "sidepanel:persona.unsavedStateDiscardPromptPersonaSwitch",
            "You have unsaved state-doc changes. Switch persona and discard local drafts?"
          )
        case "session_switch":
          return t(
            "sidepanel:persona.unsavedStateDiscardPromptSessionSwitch",
            "You have unsaved state-doc changes. Switch session and discard local drafts?"
          )
        case "restore_state":
          return t(
            "sidepanel:persona.unsavedStateDiscardPromptRestoreState",
            "You have unsaved state-doc changes. Restore this state version and discard local drafts?"
          )
        case "route_transition":
          return t(
            "sidepanel:persona.unsavedStateDiscardPromptRouteTransition",
            "You have unsaved state-doc changes. Leave this page and discard local drafts?"
          )
        case "before_unload":
          return t(
            "sidepanel:persona.unsavedStateBeforeUnloadPrompt",
            "You have unsaved state-doc changes. Leave this page without saving?"
          )
        case "generic":
        default:
          return t(
            "sidepanel:persona.unsavedStateDiscardPrompt",
            "You have unsaved state-doc changes. Discard local drafts?"
          )
      }
    },
    [t]
  )

  const confirmDiscardUnsavedStateDrafts = React.useCallback((reason: UnsavedStateDiscardReason = "generic"): boolean => {
    if (
      soulMd === savedSoulMd &&
      identityMd === savedIdentityMd &&
      heartbeatMd === savedHeartbeatMd
    ) {
      return true
    }
    return _confirmWithBrowserPrompt(getUnsavedStateDiscardPrompt(reason))
  }, [
    getUnsavedStateDiscardPrompt,
    heartbeatMd,
    identityMd,
    savedHeartbeatMd,
    savedIdentityMd,
    savedSoulMd,
    soulMd,
  ])

  const appendLog = React.useCallback(
    (kind: PersonaLogEntry["kind"], text: string) => {
      const trimmed = String(text || "").trim()
      if (!trimmed) return
      setLogs((prev) => [
        ...prev,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          kind,
          text: trimmed
        }
      ])
    },
    []
  )

  const disconnect = React.useCallback((options?: { force?: boolean }) => {
    if (!options?.force && !confirmDiscardUnsavedStateDrafts("disconnect")) {
      return false
    }
    flushLiveVoiceSessionAnalytics({ finalize: true })
    const ws = wsRef.current
    if (!ws) {
      setConnected(false)
      setActiveSessionPersonaId(null)
      setLiveSessionVoiceDefaultsBaseline(null)
      liveVoiceAnalyticsSnapshotRef.current = {
        personaId: "",
        sessionId: "",
        listeningRecoveryCount: 0,
        thinkingRecoveryCount: 0
      }
      return false
    }
    manuallyClosingRef.current = true
    try {
      ws.close()
    } catch {
      // ignore close errors
    }
    wsRef.current = null
    setConnected(false)
    setActiveSessionPersonaId(null)
    setLiveSessionVoiceDefaultsBaseline(null)
    setPersonaStateHistory([])
    setPersonaStateHistoryLoaded(false)
    setActiveApprovalKey(null)
    resetApprovalHighlightMotion()
    clearResolvedApprovalFadeTimer()
    setResolvedApprovalSnapshot(null)
    runtimeApprovalRowRefs.current.clear()
    setPendingApprovals([])
    liveVoiceAnalyticsSnapshotRef.current = {
      personaId: "",
      sessionId: "",
      listeningRecoveryCount: 0,
      thinkingRecoveryCount: 0
    }
    return true
  }, [
    clearResolvedApprovalFadeTimer,
    confirmDiscardUnsavedStateDrafts,
    flushLiveVoiceSessionAnalytics,
    resetApprovalHighlightMotion
  ])

  const handleIncomingPayload = React.useCallback(
    (payload: any) => {
      const eventType = String(payload?.event || payload?.type || "").toLowerCase()
      if (!eventType) return
      liveVoiceController.handlePayload(
        payload && typeof payload === "object"
          ? (payload as Record<string, unknown>)
          : null
      )

      if (eventType === "tool_plan") {
        const planId = String(payload?.plan_id || "")
        const stepsRaw = Array.isArray(payload?.steps) ? payload.steps : []
        const steps: PersonaPlanStep[] = stepsRaw
          .map((step: any, idx: number) => ({
            idx:
              typeof step?.idx === "number"
                ? step.idx
                : Number.parseInt(String(step?.idx ?? idx), 10),
            tool: String(step?.tool || "unknown_tool"),
            args:
              step?.args && typeof step.args === "object"
                ? (step.args as Record<string, unknown>)
                : {},
            description: step?.description ? String(step.description) : undefined,
            why: step?.why ? String(step.why) : undefined,
            policy:
              step?.policy && typeof step.policy === "object"
                ? (step.policy as PersonaToolPolicy)
                : undefined
          }))
          .filter((step) => Number.isFinite(step.idx))

        const nextMap: Record<number, boolean> = {}
        for (const step of steps) {
          nextMap[step.idx] = step.policy?.allow !== false
        }
        setApprovedStepMap(nextMap)
        const memoryPayload =
          payload?.memory && typeof payload.memory === "object"
            ? (payload.memory as PersonaMemoryUsage)
            : undefined
        const companionPayload =
          payload?.companion && typeof payload.companion === "object"
            ? (payload.companion as PersonaCompanionUsage)
            : undefined
        setPendingPlan({
          planId,
          steps,
          memory: memoryPayload,
          companion: companionPayload
        })
        appendLog("tool", `Plan proposed (${steps.length} step${steps.length === 1 ? "" : "s"})`)
        return
      }

      if (eventType === "assistant_delta") {
        const textDelta = String(payload?.text_delta || "").trim()
        if (
          personaSetupWizard.isSetupRequired &&
          personaSetupWizard.currentStep === "test" &&
          setupWizardAwaitingLiveResponseRef.current
        ) {
          if (textDelta) {
            setSetupTestOutcome({
              kind: "live_success",
              text: setupWizardLastLiveTextRef.current,
              responseText: textDelta
            })
            setupWizardAwaitingLiveResponseRef.current = false
            if (setupLiveDetourRef.current) {
              void emitSetupAnalyticsEvent({
                eventType: "detour_returned",
                step: "test",
                detourSource: setupLiveDetourRef.current.source
              })
              setSetupLiveDetour(null)
              setSetupTestResumeNote(
                "Live session responded. Finish setup when you're ready."
              )
            }
          }
        }
        if (
          textDelta &&
          activeTabRef.current === "live" &&
          setupHandoffRef.current &&
          !setupHandoffRef.current.compact
        ) {
          consumeSetupHandoffAction("live_response_received")
        }
        appendLog("assistant", String(payload?.text_delta || ""))
        return
      }

      if (eventType === "partial_transcript") {
        appendLog("user", String(payload?.text_delta || ""))
        return
      }

      if (eventType === "tool_call") {
        appendLog(
          "tool",
          `Calling ${String(payload?.tool || "tool")} (step ${String(payload?.step_idx ?? "?")})`
        )
        return
      }

      if (eventType === "tool_result") {
        const approvalPayload =
          payload?.approval && typeof payload.approval === "object"
            ? (payload.approval as PersonaRuntimeApprovalPayload)
            : null
        if (approvalPayload) {
          const scopeContext = _coerceGovernanceContext(approvalPayload.scope_context)
          const durationOptions = Array.isArray(approvalPayload.duration_options)
            ? approvalPayload.duration_options
                .map((entry) => String(entry || "").trim())
                .filter(
                  (entry): entry is PersonaRuntimeApprovalDuration =>
                    entry === "once" || entry === "session" || entry === "conversation"
                )
            : []
          const request: PersonaRuntimeApprovalRequest = {
            key: _approvalRequestKey(
              approvalPayload,
              payload as Record<string, unknown>
            ),
            approval_policy_id:
              typeof approvalPayload.approval_policy_id === "number"
                ? approvalPayload.approval_policy_id
                : null,
            mode: approvalPayload.mode ? String(approvalPayload.mode) : null,
            tool_name: String(
              approvalPayload.tool_name || payload?.tool || "tool"
            ),
            context_key: String(approvalPayload.context_key || ""),
            conversation_id: approvalPayload.conversation_id
              ? String(approvalPayload.conversation_id)
              : null,
            scope_key: String(approvalPayload.scope_key || ""),
            reason: approvalPayload.reason ? String(approvalPayload.reason) : null,
            duration_options: durationOptions.length ? durationOptions : ["once"],
            selected_duration: durationOptions[0] || "once",
            arguments_summary:
              approvalPayload.arguments_summary &&
              typeof approvalPayload.arguments_summary === "object"
                ? (approvalPayload.arguments_summary as Record<string, unknown>)
                : {},
            scope_context: scopeContext,
            session_id: payload?.session_id ? String(payload.session_id) : sessionId,
            plan_id: payload?.plan_id ? String(payload.plan_id) : null,
            step_idx:
              typeof payload?.step_idx === "number"
                ? payload.step_idx
                : Number.parseInt(String(payload?.step_idx ?? ""), 10),
            step_type: payload?.step_type ? String(payload.step_type) : "mcp_tool",
            tool: payload?.tool ? String(payload.tool) : null,
            args:
              payload?.args && typeof payload.args === "object"
                ? (payload.args as Record<string, unknown>)
                : {},
            why: payload?.why ? String(payload.why) : null,
            description: payload?.description ? String(payload.description) : null
          }
          if (resolvedApprovalSnapshot?.key === request.key) {
            clearResolvedApprovalFadeTimer()
            setResolvedApprovalSnapshot(null)
          }
          setPendingApprovals((prev) => {
            const next = prev.filter((entry) => entry.key !== request.key)
            return [...next, request]
          })
          appendLog("notice", `Runtime approval required for ${request.tool_name}`)
          return
        }
        const governanceContext = _coerceGovernanceContext(
          payload?.external_access ?? payload?.path_scope
        )
        const externalDenyMessage = _formatGovernanceDenyMessage(
          governanceContext,
          payload?.reason_code ? String(payload.reason_code) : null
        )
        if (externalDenyMessage) {
          appendLog("notice", externalDenyMessage)
          return
        }
        const output = payload?.output ?? payload?.result
        const message =
          output == null
            ? JSON.stringify(payload)
            : typeof output === "string"
              ? output
              : JSON.stringify(output)
        appendLog("tool", `Result step ${String(payload?.step_idx ?? "?")}: ${message}`)
        return
      }

      if (eventType === "notice") {
        const reasonCode = String(payload?.reason_code || "").trim().toUpperCase()
        if (
          reasonCode === "VOICE_TURN_PROCESSING" ||
          reasonCode === "VOICE_TOOL_EXECUTION_PROCESSING"
        ) {
          return
        }
        appendLog("notice", String(payload?.message || "notice"))
        return
      }

      if (eventType === "tts_audio") {
        appendLog("notice", "Received persona TTS audio chunk")
      }
    },
    [
      appendLog,
      clearResolvedApprovalFadeTimer,
      consumeSetupHandoffAction,
      emitSetupAnalyticsEvent,
      liveVoiceController,
      personaSetupWizard.currentStep,
      personaSetupWizard.isSetupRequired,
      resolvedApprovalSnapshot,
      sessionId,
    ]
  )
  handleIncomingPayloadRef.current = handleIncomingPayload

  const applyPersonaStatePayload = React.useCallback((payload: PersonaStateDocsResponse) => {
    const nextSoulMd = String(payload?.soul_md ?? "")
    const nextIdentityMd = String(payload?.identity_md ?? "")
    const nextHeartbeatMd = String(payload?.heartbeat_md ?? "")
    setSoulMd(nextSoulMd)
    setIdentityMd(nextIdentityMd)
    setHeartbeatMd(nextHeartbeatMd)
    setSavedSoulMd(nextSoulMd)
    setSavedIdentityMd(nextIdentityMd)
    setSavedHeartbeatMd(nextHeartbeatMd)
    setStateLastModified(payload?.last_modified ? String(payload.last_modified) : null)
  }, [])

  const getTargetPersonaId = React.useCallback(
    (override?: string): string =>
      String(override || (connected ? activeSessionPersonaId : selectedPersonaId) || "").trim(),
    [activeSessionPersonaId, connected, selectedPersonaId]
  )

  const loadPersonaStateDocs = React.useCallback(
    async (personaIdOverride?: string, options?: { silent?: boolean }) => {
      const personaId = getTargetPersonaId(personaIdOverride)
      if (!personaId) return false
      const silent = options?.silent === true
      if (!silent && !confirmDiscardUnsavedStateDrafts("reload_state")) {
        return false
      }
      setPersonaStateLoading(true)
      if (!silent) {
        setError(null)
      }
      try {
        const stateResp = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/state` as any,
          { method: "GET" }
        )
        if (!stateResp.ok) {
          if (!silent) {
            throw new Error(stateResp.error || "Failed to load persona state docs")
          }
          return false
        }
        const statePayload = (await stateResp.json()) as PersonaStateDocsResponse
        applyPersonaStatePayload(statePayload)
        return true
      } catch (err: any) {
        if (!silent) {
          setError(String(err?.message || "Failed to load persona state docs"))
        }
        return false
      } finally {
        setPersonaStateLoading(false)
      }
    },
    [applyPersonaStatePayload, confirmDiscardUnsavedStateDrafts, getTargetPersonaId]
  )

  const loadPersonaStateHistory = React.useCallback(
    async (personaIdOverride?: string) => {
      const personaId = getTargetPersonaId(personaIdOverride)
      if (!personaId) return false
      setPersonaStateHistoryLoading(true)
      setError(null)
      try {
        const historyResp = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/state/history?include_archived=true&limit=30` as any,
          { method: "GET" }
        )
        if (!historyResp.ok) {
          throw new Error(historyResp.error || "Failed to load persona state history")
        }
        const historyPayload = (await historyResp.json()) as PersonaStateHistoryResponse
        const entries = Array.isArray(historyPayload?.entries)
          ? historyPayload.entries
          : []
        setPersonaStateHistory(entries)
        setPersonaStateHistoryLoaded(true)
        return true
      } catch (err: any) {
        setError(String(err?.message || "Failed to load persona state history"))
        return false
      } finally {
        setPersonaStateHistoryLoading(false)
      }
    },
    [getTargetPersonaId]
  )

  const savePersonaStateDocs = React.useCallback(async () => {
    const personaId = getTargetPersonaId()
    if (!personaId || personaStateSaving) return
    if (
      soulMd === savedSoulMd &&
      identityMd === savedIdentityMd &&
      heartbeatMd === savedHeartbeatMd
    ) {
      return true
    }
    setPersonaStateSaving(true)
    setError(null)
    try {
      const toNullable = (value: string): string | null =>
        String(value || "").trim().length > 0 ? value : null
      const saveResp = await tldwClient.fetchWithAuth(
        `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/state` as any,
        {
          method: "PUT",
          body: {
            soul_md: toNullable(soulMd),
            identity_md: toNullable(identityMd),
            heartbeat_md: toNullable(heartbeatMd)
          }
        }
      )
      if (!saveResp.ok) {
        throw new Error(saveResp.error || "Failed to save persona state docs")
      }
      const savePayload = (await saveResp.json()) as PersonaStateDocsResponse
      applyPersonaStatePayload(savePayload)
      if (personaStateHistoryLoaded) {
        void loadPersonaStateHistory(personaId)
      }
      appendLog("notice", "Saved persona state docs")
      return true
    } catch (err: any) {
      setError(String(err?.message || "Failed to save persona state docs"))
      return false
    } finally {
      setPersonaStateSaving(false)
    }
  }, [
    appendLog,
    applyPersonaStatePayload,
    heartbeatMd,
    identityMd,
    getTargetPersonaId,
    loadPersonaStateHistory,
    personaStateHistoryLoaded,
    personaStateSaving,
    savedHeartbeatMd,
    savedIdentityMd,
    savedSoulMd,
    soulMd
  ])

  const restorePersonaStateHistoryEntry = React.useCallback(
    async (entryId: string) => {
      const personaId = getTargetPersonaId()
      const trimmedEntryId = String(entryId || "").trim()
      if (!personaId || !trimmedEntryId || restoringStateEntryId) return false
      if (!confirmDiscardUnsavedStateDrafts("restore_state")) {
        return false
      }
      setRestoringStateEntryId(trimmedEntryId)
      setError(null)
      try {
        const restoreResp = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/state/restore` as any,
          {
            method: "POST",
            body: { entry_id: trimmedEntryId }
          }
        )
        if (!restoreResp.ok) {
          throw new Error(restoreResp.error || "Failed to restore persona state version")
        }
        const restorePayload = (await restoreResp.json()) as PersonaStateDocsResponse
        applyPersonaStatePayload(restorePayload)
        await loadPersonaStateHistory(personaId)
        appendLog("notice", "Restored persona state version")
        return true
      } catch (err: any) {
        setError(String(err?.message || "Failed to restore persona state version"))
        return false
      } finally {
        setRestoringStateEntryId(null)
      }
    },
    [
      appendLog,
      applyPersonaStatePayload,
      confirmDiscardUnsavedStateDrafts,
      getTargetPersonaId,
      loadPersonaStateHistory,
      restoringStateEntryId,
    ]
  )

  const connect = React.useCallback(async () => {
    if (connecting || connected) return
    if (!confirmDiscardUnsavedStateDrafts("connect")) return
    setConnecting(true)
    setError(null)

    try {
      disconnect({ force: true })
      setActiveSessionPersonaId(null)
      setLiveSessionVoiceDefaultsBaseline(null)
      setPendingPlan(null)
      setApprovedStepMap({})
      setPersonaStateHistory([])
      setPersonaStateHistoryLoaded(false)
      setActiveApprovalKey(null)
      resetApprovalHighlightMotion()
      clearResolvedApprovalFadeTimer()
      setResolvedApprovalSnapshot(null)
      runtimeApprovalRowRefs.current.clear()

      const config = await tldwClient.getConfig()
      if (!config) {
        throw new Error("tldw server not configured")
      }

      const catalogResp = await tldwClient.fetchWithAuth("/api/v1/persona/catalog" as any, {
        method: "GET"
      })
      if (!catalogResp.ok) {
        throw new Error(catalogResp.error || "Failed to load persona catalog")
      }
      const catalogPayload = await catalogResp.json()
      const personas = Array.isArray(catalogPayload)
        ? (catalogPayload as PersonaInfo[])
        : []
      setCatalog(personas)

      const preferredPersonaId = isCompanionMode
        ? DEFAULT_PERSONA_ID
        : routeBootstrap.personaId || selectedPersonaId
      const selectedPersonaIsValid = personas.some(
        (persona) => String(persona.id || "") === preferredPersonaId
      )
      const resolvedPersonaId =
        (selectedPersonaIsValid ? preferredPersonaId : personas[0]?.id) ||
        preferredPersonaId ||
        DEFAULT_PERSONA_ID
      if (resolvedPersonaId && resolvedPersonaId !== selectedPersonaId) {
        setSelectedPersonaId(resolvedPersonaId)
      }
      if (isCompanionMode) {
        setCompanionContextEnabled(true)
        setPersonaStateContextEnabled(false)
        setPersonaStateContextProfileDefault(false)
      } else {
        setPersonaStateContextEnabled(true)
        setPersonaStateContextProfileDefault(true)
        let nextSavedVoiceDefaults = savedPersonaVoiceDefaults
        try {
          const profileResp = await tldwClient.fetchWithAuth(
            `/api/v1/persona/profiles/${encodeURIComponent(resolvedPersonaId)}` as any,
            { method: "GET" }
          )
          if (profileResp.ok) {
            const profilePayload = (await profileResp.json()) as PersonaProfileResponse
            const stateContextDefault =
              profilePayload?.use_persona_state_context_default !== false
            setPersonaStateContextEnabled(stateContextDefault)
            setPersonaStateContextProfileDefault(stateContextDefault)
            nextSavedVoiceDefaults = profilePayload?.voice_defaults || null
            setSavedPersonaVoiceDefaults(nextSavedVoiceDefaults)
            setSavedPersonaProfileVersion(
              typeof profilePayload?.version === "number" ? profilePayload.version : null
            )
          }
        } catch {
          // profile fetch is optional for route initialization
        }
        setLiveSessionVoiceDefaultsBaseline(nextSavedVoiceDefaults || null)
        void loadPersonaStateDocs(resolvedPersonaId, { silent: true })
      }

      const sessionsResp = await tldwClient.fetchWithAuth(
        `/api/v1/persona/sessions?persona_id=${encodeURIComponent(resolvedPersonaId)}${
          isCompanionMode
            ? `&surface=${encodeURIComponent("companion.conversation")}`
            : ""
        }&limit=50` as any,
        {
          method: "GET"
        }
      )
      let sessionsPayload: PersonaSessionSummary[] = []
      if (sessionsResp.ok) {
        const sessionsJson = await sessionsResp.json()
        sessionsPayload = Array.isArray(sessionsJson)
          ? (sessionsJson as PersonaSessionSummary[])
          : []
      }
      setSessionHistory(sessionsPayload)

      const sessionResp = await tldwClient.fetchWithAuth("/api/v1/persona/session" as any, {
        method: "POST",
        body: {
          persona_id: resolvedPersonaId,
          resume_session_id: resumeSessionId || undefined,
          surface: isCompanionMode ? "companion.conversation" : undefined
        }
      })
      if (!sessionResp.ok) {
        throw new Error(sessionResp.error || "Failed to create persona session")
      }
      const sessionPayload = await sessionResp.json()
      const nextSessionId = String(sessionPayload?.session_id || "").trim()
      if (!nextSessionId) {
        throw new Error("Persona session response missing session_id")
      }
      const connectedPersonaId =
        String(sessionPayload?.persona?.id || resolvedPersonaId || "").trim() ||
        resolvedPersonaId
      setActiveSessionPersonaId(connectedPersonaId)
      if (connectedPersonaId && connectedPersonaId !== selectedPersonaId) {
        setSelectedPersonaId(connectedPersonaId)
      }
      setSessionId(nextSessionId)
      setResumeSessionId(nextSessionId)
      try {
        const sessionDetailResp = await tldwClient.fetchWithAuth(
          `/api/v1/persona/sessions/${encodeURIComponent(nextSessionId)}?limit_turns=0` as any,
          { method: "GET" }
        )
        if (sessionDetailResp.ok) {
          const sessionDetailPayload =
            (await sessionDetailResp.json()) as PersonaSessionDetailResponse
          applySessionPreferences(sessionDetailPayload?.preferences)
        }
      } catch {
        // session detail hydration is best-effort during connect
      }
      if (!sessionsPayload.some((item) => item.session_id === nextSessionId)) {
        setSessionHistory((prev) => [{ session_id: nextSessionId }, ...prev])
      }

      const ws = new WebSocket(buildPersonaWebSocketUrl(config))
      ws.binaryType = "arraybuffer"
      wsRef.current = ws
      manuallyClosingRef.current = false

      ws.onopen = () => {
        setConnected(true)
        appendLog("notice", "Persona stream connected")
      }

      ws.onmessage = (event) => {
        if (typeof event.data !== "string") {
          if (event.data instanceof ArrayBuffer) {
            liveVoiceControllerRef.current?.handleBinaryPayload(event.data)
            return
          }
          appendLog("notice", "Received binary persona stream payload")
          return
        }
        try {
          const payload = JSON.parse(event.data)
          handleIncomingPayloadRef.current(payload)
        } catch {
          appendLog("notice", event.data)
        }
      }

      ws.onerror = () => {
        setError("Persona stream error")
      }

      ws.onclose = () => {
        wsRef.current = null
        setConnected(false)
        const manual = manuallyClosingRef.current
        manuallyClosingRef.current = false
        if (!manual) {
          appendLog("notice", "Persona stream disconnected")
        }
      }
    } catch (err: any) {
      const message = String(err?.message || "Failed to connect persona stream")
      if (
        personaSetupWizard.isSetupRequired &&
        personaSetupWizard.currentStep === "test" &&
        !connected
      ) {
        setSetupTestOutcome({ kind: "live_unavailable" })
      }
      setError(message)
      appendLog("notice", message)
    } finally {
      setConnecting(false)
    }
  }, [
    appendLog,
    clearResolvedApprovalFadeTimer,
    confirmDiscardUnsavedStateDrafts,
    connected,
    connecting,
    disconnect,
    isCompanionMode,
    loadPersonaStateDocs,
    applySessionPreferences,
    personaSetupWizard.currentStep,
    personaSetupWizard.isSetupRequired,
    resetApprovalHighlightMotion,
    resumeSessionId,
    routeBootstrap.personaId,
    savedPersonaVoiceDefaults,
    selectedPersonaId
  ])

  React.useEffect(() => {
    if (!pendingRecoveryReconnectToken) return
    if (connected || connecting) return
    setPendingRecoveryReconnectToken(0)
    void connect()
  }, [connect, connected, connecting, pendingRecoveryReconnectToken])

  const handleCopyLastVoiceCommandToComposer = React.useCallback(() => {
    const nextValue = String(liveVoiceController.lastCommittedText || "").trim()
    if (!nextValue) return
    setInput(nextValue)
  }, [liveVoiceController.lastCommittedText])

  const handleReconnectPersonaSessionFromRecovery = React.useCallback(() => {
    if (connecting) return
    liveVoiceController.resetTurn()
    setPendingRecoveryReconnectToken((current) => current + 1)
    disconnect({ force: true })
  }, [connecting, disconnect, liveVoiceController])

  React.useEffect(() => {
    return () => {
      const ws = wsRef.current
      flushLiveVoiceSessionAnalytics({ finalize: true })
      if (!ws) return
      manuallyClosingRef.current = true
      try {
        ws.close()
      } catch {
        // ignore close errors
      }
      wsRef.current = null
      liveVoiceAnalyticsSnapshotRef.current = {
        personaId: "",
        sessionId: "",
        listeningRecoveryCount: 0,
        thinkingRecoveryCount: 0
      }
    }
  }, [flushLiveVoiceSessionAnalytics])

  const canSend = connected && Boolean(sessionId) && Boolean(input.trim())
  const canSaveCompanionCheckIn =
    Boolean(input.trim()) &&
    Boolean(capabilities?.hasPersonalization) &&
    !savingCompanionCheckIn
  const hasUnsavedPersonaStateChanges =
    soulMd !== savedSoulMd ||
    identityMd !== savedIdentityMd ||
    heartbeatMd !== savedHeartbeatMd
  const routeNavigationBlocker = useCompatibleRouteBlocker(
    hasUnsavedPersonaStateChanges
  )
  const stateDirtyLabel = hasUnsavedPersonaStateChanges
    ? t("sidepanel:persona.stateDirty", "unsaved")
    : t("sidepanel:persona.stateSaved", "saved")
  const stateEditorToggleLabel = personaStateEditorExpanded
    ? t("sidepanel:persona.stateEditorHide", "Hide editor")
    : t("sidepanel:persona.stateEditorShow", "Show editor")
  const orderedPersonaStateHistory = React.useMemo(() => {
    const sorted = [...personaStateHistory].sort(
      (left, right) => _historyEntrySortEpoch(left) - _historyEntrySortEpoch(right)
    )
    if (personaStateHistoryOrder === "newest") {
      sorted.reverse()
    }
    return sorted
  }, [personaStateHistory, personaStateHistoryOrder])

  const revertPersonaStateDraft = React.useCallback(() => {
    setSoulMd(savedSoulMd)
    setIdentityMd(savedIdentityMd)
    setHeartbeatMd(savedHeartbeatMd)
  }, [savedHeartbeatMd, savedIdentityMd, savedSoulMd])

  React.useEffect(() => {
    if (routeNavigationBlocker.state !== "blocked") return
    if (confirmDiscardUnsavedStateDrafts("route_transition")) {
      routeNavigationBlocker.proceed()
    } else {
      routeNavigationBlocker.reset()
    }
  }, [confirmDiscardUnsavedStateDrafts, routeNavigationBlocker])

  React.useEffect(() => {
    if (typeof window === "undefined" || !hasUnsavedPersonaStateChanges) return
    const promptMessage = getUnsavedStateDiscardPrompt("before_unload")
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = promptMessage
      return promptMessage
    }
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
    }
  }, [getUnsavedStateDiscardPrompt, hasUnsavedPersonaStateChanges])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(
        PERSONA_STATE_EDITOR_EXPANDED_PREF_KEY,
        personaStateEditorExpanded ? "true" : "false"
      )
    } catch {
      // ignore storage access errors
    }
  }, [personaStateEditorExpanded])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(
        PERSONA_STATE_HISTORY_ORDER_PREF_KEY,
        personaStateHistoryOrder
      )
    } catch {
      // ignore storage access errors
    }
  }, [personaStateHistoryOrder])

  const updatePersonaStateContextDefault = React.useCallback(
    async (nextDefault: boolean) => {
      const personaId = getTargetPersonaId()
      if (!personaId || updatingPersonaStateContextDefault || !connected) return
      const previousDefault = personaStateContextProfileDefault
      const previousEnabled = personaStateContextEnabled
      setPersonaStateContextProfileDefault(nextDefault)
      setPersonaStateContextEnabled(nextDefault)
      setUpdatingPersonaStateContextDefault(true)
      setError(null)

      try {
        const updateResp = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}` as any,
          {
            method: "PATCH",
            body: { use_persona_state_context_default: nextDefault }
          }
        )
        if (!updateResp.ok) {
          throw new Error(
            updateResp.error || "Failed to update persona state context default"
          )
        }
        const profilePayload = (await updateResp.json()) as PersonaProfileResponse
        const persistedDefault =
          profilePayload?.use_persona_state_context_default !== false
        setPersonaStateContextProfileDefault(persistedDefault)
        setPersonaStateContextEnabled(persistedDefault)
      } catch (err: any) {
        setPersonaStateContextProfileDefault(previousDefault)
        setPersonaStateContextEnabled(previousEnabled)
        setError(String(err?.message || "Failed to update persona state context default"))
      } finally {
        setUpdatingPersonaStateContextDefault(false)
      }
    },
    [
      connected,
      getTargetPersonaId,
      personaStateContextEnabled,
      personaStateContextProfileDefault,
      updatingPersonaStateContextDefault
    ]
  )

  const handlePersonaSelectionChange = React.useCallback(
    (value: string) => {
      const nextPersonaId = String(value || "").trim()
      if (!nextPersonaId || nextPersonaId === selectedPersonaId) return
      if (!confirmDiscardUnsavedStateDrafts("persona_switch")) return
      setSelectedPersonaId(nextPersonaId)
    },
    [confirmDiscardUnsavedStateDrafts, selectedPersonaId]
  )

  const handleUsePersonaForSetup = React.useCallback(
    async (personaId: string) => {
      const nextPersonaId = String(personaId || "").trim()
      if (!nextPersonaId) return
      if (nextPersonaId !== selectedPersonaId && !confirmDiscardUnsavedStateDrafts("persona_switch")) {
        return
      }
      setSetupWizardSaving(true)
      clearSetupStepError("persona")
      const nextSetup = buildPersonaSetupInProgress("voice", ["persona"], {
        runId: createSetupRunId()
      })
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(nextPersonaId)}` as any,
          {
            method: "PATCH",
            body: {
              setup: nextSetup
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to update persona setup")
        }
        const payload = (await response.json()) as PersonaProfileResponse
        setSelectedPersonaId(nextPersonaId)
        applyPersonaProfileResponse(payload, {
          setup: nextSetup,
          voiceDefaults: payload?.voice_defaults || null
        })
        void emitSetupAnalyticsEvent({
          personaId: nextPersonaId,
          runId: nextSetup.run_id || undefined,
          eventType: "setup_started"
        })
        void emitSetupAnalyticsEvent({
          personaId: nextPersonaId,
          runId: nextSetup.run_id || undefined,
          eventType: "step_completed",
          step: "persona"
        })
      } catch (setupError: any) {
        setSetupStepError(
          "persona",
          String(setupError?.message || "Failed to update persona setup")
        )
      } finally {
        setSetupWizardSaving(false)
      }
    },
    [
      applyPersonaProfileResponse,
      buildPersonaSetupInProgress,
      clearSetupStepError,
      confirmDiscardUnsavedStateDrafts,
      createSetupRunId,
      emitSetupAnalyticsEvent,
      setSetupStepError,
      selectedPersonaId
    ]
  )

  const handleCreatePersonaForSetup = React.useCallback(
    async (name: string) => {
      const normalizedName = String(name || "").trim()
      if (!normalizedName) return
      setSetupWizardSaving(true)
      clearSetupStepError("persona")
      const nextSetup = buildPersonaSetupInProgress("voice", ["persona"], {
        runId: createSetupRunId()
      })
      try {
        const response = await tldwClient.fetchWithAuth(
          "/api/v1/persona/profiles" as any,
          {
            method: "POST",
            body: {
              name: normalizedName,
              mode: "persistent_scoped",
              setup: nextSetup
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to create persona")
        }
        const payload = (await response.json()) as PersonaProfileResponse
        const createdPersonaId = String(payload?.id || "").trim()
        if (createdPersonaId) {
          setCatalog((current) => {
            const exists = current.some((persona) => String(persona.id || "") === createdPersonaId)
            if (exists) return current
            return [
              ...current,
              {
                id: createdPersonaId,
                name: normalizedName
              }
            ]
          })
          setSelectedPersonaId(createdPersonaId)
        }
        applyPersonaProfileResponse(payload, {
          setup: nextSetup,
          voiceDefaults: payload?.voice_defaults || null
        })
        void emitSetupAnalyticsEvent({
          personaId: createdPersonaId || selectedPersonaId,
          runId: nextSetup.run_id || undefined,
          eventType: "setup_started"
        })
        void emitSetupAnalyticsEvent({
          personaId: createdPersonaId || selectedPersonaId,
          runId: nextSetup.run_id || undefined,
          eventType: "step_completed",
          step: "persona"
        })
      } catch (setupError: any) {
        setSetupStepError(
          "persona",
          String(setupError?.message || "Failed to create persona")
        )
      } finally {
        setSetupWizardSaving(false)
      }
    },
    [
      applyPersonaProfileResponse,
      buildPersonaSetupInProgress,
      clearSetupStepError,
      createSetupRunId,
      emitSetupAnalyticsEvent,
      selectedPersonaId,
      setSetupStepError
    ]
  )

  const handleCreateStarterCommandFromTemplate = React.useCallback(
    async (templateKey: string) => {
      const personaId = String(selectedPersonaId || "").trim()
      if (!personaId) return
      const template = getPersonaStarterCommandTemplate(templateKey)
      if (!template) return
      setSetupWizardSaving(true)
      clearSetupStepError("commands")
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/voice-commands` as any,
          {
            method: "POST",
            body: {
              name: template.name,
              description: template.commandDescription,
              phrases: template.phrases,
              action_type: "mcp_tool",
              action_config: {
                tool_name: template.toolName
              },
              priority: 50,
              enabled: true,
              requires_confirmation: template.requiresConfirmation
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to create starter command")
        }
        setSetupReviewSummaryDraft((current) => ({
          ...current,
          starterCommands: { mode: "added", count: 1 }
        }))
        await advancePersonaSetupStep(
          "safety",
          "Failed to advance assistant setup",
          "commands",
          "commands"
        )
      } catch (setupError: any) {
        setSetupStepError(
          "commands",
          String(setupError?.message || "Failed to create starter command")
        )
        setSetupWizardSaving(false)
      }
    },
    [advancePersonaSetupStep, clearSetupStepError, selectedPersonaId, setSetupStepError]
  )

  const handleCreateMcpStarterCommand = React.useCallback(
    async (toolName: string, phrase: string) => {
      const personaId = String(selectedPersonaId || "").trim()
      const normalizedToolName = String(toolName || "").trim()
      const normalizedPhrase = String(phrase || "").trim()
      if (!personaId || !normalizedToolName || !normalizedPhrase) return
      setSetupWizardSaving(true)
      clearSetupStepError("commands")
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/voice-commands` as any,
          {
            method: "POST",
            body: {
              name: normalizedPhrase.charAt(0).toUpperCase() + normalizedPhrase.slice(1),
              description: `Run ${normalizedToolName} from assistant setup`,
              phrases: [normalizedPhrase],
              action_type: "mcp_tool",
              action_config: {
                tool_name: normalizedToolName
              },
              priority: 50,
              enabled: true,
              requires_confirmation: false
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to create starter command")
        }
        setSetupReviewSummaryDraft((current) => ({
          ...current,
          starterCommands: { mode: "added", count: 1 }
        }))
        await advancePersonaSetupStep(
          "safety",
          "Failed to advance assistant setup",
          "commands",
          "commands"
        )
      } catch (setupError: any) {
        setSetupStepError(
          "commands",
          String(setupError?.message || "Failed to create starter command")
        )
        setSetupWizardSaving(false)
      }
    },
    [advancePersonaSetupStep, clearSetupStepError, selectedPersonaId, setSetupStepError]
  )

  const handleSetupSafetyStepContinue = React.useCallback(
    async ({
      confirmationMode,
      connectionMode,
      connection
    }: {
      confirmationMode: PersonaConfirmationMode
      connectionMode: "none" | "create"
      connection?: SetupSafetyConnectionDraft
    }) => {
      const personaId = String(selectedPersonaId || "").trim()
      if (!personaId) return
      setSetupWizardSaving(true)
      clearSetupStepError("safety")
      try {
        if (connectionMode === "create") {
          const normalizedName = String(connection?.name || "").trim()
          const normalizedBaseUrl = String(connection?.baseUrl || "").trim()
          if (!normalizedName || !normalizedBaseUrl) {
            throw new Error("Connection name and base URL are required.")
          }
          const connectionResponse = await tldwClient.fetchWithAuth(
            `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/connections` as any,
            {
              method: "POST",
              body: {
                name: normalizedName,
                base_url: normalizedBaseUrl,
                auth_type: String(connection?.authType || "none").trim() || "none",
                secret: String(connection?.secret || "").trim() || undefined
              }
            }
          )
          if (!connectionResponse.ok) {
            throw new Error(connectionResponse.error || "Failed to create setup connection")
          }
        }

        const mergedVoiceDefaults: PersonaVoiceDefaults = {
          ...(savedPersonaVoiceDefaults || {}),
          confirmation_mode: confirmationMode
        }
        const response = await tldwClient.fetchWithAuth(
          buildSetupProfileUpdatePath(personaId) as any,
          {
            method: "PATCH",
            body: {
              voice_defaults: mergedVoiceDefaults,
              setup: buildPersonaSetupInProgress(
                "test",
                mergeCompletedSetupSteps("safety")
              )
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to save assistant safety settings")
        }
        const payload = (await response.json()) as PersonaProfileResponse
        setSetupReviewSummaryDraft((current) => ({
          ...current,
          confirmationMode,
          connection:
            connectionMode === "create" && String(connection?.name || "").trim()
              ? {
                  mode: "created",
                  name: String(connection?.name || "").trim()
                }
              : { mode: "skipped" }
        }))
        applyPersonaProfileResponse(payload, {
          voiceDefaults: mergedVoiceDefaults,
          setup: buildPersonaSetupInProgress("test", mergeCompletedSetupSteps("safety"))
        })
        void emitSetupAnalyticsEvent({
          personaId,
          eventType: "step_completed",
          step: "safety"
        })
      } catch (setupError: any) {
        setSetupStepError(
          "safety",
          String(setupError?.message || "Failed to save assistant safety settings")
        )
      } finally {
        setSetupWizardSaving(false)
      }
    },
    [
      applyPersonaProfileResponse,
      buildPersonaSetupInProgress,
      buildSetupProfileUpdatePath,
      clearSetupStepError,
      emitSetupAnalyticsEvent,
      mergeCompletedSetupSteps,
      savedPersonaVoiceDefaults,
      setSetupStepError,
      selectedPersonaId
    ]
  )

  const completePersonaSetup = React.useCallback(
    async (testType: "dry_run" | "live_session") => {
      const personaId = String(selectedPersonaId || "").trim()
      if (!personaId) return
      setSetupWizardSaving(true)
      clearSetupStepError("test")
      try {
        const resolvedReviewSummary = await resolveSetupReviewSummary(personaId)
        const resolvedRunId =
          String(savedPersonaSetup?.run_id || "").trim() || createSetupRunId()
        const completedSetup: PersonaSetupState = {
          status: "completed",
          version: 1,
          run_id: resolvedRunId,
          current_step: "test",
          completed_steps: ["persona", "voice", "commands", "safety", "test"],
          completed_at: new Date().toISOString(),
          last_test_type: testType
        }
        const response = await tldwClient.fetchWithAuth(
          buildSetupProfileUpdatePath(personaId) as any,
          {
            method: "PATCH",
            body: {
              setup: completedSetup
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to complete assistant setup")
        }
        const payload = (await response.json()) as PersonaProfileResponse
        applyPersonaProfileResponse(payload, { setup: completedSetup })
        const handoffTargetTab = setupIntentTargetTab || activeTab
        const recommendedAction = deriveSetupHandoffRecommendedAction({
          completionType: testType,
          reviewSummary: resolvedReviewSummary
        })
        setActiveTab(handoffTargetTab)
        setSetupHandoff({
          runId: resolvedRunId,
          targetTab: handoffTargetTab,
          completionType: testType,
          reviewSummary: resolvedReviewSummary,
          recommendedAction,
          consumedAction: null,
          compact: false
        })
        void emitSetupAnalyticsEvent({
          personaId,
          runId: resolvedRunId,
          eventType: "step_completed",
          step: "test"
        })
        void emitSetupAnalyticsEvent({
          personaId,
          runId: resolvedRunId,
          eventType: "setup_completed",
          step: "test",
          completionType: testType
        })
        setSetupIntentPersonaId("")
        setSetupIntentTargetTab(null)
        setSetupTestOutcome(null)
        setSetupTestResumeNote(null)
        setSetupCommandDetour(null)
        setSetupLiveDetour(null)
        setSetupNoMatchPhrase(null)
        setupWizardLastLiveTextRef.current = ""
      } catch (setupError: any) {
        setSetupStepError(
          "test",
          String(setupError?.message || "Failed to complete assistant setup")
        )
      } finally {
        setSetupWizardSaving(false)
      }
    },
    [
      applyPersonaProfileResponse,
      activeTab,
      buildSetupProfileUpdatePath,
      clearSetupStepError,
      createSetupRunId,
      emitSetupAnalyticsEvent,
      resolveSetupReviewSummary,
      savedPersonaSetup?.run_id,
      selectedPersonaId,
      setupIntentTargetTab,
      setSetupHandoff,
      setSetupStepError
    ]
  )

  const restartPersonaSetupFromPersonaStep = React.useCallback(
    async (errorMessage: string) => {
      const personaId = String(selectedPersonaId || "").trim()
      if (!personaId) return
      const nextSetup = buildPersonaSetupInProgress("persona", [], {
        runId: createSetupRunId()
      })
      setSetupWizardSaving(true)
      clearAllSetupStepErrors()
      setSetupIntentPersonaId(personaId)
      setSetupIntentTargetTab(activeTab)
      setSetupTestOutcome(null)
      setSetupTestResumeNote(null)
      setSetupCommandDetour(null)
      setSetupLiveDetour(null)
      setSetupNoMatchPhrase(null)
      setSetupReviewSummaryDraft(DEFAULT_SETUP_REVIEW_SUMMARY)
      setupWizardLastLiveTextRef.current = ""
      setSetupHandoff(null)
      setupWizardAwaitingLiveResponseRef.current = false
      try {
        const response = await tldwClient.fetchWithAuth(
          buildSetupProfileUpdatePath(personaId) as any,
          {
            method: "PATCH",
            body: {
              setup: nextSetup
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || errorMessage)
        }
        const payload = (await response.json()) as PersonaProfileResponse
        applyPersonaProfileResponse(payload, { setup: nextSetup })
        void emitSetupAnalyticsEvent({
          personaId,
          runId: nextSetup.run_id || undefined,
          eventType: "setup_started"
        })
      } catch (setupError: any) {
        setSetupStepError("persona", String(setupError?.message || errorMessage))
      } finally {
        setSetupWizardSaving(false)
      }
    },
    [
      activeTab,
      applyPersonaProfileResponse,
      buildPersonaSetupInProgress,
      buildSetupProfileUpdatePath,
      clearAllSetupStepErrors,
      createSetupRunId,
      emitSetupAnalyticsEvent,
      selectedPersonaId,
      setSetupHandoff,
      setSetupStepError
    ]
  )

  const handleStartSetup = React.useCallback(() => {
    void restartPersonaSetupFromPersonaStep("Failed to start assistant setup")
  }, [restartPersonaSetupFromPersonaStep])

  const handleResumeSetup = React.useCallback(() => {
    const personaId = String(selectedPersonaId || "").trim()
    if (!personaId) return
    setSetupIntentPersonaId(personaId)
    setSetupIntentTargetTab(activeTab)
    clearSetupStepError(savedPersonaSetup?.current_step || "persona")
  }, [activeTab, clearSetupStepError, savedPersonaSetup?.current_step, selectedPersonaId])

  const handleResetSetup = React.useCallback(() => {
    void restartPersonaSetupFromPersonaStep("Failed to reset assistant setup")
  }, [restartPersonaSetupFromPersonaStep])

  const handleRerunSetup = React.useCallback(() => {
    void restartPersonaSetupFromPersonaStep("Failed to rerun assistant setup")
  }, [restartPersonaSetupFromPersonaStep])

  const handleRunSetupDryRun = React.useCallback(
    async (heardText: string) => {
      const personaId = String(selectedPersonaId || "").trim()
      const normalizedHeardText = String(heardText || "").trim()
      if (!personaId || !normalizedHeardText) return
      setSetupWizardDryRunLoading(true)
      clearSetupStepError("test")
      setSetupTestResumeNote(null)
      setSetupTestOutcome(null)
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(personaId)}/voice-commands/test` as any,
          {
            method: "POST",
            body: {
              heard_text: normalizedHeardText
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to run setup dry-run")
        }
        const payload = (await response.json()) as {
          heard_text?: string
          matched?: boolean
          command_name?: string | null
          failure_phase?: string | null
        }
        const resolvedHeardText = String(payload?.heard_text || normalizedHeardText)
        if (payload?.matched === false) {
          setSetupTestOutcome({
            kind: "dry_run_no_match",
            heardText: resolvedHeardText,
            failurePhase: payload?.failure_phase || null
          })
        } else {
          setSetupTestOutcome({
            kind: "dry_run_match",
            heardText: resolvedHeardText,
            commandName: payload?.command_name || null
          })
        }
      } catch (setupError: any) {
        setSetupTestOutcome({
          kind: "dry_run_failure",
          message: String(setupError?.message || "Failed to run setup dry-run")
        })
      } finally {
        setSetupWizardDryRunLoading(false)
      }
    },
    [clearSetupStepError, selectedPersonaId]
  )

  const handleResumeSessionSelectionChange = React.useCallback(
    (value: string) => {
      const nextResumeSessionId = value === "__new__" ? "" : String(value)
      if (nextResumeSessionId === resumeSessionId) return
      if (!confirmDiscardUnsavedStateDrafts("session_switch")) return
      setResumeSessionId(nextResumeSessionId)
    },
    [confirmDiscardUnsavedStateDrafts, resumeSessionId]
  )

  const sendUserMessage = React.useCallback(() => {
    if (!canSend || !sessionId || !wsRef.current) return
    const trimmed = input.trim()
    try {
      wsRef.current.send(
        JSON.stringify({
          type: "user_message",
          session_id: sessionId,
          text: trimmed,
          use_memory_context: memoryEnabled,
          use_companion_context: companionContextEnabled,
          use_persona_state_context: personaStateContextEnabled,
          memory_top_k: memoryTopK
        })
      )
      if (personaSetupWizard.isSetupRequired && setupLiveDetour) {
        setupWizardAwaitingLiveResponseRef.current = true
        setupWizardLastLiveTextRef.current = trimmed
      }
      appendLog("user", trimmed)
      setInput("")
    } catch (err: any) {
      setError(String(err?.message || "Failed to send message"))
    }
  }, [
    appendLog,
    canSend,
    companionContextEnabled,
    input,
    memoryEnabled,
    memoryTopK,
    personaStateContextEnabled,
    personaSetupWizard.isSetupRequired,
    sessionId,
    setupLiveDetour
  ])

  const sendSetupLiveTestMessage = React.useCallback(
    (text: string) => {
      const trimmed = String(text || "").trim()
      if (!trimmed) return
      clearSetupStepError("test")
      if (!connected || !sessionId || !wsRef.current) {
        setSetupTestOutcome({ kind: "live_unavailable" })
        return
      }
      try {
        wsRef.current.send(
          JSON.stringify({
            type: "user_message",
            session_id: sessionId,
            text: trimmed,
            use_memory_context: memoryEnabled,
            use_companion_context: companionContextEnabled,
            use_persona_state_context: personaStateContextEnabled,
            memory_top_k: memoryTopK
          })
        )
        setupWizardAwaitingLiveResponseRef.current = true
        setupWizardLastLiveTextRef.current = trimmed
        setSetupTestOutcome({
          kind: "live_sent",
          text: trimmed
        })
        appendLog("user", trimmed)
      } catch (err: any) {
        setSetupTestOutcome({
          kind: "live_failure",
          text: trimmed,
          message: String(err?.message || "Failed to send setup live test")
        })
      }
    },
    [
      appendLog,
      clearSetupStepError,
      companionContextEnabled,
      connected,
      memoryEnabled,
      memoryTopK,
      personaStateContextEnabled,
      setSetupTestOutcome,
      sessionId
    ]
  )

  const saveCompanionCheckIn = React.useCallback(async () => {
    const trimmed = input.trim()
    if (!trimmed || savingCompanionCheckIn || !capabilities?.hasPersonalization) return
    setSavingCompanionCheckIn(true)
    setError(null)
    try {
      const response = await tldwClient.fetchWithAuth("/api/v1/companion/check-ins" as any, {
        method: "POST",
        body: {
          summary: trimmed,
          surface: isCompanionMode ? "companion.conversation" : "persona.sidepanel"
        }
      })
      if (!response.ok) {
        if (isCompanionConsentRequiredResponse(response)) {
          throw new Error("Enable personalization before saving to companion.")
        }
        throw new Error(response.error || "Failed to save companion check-in")
      }
      appendLog("notice", "Saved draft to companion")
    } catch (err: any) {
      setError(String(err?.message || "Failed to save companion check-in"))
    } finally {
      setSavingCompanionCheckIn(false)
    }
  }, [
    appendLog,
    capabilities?.hasPersonalization,
    input,
    isCompanionMode,
    savingCompanionCheckIn
  ])

  const loadSessionHistory = React.useCallback(async () => {
    if (!sessionId) return
    const resp = await tldwClient.fetchWithAuth(
      `/api/v1/persona/sessions/${encodeURIComponent(sessionId)}?limit_turns=100` as any,
      { method: "GET" }
    )
    if (!resp.ok) {
      setError(resp.error || "Failed to load session history")
      return
    }
    const payload = await resp.json()
    const turns = Array.isArray(payload?.turns) ? payload.turns : []
    const historyLogs: PersonaLogEntry[] = turns.map((turn: any, idx: number) => {
      const role = String(turn?.role || "notice").toLowerCase()
      const kind: PersonaLogEntry["kind"] =
        role === "user" || role === "assistant" || role === "tool" ? role : "notice"
      return {
        id: String(turn?.turn_id || `${Date.now()}-${idx}`),
        kind,
        text: String(turn?.content || "")
      }
    })
    setLogs(historyLogs)
  }, [sessionId])

  const confirmPlan = React.useCallback(() => {
    if (!pendingPlan || !sessionId || !wsRef.current || !connected) return
    const approvedSteps = pendingPlan.steps
      .filter((step) => approvedStepMap[step.idx] !== false)
      .map((step) => step.idx)
    try {
      wsRef.current.send(
        JSON.stringify({
          type: "confirm_plan",
          session_id: sessionId,
          plan_id: pendingPlan.planId,
          approved_steps: approvedSteps
        })
      )
      appendLog(
        "notice",
        `Confirmed ${approvedSteps.length} step${approvedSteps.length === 1 ? "" : "s"}`
      )
      setPendingPlan(null)
    } catch (err: any) {
      setError(String(err?.message || "Failed to confirm plan"))
    }
  }, [appendLog, approvedStepMap, connected, pendingPlan, sessionId])

  const cancelPlan = React.useCallback(() => {
    if (!sessionId || !wsRef.current || !connected) return
    try {
      wsRef.current.send(
        JSON.stringify({
          type: "cancel",
          session_id: sessionId,
          reason: "user_cancelled"
        })
      )
      setPendingPlan(null)
      appendLog("notice", "Cancelled pending plan")
    } catch (err: any) {
      setError(String(err?.message || "Failed to cancel plan"))
    }
  }, [appendLog, connected, sessionId])

  const updateApprovalDuration = React.useCallback(
    (approvalKey: string, duration: PersonaRuntimeApprovalDuration) => {
    setPendingApprovals((prev) =>
      prev.map((approval) =>
        approval.key === approvalKey
          ? { ...approval, selected_duration: duration }
          : approval
      )
    )
    },
    []
  )

  const submitApprovalDecision = React.useCallback(
    async (
      approval: PersonaRuntimeApprovalRequest,
      decision: "approved" | "denied"
    ) => {
      const approvalDecision = _approvalDecisionPayload(decision, approval.selected_duration)
      setSubmittingApprovalKey(approval.key)
      setError(null)
      try {
        const response = await tldwClient.fetchWithAuth(
          "/api/v1/mcp/hub/approval-decisions" as any,
          {
            method: "POST",
            body: {
              approval_policy_id: approval.approval_policy_id,
              context_key: approval.context_key,
              conversation_id: approval.conversation_id,
              tool_name: approval.tool_name,
              scope_key: approval.scope_key,
              decision,
              duration: approvalDecision.duration
            }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to submit approval decision")
        }
        await response.json()
        if (approval.key === activeApprovalKey) {
          clearResolvedApprovalFadeTimer()
          setResolvedApprovalSnapshot({
            key: approval.key,
            toolName: approval.tool_name
          })
        }
        setPendingApprovals((prev) => prev.filter((entry) => entry.key !== approval.key))
        appendLog(
          "notice",
          decision === "approved"
            ? `Approved ${approval.tool_name} and retrying`
            : `Denied ${approval.tool_name}`
        )
        if (
          decision === "approved" &&
          connected &&
          wsRef.current &&
          approval.step_type &&
          approval.tool
        ) {
          wsRef.current.send(
            JSON.stringify({
              type: "retry_tool_call",
              session_id: approval.session_id || sessionId,
              plan_id: approval.plan_id,
              step_idx: approval.step_idx,
              step_type: approval.step_type,
              tool: approval.tool,
              args: approval.args || {},
              why: approval.why,
              description: approval.description
            })
          )
        }
      } catch (err: any) {
        setError(String(err?.message || "Failed to submit approval decision"))
      } finally {
        setSubmittingApprovalKey(null)
      }
    },
    [activeApprovalKey, appendLog, clearResolvedApprovalFadeTimer, connected, sessionId]
  )

  const activePendingApproval = React.useMemo(() => {
    if (!activeApprovalKey) return null
    return pendingApprovals.find((approval) => approval.key === activeApprovalKey) || null
  }, [activeApprovalKey, pendingApprovals])

  const pendingApprovalSummary = React.useMemo(() => {
    if (!pendingApprovals.length) return null
    const primaryApproval = activePendingApproval || pendingApprovals[0] || null
    if (!primaryApproval) return null
    const primaryToolName = String(primaryApproval.tool_name || "tool").trim() || "tool"
    const additionalCount = pendingApprovals.filter(
      (approval) => approval.key !== primaryApproval.key
    ).length
    if (additionalCount <= 0) {
      return `Waiting for approval: ${primaryToolName}`
    }
    return `Waiting for approval: ${primaryToolName} (+${additionalCount} more)`
  }, [activePendingApproval, pendingApprovals])

  const registerRuntimeApprovalRow = React.useCallback(
    (approvalKey: string, node: HTMLDivElement | null) => {
      if (node) {
        runtimeApprovalRowRefs.current.set(approvalKey, node)
        return
      }
      runtimeApprovalRowRefs.current.delete(approvalKey)
    },
    []
  )

  const handleJumpToRuntimeApproval = React.useCallback(() => {
    if (!pendingApprovals.length) return
    const targetApprovalKey = activeApprovalKey || pendingApprovals[0]?.key || null
    if (!targetApprovalKey) return
    setActiveApprovalKey(targetApprovalKey)
    triggerApprovalHighlightPhase("landing_primary")
    const card = runtimeApprovalCardRef.current
    const targetRow = runtimeApprovalRowRefs.current.get(targetApprovalKey) || null
    const scrollTarget = targetRow || card
    if (!scrollTarget) return
    try {
      scrollTarget.scrollIntoView?.({ block: "start", behavior: "smooth" })
    } catch {
      // Ignore environments without scrollIntoView support.
    }
    const focusRoot = targetRow || card
    const buttons = Array.from(focusRoot.querySelectorAll("button")) as HTMLButtonElement[]
    const preferredButton =
      buttons.find((button) =>
        String(button.textContent || "").toLowerCase().includes("approve")
      ) || buttons.find((button) => !button.disabled)
    preferredButton?.focus()
  }, [activeApprovalKey, pendingApprovals, triggerApprovalHighlightPhase])
  const personaUnsupported =
    !capsLoading &&
    capabilities &&
    (!capabilities.hasPersona ||
      (isCompanionMode && !capabilities.hasPersonalization))
  const routeHeader =
    shell === "sidepanel" ? (
      <div className="sticky bg-surface top-0 z-10">
        <SidepanelHeaderSimple activeTitle={routeTitle} />
      </div>
    ) : (
      <div className="rounded-lg border border-border bg-surface px-4 py-3">
        <Typography.Text strong>{routeTitle}</Typography.Text>
        <Typography.Text type="secondary" className="mt-1 block text-sm">
          {isCompanionMode
            ? "A dedicated conversation surface that keeps companion context in the loop."
            : "Live persona sessions run against your connected tldw server."}
        </Typography.Text>
      </div>
    )
  const settingsRoute = shell === "options" ? "/settings/tldw" : "/settings"
  const diagnosticsRoute = shell === "options" ? "/settings/health" : settingsRoute
  const settingsLabel = t("sidepanel:header.settingsShortLabel", "Settings")
  const setupActionLabel =
    shell === "options" && !hasCompletedFirstRun ? "Finish Setup" : settingsLabel
  const openSettings = () => navigate(settingsRoute)
  const openDiagnostics = () => navigate(diagnosticsRoute)
  const openSetup = () => {
    if (shell === "options" && !hasCompletedFirstRun) {
      navigate("/")
      return
    }
    openSettings()
  }
  const selectedPersonaName =
    catalog.find((persona) => String(persona.id || "") === selectedPersonaId)?.name ||
    selectedPersonaId
  const savedTurnDetectionValues = React.useMemo(
    () => buildTurnDetectionValuesFromSavedDefaults(savedPersonaVoiceDefaults),
    [savedPersonaVoiceDefaults]
  )
  const liveTurnDetectionValues = React.useMemo<PersonaTurnDetectionValues>(
    () => ({
      autoCommitEnabled: liveVoiceController.autoCommitEnabled,
      vadThreshold: liveVoiceController.vadThreshold,
      minSilenceMs: liveVoiceController.minSilenceMs,
      turnStopSecs: liveVoiceController.turnStopSecs,
      minUtteranceSecs: liveVoiceController.minUtteranceSecs
    }),
    [
      liveVoiceController.autoCommitEnabled,
      liveVoiceController.minSilenceMs,
      liveVoiceController.minUtteranceSecs,
      liveVoiceController.turnStopSecs,
      liveVoiceController.vadThreshold
    ]
  )
  const showSaveCurrentSettingsAsDefaults =
    connected &&
    !isCompanionMode &&
    (!savedTurnDetectionValues ||
      !areTurnDetectionValuesEqual(savedTurnDetectionValues, liveTurnDetectionValues))

  const handleSaveCurrentLiveTurnDetectionDefaults = React.useCallback(async () => {
    const personaId = getTargetPersonaId()
    if (!personaId || savingLiveVoiceDefaults) return
    setSavingLiveVoiceDefaults(true)
    setError(null)
    try {
      const mergedVoiceDefaults: PersonaVoiceDefaults = {
        ...(savedPersonaVoiceDefaults || {}),
        auto_commit_enabled: liveVoiceController.autoCommitEnabled,
        vad_threshold: liveVoiceController.vadThreshold,
        min_silence_ms: liveVoiceController.minSilenceMs,
        turn_stop_secs: liveVoiceController.turnStopSecs,
        min_utterance_secs: liveVoiceController.minUtteranceSecs
      }
      const response = await tldwClient.fetchWithAuth(
        `/api/v1/persona/profiles/${encodeURIComponent(personaId)}` as any,
        {
          method: "PATCH",
          body: {
            voice_defaults: mergedVoiceDefaults
          }
        }
      )
      if (!response.ok) {
        throw new Error(response.error || "Failed to save current live settings as defaults")
      }
      const payload = (await response.json()) as PersonaProfileResponse
      setSavedPersonaVoiceDefaults(payload?.voice_defaults || mergedVoiceDefaults)
      appendLog("notice", "Saved current live turn detection defaults")
    } catch (err: any) {
      setError(String(err?.message || "Failed to save current live settings as defaults"))
    } finally {
      setSavingLiveVoiceDefaults(false)
    }
  }, [
    appendLog,
    getTargetPersonaId,
    liveVoiceController.autoCommitEnabled,
    liveVoiceController.minSilenceMs,
    liveVoiceController.minUtteranceSecs,
    liveVoiceController.turnStopSecs,
    liveVoiceController.vadThreshold,
    savedPersonaVoiceDefaults,
    savingLiveVoiceDefaults
  ])

  const liveSessionControls = (
    <div className="flex flex-wrap items-center gap-2">
      {!isCompanionMode ? (
        <Select
          size="small"
          className="min-w-[180px]"
          value={selectedPersonaId}
          disabled={connected}
          aria-label={t("sidepanel:persona.select", "Select persona")}
          onChange={(value) => handlePersonaSelectionChange(String(value))}
          options={catalog.map((persona) => ({
            label: persona.name || persona.id,
            value: persona.id
          }))}
          placeholder={t("sidepanel:persona.select", "Select persona")}
        />
      ) : null}
      <Select
        data-testid="persona-resume-session-select"
        size="small"
        className="min-w-[180px]"
        value={resumeSessionId || "__new__"}
        aria-label={t("sidepanel:persona.resume", "Resume session")}
        disabled={connected}
        onChange={(value) => handleResumeSessionSelectionChange(String(value))}
        options={[
          { label: t("sidepanel:persona.newSession", "New session"), value: "__new__" },
          ...sessionHistory.map((session) => ({
            label: session.session_id,
            value: session.session_id
          }))
        ]}
        placeholder={t("sidepanel:persona.resume", "Resume session")}
      />
      <Checkbox
        data-testid="persona-memory-toggle"
        checked={memoryEnabled}
        onChange={(event) => setMemoryEnabled(event.target.checked)}
      >
        {t("sidepanel:persona.memoryToggle", "Memory")}
      </Checkbox>
      {!isCompanionMode ? (
        <Checkbox
          data-testid="persona-state-context-toggle"
          checked={personaStateContextEnabled}
          onChange={(event) => setPersonaStateContextEnabled(event.target.checked)}
        >
          {t("sidepanel:persona.stateContextToggle", "State context")}
        </Checkbox>
      ) : null}
      {!isCompanionMode ? (
        <Checkbox
          data-testid="persona-companion-context-toggle"
          checked={companionContextEnabled}
          onChange={(event) => setCompanionContextEnabled(event.target.checked)}
        >
          {t("sidepanel:persona.companionContextToggle", "Companion context")}
        </Checkbox>
      ) : null}
      {!isCompanionMode ? (
        <Checkbox
          data-testid="persona-state-context-default-toggle"
          checked={personaStateContextProfileDefault}
          disabled={!connected || updatingPersonaStateContextDefault}
          onChange={(event) => {
            void updatePersonaStateContextDefault(event.target.checked)
          }}
        >
          {t("sidepanel:persona.stateContextDefaultToggle", "Profile default")}
        </Checkbox>
      ) : null}
      <Select
        data-testid="persona-memory-topk-select"
        size="small"
        className="w-[150px]"
        value={memoryTopK}
        aria-label={t("sidepanel:persona.memoryTopK", "Memory results")}
        disabled={!memoryEnabled}
        onChange={(value) => setMemoryTopK(Number(value))}
        options={MEMORY_TOP_K_OPTIONS.map((k) => ({
          label: formatMemoryResultsLabel(k),
          value: k
        }))}
        placeholder={t("sidepanel:persona.memoryTopK", "Memory results")}
      />
      {!connected ? (
        <Button
          size="small"
          type="primary"
          loading={connecting}
          onClick={() => {
            void connect()
          }}
        >
          {t("sidepanel:persona.connect", "Connect")}
        </Button>
      ) : (
        <Button size="small" onClick={() => {
          disconnect()
        }}>
          {t("sidepanel:persona.disconnect", "Disconnect")}
        </Button>
      )}
      {sessionId ? <Tag color="blue">{`session: ${sessionId.slice(0, 8)}`}</Tag> : null}
      {sessionId ? (
        <Button size="small" onClick={() => void loadSessionHistory()}>
          {t("sidepanel:persona.loadHistory", "Load history")}
        </Button>
      ) : null}
    </div>
  )

  const errorBanner = error ? (
    <div className="rounded-md border border-danger/30 bg-danger/10 p-2 text-xs text-danger">
      {error}
    </div>
  ) : null

  const assistantVoiceCard = (
    <AssistantVoiceCard
      resolvedDefaults={resolvedLivePersonaVoiceDefaults}
      connected={connected}
      state={liveVoiceController.state}
      speechAvailable={liveVoiceController.speechAvailable}
      isListening={liveVoiceController.isListening}
      heardText={liveVoiceController.heardText}
      lastCommittedText={liveVoiceController.lastCommittedText}
      activeToolStatus={liveVoiceController.activeToolStatus}
      pendingApprovalSummary={pendingApprovalSummary}
      warning={liveVoiceController.warning}
      recoveryMode={liveVoiceController.recoveryMode}
      manualModeRequired={liveVoiceController.manualModeRequired}
      canSendNow={liveVoiceController.canSendNow}
      textOnlyDueToTtsFailure={liveVoiceController.textOnlyDueToTtsFailure}
      showSaveCurrentSettingsAsDefaults={showSaveCurrentSettingsAsDefaults}
      savingCurrentSettingsAsDefaults={savingLiveVoiceDefaults}
      sessionAutoResume={liveVoiceController.sessionAutoResume}
      sessionBargeIn={liveVoiceController.sessionBargeIn}
      autoCommitEnabled={liveVoiceController.autoCommitEnabled}
      vadPreset={liveVoiceController.vadPreset}
      vadThreshold={liveVoiceController.vadThreshold}
      minSilenceMs={liveVoiceController.minSilenceMs}
      turnStopSecs={liveVoiceController.turnStopSecs}
      minUtteranceSecs={liveVoiceController.minUtteranceSecs}
      onToggleListening={liveVoiceController.toggleListening}
      onSendNow={liveVoiceController.sendCurrentTranscriptNow}
      onSessionAutoResumeChange={liveVoiceController.setSessionAutoResume}
      onSessionBargeInChange={liveVoiceController.setSessionBargeIn}
      onAutoCommitEnabledChange={liveVoiceController.setAutoCommitEnabled}
      onVadPresetChange={liveVoiceController.setVadPreset}
      onVadThresholdChange={liveVoiceController.setVadThreshold}
      onMinSilenceMsChange={liveVoiceController.setMinSilenceMs}
      onTurnStopSecsChange={liveVoiceController.setTurnStopSecs}
      onMinUtteranceSecsChange={liveVoiceController.setMinUtteranceSecs}
      onKeepListening={liveVoiceController.keepListening}
      onResetTurn={liveVoiceController.resetTurn}
      onWaitOnRecovery={liveVoiceController.waitOnRecovery}
      onCopyLastCommandToComposer={handleCopyLastVoiceCommandToComposer}
      onJumpToApproval={handleJumpToRuntimeApproval}
      onSaveCurrentSettingsAsDefaults={handleSaveCurrentLiveTurnDetectionDefaults}
      onReconnectPersonaSession={handleReconnectPersonaSessionFromRecovery}
    />
  )

  const runtimeApprovalCard = pendingApprovals.length || resolvedApprovalSnapshot ? (
    <div
      ref={runtimeApprovalCardRef}
      data-testid="persona-runtime-approval-card"
      className="rounded-lg border border-warning/40 bg-warning/5 p-3"
    >
      <Typography.Text strong>
        {t("sidepanel:persona.runtimeApproval", "Runtime approval required")}
      </Typography.Text>
      {resolvedApprovalSnapshot && !pendingApprovals.length ? (
        <div
          data-testid="persona-runtime-approval-answered"
          className="mt-2 rounded-md border border-success/30 bg-success/10 p-2 text-xs text-success"
        >
          {`Answered: ${resolvedApprovalSnapshot.toolName}`}
        </div>
      ) : null}
      <div className="mt-2 space-y-3">
        {pendingApprovals.map((approval) => {
          const isSubmitting = submittingApprovalKey === approval.key
          const isHighlighted = approval.key === activeApprovalKey
          const highlightPhase = isHighlighted ? approvalHighlightPhase : "none"
          return (
            <div
              key={approval.key}
              ref={(node) => {
                registerRuntimeApprovalRow(approval.key, node)
              }}
              data-testid={`persona-runtime-approval-row-${approval.key}`}
              data-approval-key={approval.key}
              data-highlighted={isHighlighted ? "true" : "false"}
              data-highlight-phase={highlightPhase}
              data-highlight-seq={isHighlighted ? String(approvalHighlightSequence) : "0"}
              className={`rounded-md border p-3 ${
                isHighlighted
                  ? "persona-runtime-approval-row border-warning/60 bg-warning/10"
                  : "persona-runtime-approval-row border-warning/30 bg-surface"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Tag color="gold">{approval.tool_name}</Tag>
                {isHighlighted ? (
                  <Tag color="orange">Needs your approval</Tag>
                ) : null}
                {approval.mode ? <Tag color="blue">{approval.mode}</Tag> : null}
                {approval.reason ? <Tag color="red">{approval.reason}</Tag> : null}
              </div>
              {approval.scope_context?.server_name ||
              approval.scope_context?.server_id ||
              approval.scope_context?.workspace_id ||
              approval.scope_context?.workspace_bundle_ids?.length ? (
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-muted">
                  {approval.scope_context?.server_name || approval.scope_context?.server_id ? (
                    <Tag color="cyan">
                      {approval.scope_context.server_name || approval.scope_context.server_id}
                    </Tag>
                  ) : null}
                  {approval.scope_context?.workspace_id ? (
                    <Tag color="cyan">{approval.scope_context.workspace_id}</Tag>
                  ) : null}
                  {(approval.scope_context?.workspace_bundle_ids || []).map((workspaceId) => (
                    <Tag
                      key={`${approval.key}-workspace-bundle-${workspaceId}`}
                      color="purple"
                    >
                      {workspaceId}
                    </Tag>
                  ))}
                  {approval.scope_context?.selected_workspace_trust_source ? (
                    <Tag color="blue">
                      {approval.scope_context.selected_workspace_trust_source}
                    </Tag>
                  ) : null}
                  {(approval.scope_context.requested_slots || []).map((slotName) => (
                    <Tag key={`${approval.key}-${slotName}`} color="geekblue">
                      {slotName}
                    </Tag>
                  ))}
                  {(approval.scope_context.normalized_paths || []).map((pathValue) => (
                    <Tag key={`${approval.key}-path-${pathValue}`} color="magenta">
                      {pathValue}
                    </Tag>
                  ))}
                </div>
              ) : null}
              {Object.keys(approval.arguments_summary).length ? (
                <pre className="mt-2 overflow-auto rounded bg-bg p-2 text-[11px] text-text">
                  {JSON.stringify(approval.arguments_summary, null, 2)}
                </pre>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-text-muted">
                <label htmlFor={`persona-approval-duration-${approval.key}`}>
                  {t("sidepanel:persona.approvalDuration", "Approval duration")}
                </label>
                <select
                  id={`persona-approval-duration-${approval.key}`}
                  className="rounded border border-border bg-bg px-2 py-1 text-xs text-text"
                  value={approval.selected_duration}
                  disabled={isSubmitting}
                  onChange={(event) =>
                    updateApprovalDuration(
                      approval.key,
                      event.target.value as PersonaRuntimeApprovalDuration
                    )
                  }
                >
                  {approval.duration_options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <Button
                  size="small"
                  type="primary"
                  loading={isSubmitting}
                  onClick={() => {
                    void submitApprovalDecision(approval, "approved")
                  }}
                >
                  {t("sidepanel:persona.approveAndRetry", "Approve and retry")}
                </Button>
                <Button
                  size="small"
                  danger
                  disabled={isSubmitting}
                  onClick={() => {
                    void submitApprovalDecision(approval, "denied")
                  }}
                >
                  {t("sidepanel:persona.denyApproval", "Deny")}
                </Button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  ) : null

  const liveSessionStatusPanels = (
    <>
      {setupLiveDetour ? (
        <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-3 text-sm text-sky-100">
          <div>Finish this live test, then return to setup.</div>
          <button
            type="button"
            className="mt-2 rounded-md border border-sky-500/40 px-3 py-2 text-sm font-medium text-sky-100"
            onClick={handleReturnToSetupFromLiveDetour}
          >
            Return to setup
          </button>
        </div>
      ) : null}
      {errorBanner}
      {!isCompanionMode ? (
        <PersonaPolicySummary personaId={selectedPersonaId || null} />
      ) : null}
      {runtimeApprovalCard}
    </>
  )

  const pendingPlanCard = pendingPlan ? (
    <div className="rounded-lg border border-border bg-surface p-3">
      <Typography.Text strong>
        {t("sidepanel:persona.pendingPlan", "Pending tool plan")}
      </Typography.Text>
      {pendingPlan.memory ? (
        <div className="mt-1 flex flex-wrap items-center gap-1">
          <Tag color={pendingPlan.memory.enabled ? "green" : "default"}>
            {pendingPlan.memory.enabled ? "memory on" : "memory off"}
          </Tag>
          {typeof pendingPlan.memory.requested_top_k === "number" ? (
            <Tag color="blue">
              {`requested ${formatMemoryResultsLabel(
                pendingPlan.memory.requested_top_k
              ).toLowerCase()}`}
            </Tag>
          ) : null}
          {typeof pendingPlan.memory.applied_count === "number" ? (
            <Tag color="purple">
              {`applied results: ${pendingPlan.memory.applied_count}`}
            </Tag>
          ) : null}
        </div>
      ) : null}
      {pendingPlan.companion ? (
        <div className="mt-1 flex flex-wrap items-center gap-1">
          <Tag color={pendingPlan.companion.enabled ? "green" : "default"}>
            {pendingPlan.companion.enabled ? "companion on" : "companion off"}
          </Tag>
          {typeof pendingPlan.companion.applied_card_count === "number" ? (
            <Tag color="cyan">
              {`applied cards: ${pendingPlan.companion.applied_card_count}`}
            </Tag>
          ) : null}
          {typeof pendingPlan.companion.applied_activity_count === "number" ? (
            <Tag color="geekblue">
              {`applied activity: ${pendingPlan.companion.applied_activity_count}`}
            </Tag>
          ) : null}
        </div>
      ) : null}
      <div className="mt-2 space-y-1">
        {pendingPlan.steps.map((step) => (
          <label key={step.idx} className="flex items-start gap-2 text-xs text-text">
            <Checkbox
              checked={approvedStepMap[step.idx] !== false}
              disabled={step.policy?.allow === false}
              onChange={(event) => {
                const nextChecked = event.target.checked
                setApprovedStepMap((prev) => ({
                  ...prev,
                  [step.idx]: nextChecked
                }))
              }}
            />
            <span>
              <span className="font-semibold">{`${step.idx}. ${step.tool}`}</span>
              {step.description ? ` - ${step.description}` : ""}
              <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                {step.policy?.required_scope ? (
                  <Tag color="blue">{`scope: ${step.policy.required_scope}`}</Tag>
                ) : null}
                {step.policy?.requires_confirmation ? (
                  <Tag color="gold">confirm</Tag>
                ) : null}
                {step.policy?.allow === false ? (
                  <Tag color="red">{`blocked${step.policy.reason_code ? `: ${step.policy.reason_code}` : ""}`}</Tag>
                ) : null}
              </span>
              {step.policy?.allow === false && step.policy.reason ? (
                <div className="mt-1 text-[11px] text-danger">
                  {step.policy.reason}
                </div>
              ) : null}
            </span>
          </label>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2">
        <Button
          size="small"
          type="primary"
          icon={<CheckCircle2 className="h-3.5 w-3.5" />}
          onClick={confirmPlan}
        >
          {t("sidepanel:persona.confirmPlan", "Confirm plan")}
        </Button>
        <Button
          size="small"
          icon={<XCircle className="h-3.5 w-3.5" />}
          onClick={cancelPlan}
        >
          {t("sidepanel:persona.cancelPlan", "Cancel")}
        </Button>
      </div>
    </div>
  ) : null

  const stateDocsCard = (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Typography.Text strong>
          {t("sidepanel:persona.stateDocs", "Persistent state docs")}
        </Typography.Text>
        <div className="flex flex-wrap items-center gap-1">
          <Tag
            data-testid="persona-state-dirty-tag"
            color={hasUnsavedPersonaStateChanges ? "gold" : "green"}
          >
            {stateDirtyLabel}
          </Tag>
          {stateLastModified ? (
            <Typography.Text type="secondary" className="text-xs">
              {`${t("sidepanel:persona.stateUpdatedPrefix", "updated")} ${stateLastModified}`}
            </Typography.Text>
          ) : null}
          <Button
            data-testid="persona-state-editor-toggle-button"
            size="small"
            onClick={() => {
              setPersonaStateEditorExpanded((prev) => !prev)
            }}
          >
            {stateEditorToggleLabel}
          </Button>
        </div>
      </div>
      {personaStateEditorExpanded ? (
        <>
          <div className="mt-2 grid gap-2">
            <Input.TextArea
              data-testid="persona-state-soul-input"
              value={soulMd}
              autoSize={{ minRows: 2, maxRows: 4 }}
              onChange={(event) => setSoulMd(event.target.value)}
              placeholder={t("sidepanel:persona.stateSoulPlaceholder", "soul.md")}
            />
            <Input.TextArea
              data-testid="persona-state-identity-input"
              value={identityMd}
              autoSize={{ minRows: 2, maxRows: 4 }}
              onChange={(event) => setIdentityMd(event.target.value)}
              placeholder={t("sidepanel:persona.stateIdentityPlaceholder", "identity.md")}
            />
            <Input.TextArea
              data-testid="persona-state-heartbeat-input"
              value={heartbeatMd}
              autoSize={{ minRows: 2, maxRows: 4 }}
              onChange={(event) => setHeartbeatMd(event.target.value)}
              placeholder={t("sidepanel:persona.stateHeartbeatPlaceholder", "heartbeat.md")}
            />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button
              data-testid="persona-state-load-button"
              size="small"
              loading={personaStateLoading}
              disabled={!connected || personaStateSaving}
              onClick={() => {
                void loadPersonaStateDocs()
              }}
            >
              {t("sidepanel:persona.stateLoad", "Load state")}
            </Button>
            <Button
              data-testid="persona-state-save-button"
              size="small"
              type="primary"
              loading={personaStateSaving}
              disabled={!connected || !hasUnsavedPersonaStateChanges}
              onClick={() => {
                void savePersonaStateDocs()
              }}
            >
              {t("sidepanel:persona.stateSave", "Save state")}
            </Button>
            <Button
              data-testid="persona-state-revert-button"
              size="small"
              disabled={!hasUnsavedPersonaStateChanges || personaStateSaving}
              onClick={revertPersonaStateDraft}
            >
              {t("sidepanel:persona.stateRevert", "Revert")}
            </Button>
            <Button
              data-testid="persona-state-history-button"
              size="small"
              loading={personaStateHistoryLoading}
              disabled={!connected}
              onClick={() => {
                void loadPersonaStateHistory()
              }}
            >
              {t("sidepanel:persona.stateHistory", "Load history")}
            </Button>
          </div>
          {personaStateHistory.length > 0 ? (
            <div className="mt-3 space-y-2">
              {personaStateHistory.length > 1 ? (
                <div className="mb-1 flex items-center gap-2 text-xs">
                  <Typography.Text type="secondary" className="text-xs">
                    {t("sidepanel:persona.stateHistoryOrderLabel", "Order")}
                  </Typography.Text>
                  <Button
                    data-testid="persona-state-history-order-newest-button"
                    size="small"
                    type={personaStateHistoryOrder === "newest" ? "primary" : "default"}
                    onClick={() => {
                      setPersonaStateHistoryOrder("newest")
                    }}
                  >
                    {t("sidepanel:persona.stateHistoryOrderNewest", "Newest")}
                  </Button>
                  <Button
                    data-testid="persona-state-history-order-oldest-button"
                    size="small"
                    type={personaStateHistoryOrder === "oldest" ? "primary" : "default"}
                    onClick={() => {
                      setPersonaStateHistoryOrder("oldest")
                    }}
                  >
                    {t("sidepanel:persona.stateHistoryOrderOldest", "Oldest")}
                  </Button>
                </div>
              ) : null}
              {orderedPersonaStateHistory.map((entry) => (
                <div
                  data-testid={`persona-state-history-entry-${entry.entry_id}`}
                  key={entry.entry_id}
                  className="rounded border border-border bg-surface2 px-2 py-1.5 text-xs"
                >
                  <div className="flex flex-wrap items-center gap-1">
                    <Tag color={entry.is_active ? "green" : "default"}>
                      {entry.is_active
                        ? t("sidepanel:persona.stateHistoryActive", "active")
                        : t("sidepanel:persona.stateHistoryArchived", "archived")}
                    </Tag>
                    <Tag color="blue">{entry.field}</Tag>
                    {typeof entry.version === "number" ? (
                      <Tag color="purple">{`v${entry.version}`}</Tag>
                    ) : null}
                    <Button
                      data-testid={`persona-state-restore-${entry.entry_id}`}
                      size="small"
                      disabled={entry.is_active === true}
                      loading={restoringStateEntryId === entry.entry_id}
                      onClick={() => {
                        void restorePersonaStateHistoryEntry(entry.entry_id)
                      }}
                    >
                      {t("sidepanel:persona.stateRestore", "Restore")}
                    </Button>
                  </div>
                  <div className="mt-1 whitespace-pre-wrap text-text">
                    {String(entry.content || "")}
                  </div>
                  {entry.created_at || entry.last_modified ? (
                    <Typography.Text
                      data-testid={`persona-state-history-meta-${entry.entry_id}`}
                      type="secondary"
                      className="mt-1 block text-[11px]"
                    >
                      {[
                        entry.created_at
                          ? `${t("sidepanel:persona.stateHistoryCreated", "created")} ${entry.created_at}`
                          : null,
                        entry.last_modified
                          ? `${t("sidepanel:persona.stateHistoryUpdated", "updated")} ${entry.last_modified}`
                          : null
                      ]
                        .filter((item): item is string => Boolean(item))
                        .join(" · ")}
                    </Typography.Text>
                  ) : null}
                </div>
              ))}
            </div>
          ) : personaStateHistoryLoaded ? (
            <Typography.Text
              data-testid="persona-state-history-empty"
              type="secondary"
              className="mt-3 block text-xs"
            >
              {t(
                "sidepanel:persona.stateHistoryEmpty",
                "No state history entries yet."
              )}
            </Typography.Text>
          ) : null}
        </>
      ) : null}
    </div>
  )

  const transcriptPanel = (
    <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-surface p-3">
      <div className="space-y-2">
        {logs.length === 0 ? (
          <Typography.Text type="secondary" className="text-xs">
            {isCompanionMode
              ? "Connect to companion and send a message to start."
              : t(
                  "sidepanel:persona.empty",
                  "Connect to persona and send a message to start."
                )}
          </Typography.Text>
        ) : (
          logs.map((entry) => (
            <div
              key={entry.id}
              className="rounded border border-border bg-surface2 px-2 py-1.5 text-xs"
            >
              <div className="mb-1 uppercase tracking-wide text-[10px] text-text-muted">
                {entry.kind}
              </div>
              <div className="whitespace-pre-wrap text-text">{entry.text}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )

  const composerPanel = (
    <div className="flex flex-col gap-2">
      {isCompanionMode && companionPrompts.length ? (
        <div
          className="flex flex-wrap gap-2"
          data-testid="companion-conversation-prompts"
        >
          {companionPrompts.map((prompt) => (
            <Button
              key={prompt.prompt_id}
              size="small"
              onClick={() => {
                setInput(prompt.prompt_text)
              }}
              type="default"
            >
              {prompt.label}
            </Button>
          ))}
        </div>
      ) : null}
      <div className="flex items-end gap-2">
        <Input.TextArea
          value={input}
          autoSize={{ minRows: 2, maxRows: 4 }}
          onChange={(event) => setInput(event.target.value)}
          placeholder={
            isCompanionMode
              ? "Ask Companion..."
              : t("sidepanel:persona.inputPlaceholder", "Ask Persona...")
          }
          onPressEnter={(event) => {
            if (event.shiftKey) return
            event.preventDefault()
            sendUserMessage()
          }}
        />
        {capabilities?.hasPersonalization ? (
          <Button
            data-testid="persona-save-checkin-button"
            disabled={!canSaveCompanionCheckIn}
            loading={savingCompanionCheckIn}
            onClick={() => {
              void saveCompanionCheckIn()
            }}
          >
            {t("sidepanel:persona.saveCheckIn", "Save check-in")}
          </Button>
        ) : null}
        <Button
          type="primary"
          icon={<Send className="h-4 w-4" />}
          disabled={!canSend}
          onClick={sendUserMessage}
        >
          {t("common:send", "Send")}
        </Button>
      </div>
    </div>
  )

  const dismissSetupHandoff = React.useCallback(() => {
    if (setupHandoff) {
      void emitSetupAnalyticsEvent({
        runId: setupHandoff.runId,
        eventType: "handoff_dismissed"
      })
    }
    setSetupHandoffFocusRequest(null)
    setSetupHandoff(null)
  }, [emitSetupAnalyticsEvent, setupHandoff])

  const openSetupHandoffTarget = React.useCallback((target: { tab: "live" } | SetupHandoffSectionTarget) => {
    const tab = target.tab
    const currentHandoff = setupHandoffRef.current
    if (currentHandoff) {
      void emitSetupAnalyticsEvent({
        runId: currentHandoff.runId,
        eventType: "handoff_action_clicked",
        actionTarget: tab
      })
    }
    setActiveTab(tab)
    if ("section" in target) {
      setupHandoffFocusTokenRef.current += 1
      setSetupHandoffFocusRequest({
        tab: target.tab,
        section: target.section,
        token: setupHandoffFocusTokenRef.current,
        connectionId: "connectionId" in target ? (target.connectionId ?? null) : null,
        connectionName:
          "connectionName" in target ? (target.connectionName ?? null) : null
      })
    } else {
      setSetupHandoffFocusRequest(null)
    }
    setSetupHandoff((current) => {
      if (!current) return null
      if (current.targetTab === tab) {
        return current
      }
      return {
        ...current,
        targetTab: tab
      }
    })
  }, [emitSetupAnalyticsEvent])

  const handleSetupHandoffFocusConsumed = React.useCallback((token: number) => {
    const currentRequest = setupHandoffFocusRequestRef.current || setupHandoffFocusRequest
    if (!currentRequest || currentRequest.token !== token) return
    const currentHandoff = setupHandoffRef.current || setupHandoff

    const actionTarget = `${currentRequest.tab}.${currentRequest.section}`
    void emitSetupAnalyticsEvent({
      runId: currentHandoff?.runId,
      eventType: "handoff_target_reached",
      actionTarget,
      metadata: {
        connection_id: currentRequest.connectionId || undefined,
        connection_name: currentRequest.connectionName || undefined,
        recommended_action: currentHandoff?.recommendedAction || undefined,
        completion_type: currentHandoff?.completionType || undefined
      }
    })

    setSetupHandoffFocusRequest((current) => {
      if (!current) return current
      if (current.token !== token) return current
      return null
    })
  }, [emitSetupAnalyticsEvent, setupHandoff, setupHandoffFocusRequest])

  const handleProfileDefaultsSaved = React.useCallback(() => {
    consumeSetupHandoffAction("voice_defaults_saved")
  }, [consumeSetupHandoffAction])

  const handleConnectionSaved = React.useCallback(() => {
    consumeSetupHandoffAction("connection_saved")
  }, [consumeSetupHandoffAction])

  const handleConnectionTestSucceeded = React.useCallback(() => {
    consumeSetupHandoffAction("connection_test_succeeded")
  }, [consumeSetupHandoffAction])

  const handleTestLabDryRunCompleted = React.useCallback((result: TestLabDryRunCompletedResult) => {
    if (!result.matched) return
    consumeSetupHandoffAction("dry_run_match")
  }, [consumeSetupHandoffAction])

  const renderSetupHandoffCard = React.useCallback(
    (tab: PersonaGardenTabKey) => {
      if (!setupHandoff || setupHandoff.targetTab !== tab) return null
      return (
        <PersonaSetupHandoffCard
          targetTab={setupHandoff.targetTab}
          completionType={setupHandoff.completionType}
          reviewSummary={setupHandoff.reviewSummary}
          recommendedAction={setupHandoff.recommendedAction}
          compact={setupHandoff.compact}
          onDismiss={dismissSetupHandoff}
          onAddCommand={() =>
            openSetupHandoffTarget({ tab: "commands", section: "command_form" })
          }
          onOpenCommands={() =>
            openSetupHandoffTarget({ tab: "commands", section: "command_list" })
          }
          onOpenTestLab={() =>
            openSetupHandoffTarget({ tab: "test-lab", section: "dry_run_form" })
          }
          onOpenLive={() => openSetupHandoffTarget({ tab: "live" })}
          onOpenProfiles={() =>
            openSetupHandoffTarget({
              tab: "profiles",
              section: "confirmation_mode"
            })
          }
          onOpenConnections={() =>
            setupHandoff.reviewSummary.connection.mode === "skipped"
              ? openSetupHandoffTarget({
                  tab: "connections",
                  section: "connection_form"
                })
              : openSetupHandoffTarget({
                  tab: "connections",
                  section: "saved_connections",
                  connectionName:
                    setupHandoff.reviewSummary.connection.mode === "created" ||
                    setupHandoff.reviewSummary.connection.mode === "available"
                      ? setupHandoff.reviewSummary.connection.name
                      : null
                })
          }
        />
      )
    },
    [dismissSetupHandoff, openSetupHandoffTarget, setupHandoff]
  )

  const withSetupHandoff = React.useCallback(
    (tab: PersonaGardenTabKey, content: React.ReactNode) => (
      <div className="space-y-3">
        {renderSetupHandoffCard(tab)}
        {content}
      </div>
    ),
    [renderSetupHandoffCard]
  )

  const tabItems = [
    {
      key: "commands",
      label: t("sidepanel:persona.tabCommands", "Commands"),
      content: withSetupHandoff(
        "commands",
        <CommandsPanel
          selectedPersonaId={selectedPersonaId}
          selectedPersonaName={selectedPersonaName}
          isActive={activeTab === "commands"}
          analytics={voiceAnalytics}
          analyticsLoading={voiceAnalyticsLoading}
          handoffFocusRequest={
            setupHandoffFocusRequest?.tab === "commands"
              ? {
                  section: setupHandoffFocusRequest.section as "command_form" | "command_list",
                  token: setupHandoffFocusRequest.token
                }
              : null
          }
          onSetupHandoffFocusConsumed={handleSetupHandoffFocusConsumed}
          openCommandId={openCommandId}
          onOpenCommandHandled={handleOpenCommandHandled}
          draftCommandPhrase={draftCommandPhrase}
          draftCommandSource={draftCommandSource}
          onDraftCommandPhraseHandled={handleDraftCommandPhraseHandled}
          rerunAfterSaveCommandId={rerunAfterSaveCommandId}
          onRerunAfterSave={handleRerunAfterCommandSave}
          onCommandSaved={handleCommandSaved}
        />
      )
    },
    {
      key: "test-lab",
      label: t("sidepanel:persona.tabTestLab", "Test Lab"),
      content: withSetupHandoff(
        "test-lab",
        <TestLabPanel
          selectedPersonaId={selectedPersonaId}
          selectedPersonaName={selectedPersonaName}
          isActive={activeTab === "test-lab"}
          analytics={voiceAnalytics}
          handoffFocusRequest={
            setupHandoffFocusRequest?.tab === "test-lab"
              ? {
                  section: setupHandoffFocusRequest.section as "dry_run_form",
                  token: setupHandoffFocusRequest.token
                }
              : null
          }
          onSetupHandoffFocusConsumed={handleSetupHandoffFocusConsumed}
          initialHeardText={lastTestLabPhrase}
          rerunRequestToken={testLabRerunToken}
          onOpenCommand={handleOpenCommandFromTestLab}
          onCreateCommandDraft={handleCreateCommandFromTestLab}
          onDryRunCompleted={handleTestLabDryRunCompleted}
        />
      )
    },
    {
      key: "live",
      label: t("sidepanel:persona.tabLive", "Live Session"),
      content: withSetupHandoff(
        "live",
        <LiveSessionPanel
          controls={liveSessionControls}
          assistantVoice={assistantVoiceCard}
          error={liveSessionStatusPanels}
          pendingPlan={pendingPlanCard}
          transcript={transcriptPanel}
          composer={composerPanel}
        />
      )
    },
    {
      key: "profiles",
      label: t("sidepanel:persona.tabProfiles", "Profiles"),
      content: withSetupHandoff(
        "profiles",
        <ProfilePanel
          selectedPersonaId={selectedPersonaId}
          selectedPersonaName={selectedPersonaName}
          personaCount={catalog.length}
          connected={connected}
          sessionId={sessionId}
          setup={savedPersonaSetup}
          onStartSetup={handleStartSetup}
          onResumeSetup={handleResumeSetup}
          onResetSetup={handleResetSetup}
          onRerunSetup={handleRerunSetup}
          onDefaultsSaved={handleProfileDefaultsSaved}
          isActive={activeTab === "profiles"}
          setupAnalytics={setupAnalytics}
          setupAnalyticsLoading={setupAnalyticsLoading}
          analytics={voiceAnalytics}
          analyticsLoading={voiceAnalyticsLoading}
          handoffFocusRequest={
            setupHandoffFocusRequest?.tab === "profiles"
              ? {
                  section: setupHandoffFocusRequest.section as
                    | "assistant_defaults"
                    | "confirmation_mode",
                  token: setupHandoffFocusRequest.token
                }
              : null
          }
          onSetupHandoffFocusConsumed={handleSetupHandoffFocusConsumed}
        />
      )
    },
    {
      key: "voice",
      label: t("sidepanel:persona.tabVoice", "Voice & Examples"),
      content: (
        <VoiceExamplesPanel
          selectedPersonaId={selectedPersonaId}
          selectedPersonaName={selectedPersonaName}
          isActive={activeTab === "voice"}
        />
      )
    },
    {
      key: "connections",
      label: t("sidepanel:persona.tabConnections", "Connections"),
      content: withSetupHandoff(
        "connections",
        <ConnectionsPanel
          selectedPersonaId={selectedPersonaId}
          selectedPersonaName={selectedPersonaName}
          isActive={activeTab === "connections"}
          onConnectionSaved={handleConnectionSaved}
          onConnectionTestSucceeded={handleConnectionTestSucceeded}
          handoffFocusRequest={
            setupHandoffFocusRequest?.tab === "connections"
              ? {
                  section: setupHandoffFocusRequest.section as
                    | "connection_form"
                    | "saved_connections",
                  token: setupHandoffFocusRequest.token,
                  connectionId: setupHandoffFocusRequest.connectionId ?? null,
                  connectionName: setupHandoffFocusRequest.connectionName ?? null
                }
              : null
          }
          onSetupHandoffFocusConsumed={handleSetupHandoffFocusConsumed}
        />
      )
    },
    {
      key: "state",
      label: t("sidepanel:persona.tabStateDocs", "State Docs"),
      content: <StateDocsPanel>{stateDocsCard}</StateDocsPanel>
    },
    {
      key: "scopes",
      label: t("sidepanel:persona.tabScopes", "Scopes"),
      content: <ScopesPanel selectedPersonaName={selectedPersonaName} />
    },
    {
      key: "policies",
      label: t("sidepanel:persona.tabPolicies", "Policies"),
      content: <PoliciesPanel hasPendingPlan={Boolean(pendingPlan)} />
    }
  ]
  if (uxState === "error_auth" || uxState === "configuring_auth") {
    return (
      <div
        data-testid="persona-route-root"
        className={routeRootClassName}
      >
        {routeHeader}
        <div className="p-4">
          <FeatureEmptyState
            title={
              isCompanionMode
                ? "Add your credentials to use Companion"
                : "Add your credentials to use Persona"
            }
            description={
              isCompanionMode
                ? "Companion conversation needs a reachable tldw server plus valid credentials before a session can start."
                : "Persona streaming needs a reachable tldw server plus valid credentials before a session can start."
            }
            primaryActionLabel={settingsLabel}
            onPrimaryAction={openSettings}
          />
        </div>
      </div>
    )
  }

  if (uxState === "unconfigured" || uxState === "configuring_url") {
    return (
      <div
        data-testid="persona-route-root"
        className={routeRootClassName}
      >
        {routeHeader}
        <div className="p-4">
          <FeatureEmptyState
            title={
              isCompanionMode
                ? "Finish setup to use Companion"
                : "Finish setup to use Persona"
            }
            description={
              isCompanionMode
                ? "Companion conversation depends on a configured tldw server before you can start a session."
                : "Persona streaming depends on a configured tldw server before you can start a session."
            }
            primaryActionLabel={setupActionLabel}
            onPrimaryAction={openSetup}
          />
        </div>
      </div>
    )
  }

  if (uxState === "error_unreachable") {
    return (
      <div
        data-testid="persona-route-root"
        className={routeRootClassName}
      >
        {routeHeader}
        <div className="p-4">
          <FeatureEmptyState
            title="Can't reach your tldw server right now"
            description={
              isCompanionMode
                ? "Companion conversation depends on a reachable tldw server. Review your server status and URL before trying again."
                : "Persona streaming depends on a reachable tldw server. Review your server status and URL before trying again."
            }
            primaryActionLabel={
              shell === "options"
                ? "Health & diagnostics"
                : settingsLabel
            }
            onPrimaryAction={
              shell === "options" ? openDiagnostics : openSettings
            }
            secondaryActionLabel={
              shell === "options" ? settingsLabel : undefined
            }
            onSecondaryAction={
              shell === "options" ? openSettings : undefined
            }
          />
        </div>
      </div>
    )
  }

  if (!isOnline) {
    return (
      <div
        data-testid="persona-route-root"
        className={routeRootClassName}
      >
        {routeHeader}
        <div className="p-4">
          <FeatureEmptyState
            title={
              isCompanionMode
                ? "Connect to use Companion"
                : t("sidepanel:persona.connectTitle", "Connect to use Persona")
            }
            description={
              isCompanionMode
                ? "Companion conversation runs on your tldw server. Connect to start a session."
                : t(
                    "sidepanel:persona.connectDescription",
                    "Persona streaming runs on your tldw server. Connect to a server to start a session."
                  )
            }
            primaryActionLabel={settingsLabel}
            onPrimaryAction={openSettings}
          />
        </div>
      </div>
    )
  }

  if (personaUnsupported) {
    return (
      <div
        data-testid="persona-route-root"
        className={routeRootClassName}
      >
        {routeHeader}
        <div className="p-4">
          <FeatureEmptyState
            title={
              isCompanionMode
                ? "Companion unavailable"
                : t("sidepanel:persona.unavailableTitle", "Persona unavailable")
            }
            description={
              isCompanionMode
                ? "This server does not currently advertise persona support for companion conversation."
                : t(
                    "sidepanel:persona.unavailableDescription",
                    "This server does not currently advertise persona support."
                  )
            }
            primaryActionLabel={t("sidepanel:header.settingsShortLabel", "Settings")}
            onPrimaryAction={() => navigate("/settings")}
          />
        </div>
      </div>
    )
  }

  return (
    <div
      data-testid="persona-route-root"
      className={routeRootClassName}
    >
      {routeHeader}
      {isCompanionMode ? (
        <div className="flex flex-1 flex-col gap-3 p-3">
          {liveSessionControls}
          {liveSessionStatusPanels}
          {pendingPlanCard}
          {transcriptPanel}
          {composerPanel}
        </div>
      ) : (
        <div className="flex flex-1 flex-col p-3">
          {personaSetupWizard.isSetupRequired && !setupCommandDetour && !setupLiveDetour ? (
            <AssistantSetupWizard
              catalog={catalog.map((persona) => ({
                id: String(persona.id || ""),
                name: String(persona.name || persona.id || "")
              }))}
              selectedPersonaId={selectedPersonaId}
              currentStep={personaSetupWizard.currentStep}
              postSetupTargetTab={setupIntentTargetTab || activeTab}
              progressItems={assistantSetupProgressItems}
              onResetSetup={handleResetSetup}
              voiceStepContent={
                personaSetupWizard.currentStep === "voice" ? (
                  <AssistantDefaultsPanel
                    selectedPersonaId={selectedPersonaId}
                    selectedPersonaName={selectedPersonaName}
                    isActive
                    analytics={null}
                    analyticsLoading={false}
                    onSaved={() => {
                      void handleSetupVoiceDefaultsSaved()
                    }}
                  />
                ) : undefined
              }
              commandsStepContent={
                personaSetupWizard.currentStep === "commands" ? (
                  <SetupStarterCommandsStep
                    saving={setupWizardSaving}
                    error={setupStepErrors.commands || null}
                    onCreateFromTemplate={(templateKey) => {
                      void handleCreateStarterCommandFromTemplate(templateKey)
                    }}
                    onCreateMcpStarter={(toolName, phrase) => {
                      void handleCreateMcpStarterCommand(toolName, phrase)
                    }}
                    onSkip={() => {
                      setSetupReviewSummaryDraft((current) => ({
                        ...current,
                        starterCommands: { mode: "skipped" }
                      }))
                      void advancePersonaSetupStep(
                        "safety",
                        "Failed to advance assistant setup",
                        undefined,
                        "commands"
                      )
                    }}
                  />
                ) : undefined
              }
              safetyStepContent={
                personaSetupWizard.currentStep === "safety" ? (
                  <SetupSafetyConnectionsStep
                    saving={setupWizardSaving}
                    error={setupStepErrors.safety || null}
                    currentConfirmationMode={
                      savedPersonaVoiceDefaults?.confirmation_mode || "destructive_only"
                    }
                    onContinue={(payload) => {
                      void handleSetupSafetyStepContinue(payload)
                    }}
                  />
                ) : undefined
              }
              testStepContent={
                personaSetupWizard.currentStep === "test" ? (
                  <SetupTestAndFinishStep
                    saving={setupWizardSaving}
                    dryRunLoading={setupWizardDryRunLoading}
                    liveConnected={connected}
                    error={setupStepErrors.test || null}
                    initialHeardText={setupNoMatchPhrase}
                    notice={setupTestResumeNote}
                    outcome={setupTestOutcome}
                    onRunDryRun={(heardText) => {
                      void handleRunSetupDryRun(heardText)
                    }}
                    onCreateCommandFromPhrase={handleCreateCommandFromSetupNoMatch}
                    onConnectLive={() => {
                      void connect()
                    }}
                    onRecoverInLiveSession={handleRecoverSetupInLiveSession}
                    onSendLive={(text) => {
                      sendSetupLiveTestMessage(text)
                    }}
                    onFinishWithDryRun={() => {
                      void completePersonaSetup("dry_run")
                    }}
                    onFinishWithLiveSession={() => {
                      void completePersonaSetup("live_session")
                    }}
                  />
                ) : undefined
              }
              saving={setupWizardSaving}
              error={currentSetupWizardError}
              onUsePersona={handleUsePersonaForSetup}
              onCreatePersona={handleCreatePersonaForSetup}
            />
          ) : (
            <PersonaGardenTabs
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key as PersonaGardenTabKey)}
              items={tabItems}
            />
          )}
        </div>
      )}
    </div>
  )
}

export default SidepanelPersona
