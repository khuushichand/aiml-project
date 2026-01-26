import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline"
import {
  Segmented,
  Space,
  Input,
  Alert,
  Form,
  Modal,
  Spin,
  Button,
  Select,
  Collapse,
  Tag
} from "antd"
import { Link, useNavigate } from "react-router-dom"
import React, { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { isFirefoxTarget } from "@/config/platform"
import { tldwClient, TldwConfig } from "@/services/tldw/TldwApiClient"
import { tldwAuth } from "@/services/tldw/TldwAuth"
import { SettingsSkeleton } from "@/components/Common/Settings/SettingsSkeleton"
import { DEFAULT_TLDW_API_KEY } from "@/services/tldw-server"
import { apiSend } from "@/services/api-send"
import type { PathOrUrl } from "@/services/tldw/openapi-guard"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import { useConnectionStore } from "@/store/connection"
import { mapMultiUserLoginErrorMessage } from "@/services/auth-errors"
import { ServerOverviewHint } from "@/components/Common/ServerOverviewHint"

type TimeoutPresetKey = 'balanced' | 'extended'
type LoginMethod = 'magic-link' | 'password'

type TimeoutValues = {
  request: number
  stream: number
  chatRequest: number
  chatStream: number
  ragRequest: number
  media: number
  upload: number
}

type BillingPlan = {
  name: string
  display_name: string
  description?: string
  price_usd_monthly?: number
  price_usd_yearly?: number
  limits?: Record<string, any>
}

type BillingSubscription = {
  plan_name: string
  plan_display_name: string
  status: string
  billing_cycle?: string | null
  current_period_end?: string | null
  trial_end?: string | null
  cancel_at_period_end?: boolean
  limits?: Record<string, any>
}

type BillingUsage = {
  plan_name?: string
  limits?: Record<string, any>
  usage?: Record<string, number>
  limit_checks?: Record<string, {
    limit?: number | null
    current?: number
    exceeded?: boolean
    warning?: boolean
    unlimited?: boolean
    percent_used?: number
  }>
  has_warnings?: boolean
  has_exceeded?: boolean
}

const TIMEOUT_PRESETS: Record<TimeoutPresetKey, TimeoutValues> = {
  balanced: {
    request: 10,
    stream: 15,
    chatRequest: 10,
    chatStream: 15,
    ragRequest: 10,
    media: 60,
    upload: 60
  },
  extended: {
    request: 20,
    stream: 30,
    chatRequest: 20,
    chatStream: 30,
    ragRequest: 20,
    media: 90,
    upload: 90
  }
}

const BILLING_BASE_URL = "https://vademhq.com"
const BILLING_SUCCESS_URL = `${BILLING_BASE_URL}/billing/success`
const BILLING_CANCEL_URL = `${BILLING_BASE_URL}/billing/cancel`
const BILLING_RETURN_URL = `${BILLING_BASE_URL}/billing`

type CoreStatus = 'unknown' | 'checking' | 'connected' | 'failed'
type RagStatus = 'healthy' | 'unhealthy' | 'unknown' | 'checking'

export const TldwSettings = () => {
  const { t } = useTranslation(["settings", "common"])
  const message = useAntdMessage()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [initializing, setInitializing] = useState(true)
  const [initializingError, setInitializingError] = useState<string | null>(null)
  const [testingConnection, setTestingConnection] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<'success' | 'error' | null>(null)
  const [connectionDetail, setConnectionDetail] = useState<string>("")
  const [coreStatus, setCoreStatus] = useState<CoreStatus>("unknown")
  const [ragStatus, setRagStatus] = useState<RagStatus>("unknown")
  const [authMode, setAuthMode] = useState<'single-user' | 'multi-user'>('single-user')
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [loginMethod, setLoginMethod] = useState<LoginMethod>('magic-link')
  const [magicEmail, setMagicEmail] = useState("")
  const [magicToken, setMagicToken] = useState("")
  const [magicSent, setMagicSent] = useState(false)
  const [magicSending, setMagicSending] = useState(false)
  const [serverUrl, setServerUrl] = useState("")
  const [requestTimeoutSec, setRequestTimeoutSec] = useState<number>(10)
  const [streamIdleTimeoutSec, setStreamIdleTimeoutSec] = useState<number>(15)
  const [chatRequestTimeoutSec, setChatRequestTimeoutSec] = useState<number>(10)
  const [chatStreamIdleTimeoutSec, setChatStreamIdleTimeoutSec] = useState<number>(15)
  const [ragRequestTimeoutSec, setRagRequestTimeoutSec] = useState<number>(10)
  const [mediaRequestTimeoutSec, setMediaRequestTimeoutSec] = useState<number>(60)
  const [uploadRequestTimeoutSec, setUploadRequestTimeoutSec] = useState<number>(60)
  const [timeoutPreset, setTimeoutPreset] = useState<TimeoutPresetKey | 'custom'>('balanced')
  const [showDefaultKeyWarning, setShowDefaultKeyWarning] = useState(false)
  const [billingLoading, setBillingLoading] = useState(false)
  const [billingError, setBillingError] = useState<string | null>(null)
  const [billingPlans, setBillingPlans] = useState<BillingPlan[]>([])
  const [billingStatus, setBillingStatus] = useState<BillingSubscription | null>(null)
  const [billingUsage, setBillingUsage] = useState<BillingUsage | null>(null)
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')

  const determinePreset = (values: TimeoutValues): TimeoutPresetKey | 'custom' => {
    for (const [key, presetValues] of Object.entries(TIMEOUT_PRESETS) as [TimeoutPresetKey, typeof TIMEOUT_PRESETS[TimeoutPresetKey]][]) {
      const matches =
        presetValues.request === values.request &&
        presetValues.stream === values.stream &&
        presetValues.chatRequest === values.chatRequest &&
        presetValues.chatStream === values.chatStream &&
        presetValues.ragRequest === values.ragRequest &&
        presetValues.media === values.media &&
        presetValues.upload === values.upload
      if (matches) {
        return key
      }
    }
    return 'custom'
  }

  const applyTimeoutPreset = (preset: TimeoutPresetKey) => {
    const presetValues = TIMEOUT_PRESETS[preset]
    setRequestTimeoutSec(presetValues.request)
    setStreamIdleTimeoutSec(presetValues.stream)
    setChatRequestTimeoutSec(presetValues.chatRequest)
    setChatStreamIdleTimeoutSec(presetValues.chatStream)
    setRagRequestTimeoutSec(presetValues.ragRequest)
    setMediaRequestTimeoutSec(presetValues.media)
    setUploadRequestTimeoutSec(presetValues.upload)
    setTimeoutPreset(preset)
  }

  const parseSeconds = (value: string, fallback: number) => {
    const parsed = parseInt(value, 10)
    return Number.isNaN(parsed) ? fallback : parsed
  }

  const coreStatusColor = (status: CoreStatus) => {
    switch (status) {
      case "connected":
        return "green"
      case "failed":
        return "red"
      default:
        return "default"
    }
  }

  const coreStatusLabel = (status: CoreStatus) => {
    switch (status) {
      case "checking":
        return t("settings:tldw.connection.coreChecking", "Core: checking…")
      case "connected":
        return t("settings:tldw.connection.coreOk", "Core: reachable")
      case "failed":
        return t("settings:tldw.connection.coreFailed", "Core: unreachable")
      default:
        return t("settings:tldw.connection.coreUnknown", "Core: waiting")
    }
  }

  const ragStatusColor = (status: RagStatus) => {
    switch (status) {
      case "healthy":
        return "green"
      case "unhealthy":
        return "red"
      default:
        return "default"
    }
  }

  const ragStatusLabel = (status: RagStatus) => {
    switch (status) {
      case "checking":
        return t("settings:tldw.connection.ragChecking", "RAG: checking…")
      case "healthy":
        return t("settings:tldw.connection.ragHealthy", "RAG: healthy")
      case "unhealthy":
        return t("settings:tldw.connection.ragUnhealthy", "RAG: needs attention")
      default:
        return t("settings:tldw.connection.ragUnknown", "RAG: waiting")
    }
  }

  const formatNumber = (value?: number | null) => {
    if (value === null || value === undefined) {
      return t('settings:tldw.billing.unknown', '—')
    }
    if (Number.isFinite(value)) {
      return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
    }
    return String(value)
  }

  const formatLimitValue = (value?: number | null, unlimited?: boolean) => {
    if (unlimited) {
      return t('settings:tldw.billing.unlimited', 'Unlimited')
    }
    if (value === null || value === undefined) {
      return t('settings:tldw.billing.unknown', '—')
    }
    if (value === -1) {
      return t('settings:tldw.billing.unlimited', 'Unlimited')
    }
    return formatNumber(value)
  }

  const formatUsageLabel = (key: string) => {
    const map: Record<string, string> = {
      api_calls_day: t('settings:tldw.billing.usage.apiCallsDay', 'API calls / day'),
      llm_tokens_month: t('settings:tldw.billing.usage.llmTokensMonth', 'LLM tokens / month'),
      storage_mb: t('settings:tldw.billing.usage.storageMb', 'Storage (MB)'),
      team_members: t('settings:tldw.billing.usage.teamMembers', 'Team members'),
      transcription_minutes_month: t('settings:tldw.billing.usage.transcriptionMinutes', 'Transcription minutes / month'),
      rag_queries_day: t('settings:tldw.billing.usage.ragQueriesDay', 'RAG queries / day'),
      concurrent_jobs: t('settings:tldw.billing.usage.concurrentJobs', 'Concurrent jobs')
    }
    return map[key] || key.replace(/_/g, ' ')
  }

  const formatPlanPrice = (plan: BillingPlan, cycle: 'monthly' | 'yearly') => {
    const price =
      cycle === 'yearly'
        ? plan.price_usd_yearly
        : plan.price_usd_monthly
    if (typeof price === 'number' && !Number.isNaN(price)) {
      const suffix = cycle === 'yearly' ? 'yr' : 'mo'
      return `$${price.toLocaleString()}/${suffix}`
    }
    return t('settings:tldw.billing.customPrice', 'Custom')
  }

  const formatDate = (value?: string | null) => {
    if (!value) return t('settings:tldw.billing.unknown', '—')
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
      return value
    }
    return parsed.toLocaleDateString()
  }

  const billingStatusColor = (status?: string | null) => {
    switch (status) {
      case "active":
        return "green"
      case "trialing":
        return "blue"
      case "past_due":
        return "orange"
      case "canceling":
        return "gold"
      case "canceled":
        return "red"
      default:
        return "default"
    }
  }

  const billingStatusLabel = (status?: string | null) => {
    switch (status) {
      case "active":
        return t('settings:tldw.billing.status.active', 'Active')
      case "trialing":
        return t('settings:tldw.billing.status.trialing', 'Trialing')
      case "past_due":
        return t('settings:tldw.billing.status.pastDue', 'Past due')
      case "canceling":
        return t('settings:tldw.billing.status.canceling', 'Canceling')
      case "canceled":
        return t('settings:tldw.billing.status.canceled', 'Canceled')
      default:
        return t('settings:tldw.billing.status.unknown', 'Unknown')
    }
  }

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    setLoading(true)
    setInitializingError(null)
    try {
      const config = await tldwClient.getConfig()
      if (config) {
        setAuthMode(config.authMode)
        setServerUrl(config.serverUrl)
        const nextTimeouts = { ...TIMEOUT_PRESETS.balanced }
        if (typeof (config as any).requestTimeoutMs === 'number') nextTimeouts.request = Math.round((config as any).requestTimeoutMs / 1000)
        if (typeof (config as any).streamIdleTimeoutMs === 'number') nextTimeouts.stream = Math.round((config as any).streamIdleTimeoutMs / 1000)
        if (typeof (config as any).chatRequestTimeoutMs === 'number') nextTimeouts.chatRequest = Math.round((config as any).chatRequestTimeoutMs / 1000)
        if (typeof (config as any).chatStreamIdleTimeoutMs === 'number') nextTimeouts.chatStream = Math.round((config as any).chatStreamIdleTimeoutMs / 1000)
        if (typeof (config as any).ragRequestTimeoutMs === 'number') nextTimeouts.ragRequest = Math.round((config as any).ragRequestTimeoutMs / 1000)
        if (typeof (config as any).mediaRequestTimeoutMs === 'number') nextTimeouts.media = Math.round((config as any).mediaRequestTimeoutMs / 1000)
        if (typeof (config as any).uploadRequestTimeoutMs === 'number') nextTimeouts.upload = Math.round((config as any).uploadRequestTimeoutMs / 1000)

        setRequestTimeoutSec(nextTimeouts.request)
        setStreamIdleTimeoutSec(nextTimeouts.stream)
        setChatRequestTimeoutSec(nextTimeouts.chatRequest)
        setChatStreamIdleTimeoutSec(nextTimeouts.chatStream)
        setRagRequestTimeoutSec(nextTimeouts.ragRequest)
        setMediaRequestTimeoutSec(nextTimeouts.media)
        setUploadRequestTimeoutSec(nextTimeouts.upload)
        setTimeoutPreset(determinePreset(nextTimeouts))
        form.setFieldsValue({
          serverUrl: config.serverUrl,
          apiKey: config.apiKey,
          authMode: config.authMode
        })
        
        // Check if logged in for multi-user mode
        if (config.authMode === 'multi-user' && config.accessToken) {
          setIsLoggedIn(true)
        }
      } else {
        setTimeoutPreset('balanced')
      }
      setInitializingError(null)
    } catch (error) {
      console.error('Failed to load config:', error)
      setInitializingError(
        (error as Error)?.message ||
          t('settings:tldw.loadError', 'Unable to load tldw server settings. Check your connection and try again.')
      )
    } finally {
      setLoading(false)
      setInitializing(false)
    }
  }

  const handleSave = async (values: any) => {
    setLoading(true)
    try {
      const config: Partial<TldwConfig & {
        requestTimeoutMs?: number
        streamIdleTimeoutMs?: number
        chatRequestTimeoutMs?: number
        chatStreamIdleTimeoutMs?: number
        ragRequestTimeoutMs?: number
        mediaRequestTimeoutMs?: number
        uploadRequestTimeoutMs?: number
      }> = {
        serverUrl: values.serverUrl,
        authMode: values.authMode,
        // Clamp timeout values to prevent integer overflow (max ~24 days in seconds = 2147483 to avoid JS int overflow)
        requestTimeoutMs: Math.min(2147483000, Math.max(1, Math.round(Number(requestTimeoutSec) || 10)) * 1000),
        streamIdleTimeoutMs: Math.min(2147483000, Math.max(1, Math.round(Number(streamIdleTimeoutSec) || 15)) * 1000),
        chatRequestTimeoutMs: Math.min(2147483000, Math.max(1, Math.round(Number(chatRequestTimeoutSec) || requestTimeoutSec || 10)) * 1000),
        chatStreamIdleTimeoutMs: Math.min(2147483000, Math.max(1, Math.round(Number(chatStreamIdleTimeoutSec) || streamIdleTimeoutSec || 15)) * 1000),
        ragRequestTimeoutMs: Math.min(2147483000, Math.max(1, Math.round(Number(ragRequestTimeoutSec) || requestTimeoutSec || 10)) * 1000),
        mediaRequestTimeoutMs: Math.min(2147483000, Math.max(1, Math.round(Number(mediaRequestTimeoutSec) || requestTimeoutSec || 10)) * 1000),
        uploadRequestTimeoutMs: Math.min(2147483000, Math.max(1, Math.round(Number(uploadRequestTimeoutSec) || mediaRequestTimeoutSec || 60)) * 1000)
      }

      if (values.authMode === 'single-user') {
        config.apiKey = values.apiKey
        // Clear multi-user tokens
        config.accessToken = undefined
        config.refreshToken = undefined
      }

      await tldwClient.updateConfig(config)

      // Request optional host permission for the configured origin on Chromium-based browsers
      try {
        const origin = new URL(values.serverUrl).origin
        const chromePermissions = (
          globalThis as {
            chrome?: {
              permissions?: {
                request?: (
                  options: { origins: string[] },
                  callback: (granted: boolean) => void
                ) => void
              }
            }
          }
        ).chrome?.permissions
        if (chromePermissions?.request) {
          chromePermissions.request({ origins: [origin + '/*'] }, (granted) => {
            if (!granted) {
              console.warn('Permission not granted for origin:', origin)
            }
          })
        }
      } catch (e) {
        console.warn('Could not request optional host permission:', e)
      }
      message.success(t("settings:savedSuccessfully"))
      
      // Test connection after saving
      await testConnection()
    } catch (error) {
      message.error(t("settings:saveFailed"))
      console.error('Failed to save config:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadBilling = async () => {
    if (authMode !== 'multi-user' || !isLoggedIn) return
    setBillingLoading(true)
    setBillingError(null)
    try {
      const [plansResp, subResp, usageResp] = await Promise.all([
        apiSend<{ plans?: BillingPlan[] }>({
          path: "/api/v1/billing/plans" as PathOrUrl,
          method: "GET"
        }),
        apiSend<BillingSubscription>({
          path: "/api/v1/billing/subscription" as PathOrUrl,
          method: "GET"
        }),
        apiSend<BillingUsage>({
          path: "/api/v1/billing/usage" as PathOrUrl,
          method: "GET"
        })
      ])
      const plans = plansResp?.data?.plans || []
      const subscription = subResp?.data || null
      const usage = usageResp?.data || null

      setBillingPlans(plans)
      setBillingStatus(subscription)
      setBillingUsage(usage)

      if (!plansResp?.ok || !subResp?.ok || !usageResp?.ok) {
        const errorMsg =
          plansResp?.error ||
          subResp?.error ||
          usageResp?.error ||
          'Failed to load billing details'
        setBillingError(errorMsg)
      }

      if (!selectedPlan) {
        if (subscription?.plan_name) {
          setSelectedPlan(subscription.plan_name)
        } else if (plans.length > 0) {
          setSelectedPlan(plans[0].name)
        }
      }
      if (subscription?.billing_cycle) {
        setBillingCycle(subscription.billing_cycle === 'yearly' ? 'yearly' : 'monthly')
      }
    } catch (err: any) {
      setBillingError(err?.message || 'Failed to load billing details')
    } finally {
      setBillingLoading(false)
    }
  }

  useEffect(() => {
    if (authMode === 'multi-user' && isLoggedIn) {
      void loadBilling()
    }
  }, [authMode, isLoggedIn])

  const testConnection = async () => {
    setTestingConnection(true)
    setConnectionStatus(null)
    setConnectionDetail("")
    setCoreStatus("checking")
    setRagStatus("unknown")
    
    try {
      const values = form.getFieldsValue()
      const errors = await form.validateFields(["serverUrl"]).catch(e => e)
      if (errors?.errorFields?.length) {
        return
      }
      let success = false

      // Test core connectivity via the health endpoint only, so we never
      // rely on the LLM provider for connection checks.
      const baseUrl = String(values.serverUrl || '').replace(/\/$/, '')
      const healthPath: PathOrUrl = (baseUrl
        ? `${baseUrl}/api/v1/health`
        : "/api/v1/health") as PathOrUrl
      const singleUser = values.authMode === "single-user"
      const hasApiKey =
        singleUser && typeof values.apiKey === "string" && values.apiKey.trim().length > 0

      const resp = await apiSend({
        path: healthPath,
        method: "GET",
        // For single-user mode, send the API key explicitly and bypass
        // background auth injection so we validate the current form values.
        headers:
          hasApiKey && baseUrl
            ? { "X-API-KEY": String(values.apiKey).trim() }
            : undefined,
        noAuth: hasApiKey && baseUrl ? true : false
      })

      success = !!resp?.ok
      setCoreStatus(success ? "connected" : "failed")

      if (!success) {
        const code = resp?.status
        const detail = resp?.error || ""

        if (code === 401 || code === 403) {
          const hint =
            code === 401
              ? t(
                  "settings:tldw.errors.invalidApiKey",
                  "Invalid API key"
                )
              : t(
                  "settings:tldw.errors.forbidden",
                  "Forbidden (check permissions)"
                )
          const healthHint = t(
            "settings:tldw.errors.seeHealth",
            "Open Health & diagnostics for more details."
          )
          const suffix = code ? ` — HTTP ${code}` : ""
          const extra = detail ? ` (${detail})` : ""
          setConnectionDetail(`${hint}${suffix} — ${healthHint}${extra}`)
        } else {
          const base = t(
            "settings:tldw.errors.serverUnreachableDetailed",
            "Server not reachable. Check that your tldw_server is running and that your browser can reach it, then try again. Health & diagnostics can help debug connectivity issues."
          )
          const suffix = code ? ` — HTTP ${code}` : ""
          const extra = detail ? ` (${detail})` : ""
          setConnectionDetail(`${base}${suffix}${extra}`)
        }
      }

      setConnectionStatus(success ? 'success' : 'error')
      // Probe RAG health after core connection test when server URL is present
      try {
        setRagStatus("checking")
        await tldwClient.initialize()
        const rag = await tldwClient.ragHealth()
        setRagStatus('healthy')
      } catch (e) {
        setRagStatus('unhealthy')
      }
      
      if (success) {
        message.success(t('settings:tldw.connection.success', 'Connection successful!'))
        if (
          values.authMode === 'single-user' &&
          typeof values.apiKey === 'string' &&
          values.apiKey.trim() === DEFAULT_TLDW_API_KEY
        ) {
          setShowDefaultKeyWarning(true)
        } else {
          setShowDefaultKeyWarning(false)
        }
        await tldwClient.initialize()
        try {
          // Refresh shared connection state so entry views transition
          // from the connection card to the live chat/media UI.
          await useConnectionStore.getState().checkOnce()
        } catch {
          // Best-effort only; ignore failures here.
        }
      } else {
        message.error(t('settings:tldw.connection.failed', 'Connection failed. Please check your settings.'))
        setShowDefaultKeyWarning(false)
      }
    } catch (error) {
      setConnectionStatus('error')
      setCoreStatus("failed")
      const raw = (error as any)?.message || ''
      const friendly =
        raw && /network|timeout|failed to fetch/i.test(raw)
          ? t(
              'settings:tldw.errors.serverUnreachableDetailed',
              'Server not reachable. Check that your tldw_server is running and that your browser can reach it, then try again. Health & diagnostics can help debug connectivity issues.'
            )
          : raw ||
            t(
              'settings:tldw.errors.connectionFailedDetailed',
              'Connection failed. Please check your server URL and API key, then open Health & diagnostics for more details.'
            )
      setConnectionDetail(friendly)
      message.error(friendly)
      console.error('Connection test failed:', error)
    } finally {
      setTestingConnection(false)
    }
  }

  const grantSiteAccess = async () => {
    try {
      const values = form.getFieldsValue()
      const urlStr = String(values?.serverUrl || serverUrl || '')
      if (!urlStr) {
        message.warning(t('settings:enterServerUrlFirst', 'Enter a server URL first'))
        return
      }
      const origin = new URL(urlStr).origin
      const chromePermissions = (
        globalThis as {
          chrome?: {
            permissions?: {
              request?: (
                options: { origins: string[] },
                callback: (granted: boolean) => void
              ) => void
            }
          }
        }
      ).chrome?.permissions
      if (!chromePermissions?.request) {
        message.info(t('settings:siteAccessChromiumOnly', 'Site access is only needed on Chrome/Edge'))
        return
      }
      chromePermissions.request({ origins: [origin + '/*'] }, (granted) => {
        if (granted) message.success(t('settings:siteAccessGranted', 'Host permission granted for {{origin}}', { origin }))
        else message.warning(t('settings:siteAccessDenied', 'Permission not granted for {{origin}}', { origin }))
      })
    } catch (e: any) {
      message.error(t('settings:siteAccessFailed', 'Failed to request site access: {{msg}}', { msg: e?.message || String(e) }))
    }
  }

  const handleLogin = async () => {
    try {
      const values = await form.validateFields(['username', 'password'])
      setLoading(true)
      
      await tldwAuth.login({
        username: values.username,
        password: values.password
      })
      
      setIsLoggedIn(true)
      message.success(t('settings:tldw.login.success', 'Login successful!'))
      
      // Clear password field
      form.setFieldValue('password', '')
      
      // Test connection after login
      await testConnection()
    } catch (error: any) {
      const friendly = mapMultiUserLoginErrorMessage(
        t,
        error,
        'settings'
      )
      message.error(friendly)
      console.error('Login failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSendMagicLink = async () => {
    if (!magicEmail.trim()) {
      message.warning(
        t('settings:tldw.magicLink.missingEmail', 'Enter your email to receive a magic link.')
      )
      return
    }
    setMagicSending(true)
    try {
      await tldwAuth.requestMagicLink(magicEmail.trim())
      setMagicSent(true)
      message.success(
        t('settings:tldw.magicLink.sent', 'Magic link sent. Check your inbox.')
      )
    } catch (error: any) {
      const friendly = mapMultiUserLoginErrorMessage(t, error, 'settings')
      message.error(friendly)
      console.error('Magic link request failed:', error)
    } finally {
      setMagicSending(false)
    }
  }

  const handleVerifyMagicLink = async () => {
    if (!magicToken.trim()) {
      message.warning(
        t('settings:tldw.magicLink.missingToken', 'Paste the magic link token to continue.')
      )
      return
    }
    setLoading(true)
    try {
      await tldwAuth.verifyMagicLink(magicToken.trim())
      setIsLoggedIn(true)
      message.success(t('settings:tldw.login.success', 'Login successful!'))
      setMagicToken('')
      await testConnection()
    } catch (error: any) {
      const friendly = mapMultiUserLoginErrorMessage(t, error, 'settings')
      message.error(friendly)
      console.error('Magic link login failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      setLoading(true)
      await tldwAuth.logout()
      setIsLoggedIn(false)
      message.success(t('settings:tldw.logout.success', 'Logged out successfully'))
    } catch (error) {
      message.error(t('settings:tldw.logout.failed', 'Logout failed'))
      console.error('Logout failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCheckout = async () => {
    if (!selectedPlan) {
      message.warning(t('settings:tldw.billing.missingPlan', 'Select a plan to continue.'))
      return
    }
    setBillingLoading(true)
    try {
      const resp = await apiSend<{ url?: string }>({
        path: "/api/v1/billing/checkout" as PathOrUrl,
        method: "POST",
        body: {
          plan_name: selectedPlan,
          billing_cycle: billingCycle,
          success_url: BILLING_SUCCESS_URL,
          cancel_url: BILLING_CANCEL_URL
        }
      })
      if (resp?.data?.url) {
        window.open(resp.data.url, "_blank", "noopener,noreferrer")
      } else if (!resp?.ok) {
        message.error(resp?.error || t('settings:tldw.billing.checkoutFailed', 'Checkout failed.'))
      } else {
        message.error(t('settings:tldw.billing.checkoutFailed', 'Checkout failed.'))
      }
    } catch (error: any) {
      message.error(error?.message || t('settings:tldw.billing.checkoutFailed', 'Checkout failed.'))
    } finally {
      setBillingLoading(false)
    }
  }

  const handleBillingPortal = async () => {
    setBillingLoading(true)
    try {
      const resp = await apiSend<{ url?: string }>({
        path: "/api/v1/billing/portal" as PathOrUrl,
        method: "POST",
        body: { return_url: BILLING_RETURN_URL }
      })
      if (resp?.data?.url) {
        window.open(resp.data.url, "_blank", "noopener,noreferrer")
      } else if (!resp?.ok) {
        message.error(resp?.error || t('settings:tldw.billing.portalFailed', 'Unable to open billing portal.'))
      } else {
        message.error(t('settings:tldw.billing.portalFailed', 'Unable to open billing portal.'))
      }
    } catch (error: any) {
      message.error(error?.message || t('settings:tldw.billing.portalFailed', 'Unable to open billing portal.'))
    } finally {
      setBillingLoading(false)
    }
  }

  const openHealthDiagnostics = () => {
    navigate("/settings/health")
  }

  const selectedPlanDetails = billingPlans.find((plan) => plan.name === selectedPlan) || null
  const planOptions = billingPlans.map((plan) => ({
    value: plan.name,
    label: (
      <div className="flex items-center justify-between gap-2">
        <span>{plan.display_name}</span>
        <span className="text-xs text-text-muted">
          {formatPlanPrice(plan, billingCycle)}
        </span>
      </div>
    )
  }))

  const usageOrder = [
    "api_calls_day",
    "llm_tokens_month",
    "storage_mb",
    "team_members",
    "transcription_minutes_month",
    "rag_queries_day",
    "concurrent_jobs"
  ]
  const usageEntries = Object.entries(billingUsage?.usage ?? {})
  const usageChecks = billingUsage?.limit_checks ?? {}
  const sortedUsageEntries = usageEntries.sort((a, b) => {
    const aIndex = usageOrder.indexOf(a[0])
    const bIndex = usageOrder.indexOf(b[0])
    const aRank = aIndex === -1 ? usageOrder.length + 1 : aIndex
    const bRank = bIndex === -1 ? usageOrder.length + 1 : bIndex
    if (aRank !== bRank) return aRank - bRank
    return a[0].localeCompare(b[0])
  })

  const isSamePlan = !!billingStatus?.plan_name && selectedPlan === billingStatus?.plan_name
  const isSameCycle = !!billingStatus?.billing_cycle && billingStatus?.billing_cycle === billingCycle

  if (initializing) {
    return (
      <div className="max-w-2xl">
        <SettingsSkeleton sections={3} />
      </div>
    )
  }

  return (
    <Spin
      spinning={loading}
      tip={loading ? t('common:saving', 'Saving...') : undefined}>
      <div className="max-w-2xl">
        {initializingError && (
          <Alert
            type="error"
            showIcon
            closable
            className="mb-4"
            message={t('settings:tldw.loadError', 'Unable to load tldw settings')}
            description={initializingError}
            onClose={() => setInitializingError(null)}
          />
        )}
        {showDefaultKeyWarning && authMode === 'single-user' && (
          <Alert
            type="warning"
            showIcon
            closable
            className="mb-4"
            message={t(
              'settings:tldw.defaultKeyWarning.title',
              'Default demo API key in use'
            )}
            description={t(
              'settings:tldw.defaultKeyWarning.body',
              'You are using the default demo API key for tldw_server. For production or shared deployments, rotate the key on your server and update it here. Continue at your own risk.'
            )}
            onClose={() => setShowDefaultKeyWarning(false)}
          />
        )}
        <div className="mb-4 rounded-lg bg-surface2 p-4">
          <h3 className="mb-2 font-semibold">
            {t(
              "settings:tldw.about.title",
              "About tldw server integration"
            )}
          </h3>
          <p className="text-sm text-text-muted">
            {t(
              "settings:tldw.about.description",
              "tldw server turns this extension into a full workspace for chat, knowledge search, and media."
            )}
          </p>
          <ServerOverviewHint />
        </div>
        <div className="mb-4 p-2 rounded border border-transparent bg-transparent flex items-center justify-between transition-colors duration-150 hover:border-border hover:bg-surface2">
          <div className="text-sm text-text">
            <span className="mr-2 font-medium">{t('settings:tldw.serverLabel', 'Server:')}</span>
            <span className="text-text-muted break-all">{serverUrl || t('settings:tldw.notConfigured', 'Not configured')}</span>
          </div>
          <Space>
            <Link to="/settings/health">
              <Button>{t('settings:tldw.buttons.health', 'Health')}</Button>
            </Link>
            <Button type="primary" onClick={testConnection} loading={testingConnection}>{t('settings:tldw.buttons.recheck', 'Recheck')}</Button>
          </Space>
        </div>
        <h2 className="text-base font-semibold mb-4 text-text">{t('settings:tldw.serverConfigTitle', 'tldw Server Configuration')}</h2>
        
        <Form
          form={form}
          onFinish={handleSave}
          layout="vertical"
          initialValues={{
            authMode: 'single-user',
            apiKey: ''
          }}
        >
          <Form.Item
            label={t('settings:tldw.fields.serverUrl.label', 'Server URL')}
            name="serverUrl"
            rules={[
              { required: true, message: t('settings:tldw.fields.serverUrl.required', 'Please enter the server URL') as string },
              { type: 'url', message: t('settings:tldw.fields.serverUrl.invalid', 'Please enter a valid URL') as string }
            ]}
            extra={t(
              'settings:tldw.fields.serverUrl.extra',
              'The URL of your tldw_server instance. Default address for local installs: http://127.0.0.1:8000'
            )}
          >
            <Input
              placeholder={t(
                'settings:tldw.fields.serverUrl.placeholder',
                'http://127.0.0.1:8000'
              ) as string}
            />
          </Form.Item>
          <Form.Item
            label={t('settings:tldw.authMode.label', 'Authentication Mode')}
            name="authMode"
            rules={[{ required: true }]}
          >
            <Segmented
              options={[
                { label: t('settings:tldw.authMode.single', 'Single User (API Key)'), value: 'single-user' },
                { label: t('settings:tldw.authMode.multi', 'Multi User (Login)'), value: 'multi-user' }
              ]}
              onChange={(value) => {
                if (authMode !== value) {
                  Modal.confirm({
                    title: t('settings:tldw.authModeChangeWarning.title', 'Change authentication mode?'),
                    content: t('settings:tldw.authModeChangeWarning.content',
                      'Switching authentication modes will clear your current credentials. You will need to re-enter them after saving.'),
                    okText: t('common:continue', 'Continue'),
                    cancelText: t('common:cancel', 'Cancel'),
                    centered: true,
                    onOk: () => {
                      setAuthMode(value as 'single-user' | 'multi-user')
                      // Reset form fields for the new auth mode
                      if (value === 'multi-user') {
                        form.setFieldValue('apiKey', '')
                      } else {
                        form.setFieldValue('username', '')
                        form.setFieldValue('password', '')
                        setIsLoggedIn(false)
                      }
                    },
                    onCancel: () => {
                      // Reset the Segmented back to current value
                      form.setFieldValue('authMode', authMode)
                    }
                  })
                }
              }}
            />
          </Form.Item>
          {authMode === 'single-user' && (
            <Form.Item
              label={t('settings:tldw.fields.apiKey.label', 'API Key')}
              name="apiKey"
              rules={[{ required: true, message: t('settings:tldw.fields.apiKey.required', 'Please enter your API key') }]}
              extra={t('settings:tldw.fields.apiKey.extra', 'Your tldw_server API key for authentication')}
            >
              <Input.Password placeholder={t('settings:tldw.fields.apiKey.placeholder', 'Enter your API key')} />
            </Form.Item>
          )}

          {authMode === 'multi-user' && !isLoggedIn && (
            <>
              <Alert
                message={t('settings:tldw.loginRequired.title', 'Login Required')}
                description={t('settings:tldw.loginRequired.description', 'Please login with your tldw_server credentials')}
                type="info"
                showIcon
                className="mb-4"
              />
              <Form.Item
                label={t('settings:tldw.loginMethod.label', 'Login Method')}
              >
                <Segmented
                  options={[
                    { label: t('settings:tldw.loginMethod.magic', 'Magic link'), value: 'magic-link' },
                    { label: t('settings:tldw.loginMethod.password', 'Password'), value: 'password' }
                  ]}
                  value={loginMethod}
                  onChange={(value) => {
                    if (value === 'magic-link' || value === 'password') {
                      setLoginMethod(value)
                    }
                  }}
                />
              </Form.Item>

              {loginMethod === 'password' ? (
                <>
                  <Form.Item
                    label={t('settings:tldw.fields.username.label', 'Username')}
                    name="username"
                    rules={[{ required: true, message: t('settings:tldw.fields.username.required', 'Please enter your username') }]}
                  >
                    <Input placeholder={t('settings:tldw.fields.username.placeholder', 'Enter username')} />
                  </Form.Item>

                  <Form.Item
                    label={t('settings:tldw.fields.password.label', 'Password')}
                    name="password"
                    rules={[{ required: true, message: t('settings:tldw.fields.password.required', 'Please enter your password') }]}
                  >
                    <Input.Password placeholder={t('settings:tldw.fields.password.placeholder', 'Enter password')} />
                  </Form.Item>

                  <Form.Item>
                    <Button type="primary" onClick={handleLogin}>
                      {t('settings:tldw.buttons.login', 'Login')}
                    </Button>
                  </Form.Item>
                </>
              ) : (
                <>
                  <Form.Item
                    label={t('settings:tldw.magicLink.email.label', 'Email')}
                    name="magicEmail"
                    rules={[{ required: true, message: t('settings:tldw.magicLink.email.required', 'Please enter your email') }]}
                  >
                    <Input
                      placeholder={t('settings:tldw.magicLink.email.placeholder', 'you@company.com')}
                      value={magicEmail}
                      onChange={(e) => setMagicEmail(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item
                    label={t('settings:tldw.magicLink.token.label', 'Magic link token')}
                    name="magicToken"
                    rules={[{ required: true, message: t('settings:tldw.magicLink.token.required', 'Please paste your magic link token') }]}
                  >
                    <Input
                      placeholder={t('settings:tldw.magicLink.token.placeholder', 'Paste the token from your email')}
                      value={magicToken}
                      onChange={(e) => setMagicToken(e.target.value)}
                    />
                  </Form.Item>

                  <Form.Item>
                    <Space>
                      <Button onClick={handleSendMagicLink} loading={magicSending}>
                        {magicSent
                          ? t('settings:tldw.magicLink.resend', 'Resend magic link')
                          : t('settings:tldw.magicLink.send', 'Send magic link')}
                      </Button>
                      <Button type="primary" onClick={handleVerifyMagicLink}>
                        {t('settings:tldw.magicLink.verify', 'Verify & Login')}
                      </Button>
                    </Space>
                  </Form.Item>
                </>
              )}
            </>
          )}

          {authMode === 'multi-user' && isLoggedIn && (
            <Alert
              message={t('settings:tldw.loggedIn.title', 'Logged In')}
              description={t('settings:tldw.loggedIn.description', 'You are currently logged in to tldw_server')}
              type="success"
              showIcon
              action={
                <Button size="small" danger onClick={handleLogout}>
                  {t('settings:tldw.buttons.logout', 'Logout')}
                </Button>
              }
              className="mb-4"
            />
          )}

          <Space className="w-full justify-between">
            <Space>
              <Button type="primary" htmlType="submit">
                {t('common:save')}
              </Button>

              <Button
                onClick={testConnection}
                loading={testingConnection}
                icon={
                  connectionStatus === 'success' ? (
                    <CheckIcon className="w-4 h-4 text-green-500" />
                  ) : connectionStatus === 'error' ? (
                    <XMarkIcon className="w-4 h-4 text-red-500" />
                  ) : null
                }
              >
                {t('settings:tldw.buttons.testConnection', 'Test Connection')}
              </Button>

              {!isFirefoxTarget && (
                <Button onClick={grantSiteAccess}>
                  {t('settings:tldw.buttons.grantSiteAccess', 'Grant Site Access')}
                </Button>
              )}
            </Space>

            <div className="flex flex-col items-start gap-1 ml-4">
              {testingConnection && (
                <span className="text-xs text-text-subtle">
                  {t(
                    "settings:tldw.connection.checking",
                    "Checking connection and RAG health…"
                  )}
                </span>
              )}
              {connectionStatus && !testingConnection && (
                <span
                  className={`text-sm ${
                    connectionStatus === "success"
                      ? "text-green-500"
                      : "text-red-500"
                  }`}>
                  {connectionStatus === "success"
                    ? t(
                        "settings:tldw.connection.success",
                        "Connection successful!"
                      )
                    : t(
                        "settings:tldw.connection.failed",
                        "Connection failed. Please check your settings."
                      )}
                </span>
              )}
              {connectionDetail && connectionStatus !== "success" && (
                <span className="flex flex-wrap items-center gap-2 text-xs text-text-subtle">
                  <span>{connectionDetail}</span>
                  <button
                    type="button"
                    className="underline text-primary hover:text-primaryStrong"
                    onClick={openHealthDiagnostics}>
                    {t(
                      "settings:healthSummary.diagnostics",
                      "Health & diagnostics"
                    )}
                  </button>
                </span>
              )}
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                <span className="font-medium">
                  {t("settings:tldw.connection.checksLabel", "Checks")}
                </span>
                <Tag
                  color={coreStatusColor(coreStatus)}>
                  {coreStatusLabel(coreStatus)}
                </Tag>
                <Tag
                  color={ragStatusColor(ragStatus)}>
                  {ragStatusLabel(ragStatus)}
                </Tag>
              </div>
            </div>
          </Space>
          <Collapse
            className="mt-4"
            items={[
              {
                key: 'adv',
                label: t('settings:tldw.advancedTimeouts'),
                children: (
                  <div className="space-y-3">
                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-medium">
                        {t('settings:tldw.timeoutPresetLabel')}
                      </span>
                      <div className="flex flex-wrap items-center gap-3">
                        <Segmented
                          value={timeoutPreset === 'extended' ? 'extended' : 'balanced'}
                          onChange={(value) => applyTimeoutPreset(value as TimeoutPresetKey)}
                          options={[
                            {
                              label: t('settings:tldw.timeoutPresetBalanced'),
                              value: 'balanced'
                            },
                            {
                              label: t('settings:tldw.timeoutPresetExtended'),
                              value: 'extended'
                            }
                          ]}
                        />
                        {timeoutPreset === 'custom' && (
                          <Tag color="default">
                            {t('settings:tldw.timeoutPresetCustom')}
                          </Tag>
                        )}
                      </div>
                      <span className="text-xs text-text-subtle">
                        {t('settings:tldw.timeoutPresetHint')}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {t('settings:tldw.requestTimeout')}
                        </label>
                        <Input
                          type="number"
                          min={1}
                          value={requestTimeoutSec}
                          onChange={(e) => {
                            const newValue = parseSeconds(
                              e.target.value,
                              TIMEOUT_PRESETS.balanced.request
                            )
                            setRequestTimeoutSec(newValue)
                            setTimeoutPreset(
                              determinePreset({
                                request: newValue,
                                stream: streamIdleTimeoutSec,
                                chatRequest: chatRequestTimeoutSec,
                                chatStream: chatStreamIdleTimeoutSec,
                                ragRequest: ragRequestTimeoutSec,
                                media: mediaRequestTimeoutSec,
                                upload: uploadRequestTimeoutSec
                              })
                            )
                          }}
                          placeholder="10"
                          suffix="s"
                        />
                        <div className="text-xs text-text-subtle mt-1">
                          {t('settings:tldw.hints.requestTimeout', {
                            defaultValue:
                              'Abort initial requests if no response within this time. Default: {{seconds}}s.',
                            seconds: TIMEOUT_PRESETS.balanced.request
                          })}
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {t('settings:tldw.streamingIdle')}
                        </label>
                        <Input
                          type="number"
                          min={1}
                          value={streamIdleTimeoutSec}
                          onChange={(e) => {
                            const newValue = parseSeconds(
                              e.target.value,
                              TIMEOUT_PRESETS.balanced.stream
                            )
                            setStreamIdleTimeoutSec(newValue)
                            setTimeoutPreset(
                              determinePreset({
                                request: requestTimeoutSec,
                                stream: newValue,
                                chatRequest: chatRequestTimeoutSec,
                                chatStream: chatStreamIdleTimeoutSec,
                                ragRequest: ragRequestTimeoutSec,
                                media: mediaRequestTimeoutSec,
                                upload: uploadRequestTimeoutSec
                              })
                            )
                          }}
                          placeholder="15"
                          suffix="s"
                        />
                        <div className="text-xs text-text-subtle mt-1">
                          {t('settings:tldw.hints.streamingIdle', {
                            defaultValue:
                              'Abort streaming if no updates received within this time. Default: {{seconds}}s.',
                            seconds: TIMEOUT_PRESETS.balanced.stream
                          })}
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {t('settings:tldw.chatRequest')}
                        </label>
                        <Input
                          type="number"
                          min={1}
                          value={chatRequestTimeoutSec}
                          onChange={(e) => {
                            const newValue = parseSeconds(
                              e.target.value,
                              TIMEOUT_PRESETS.balanced.chatRequest
                            )
                            setChatRequestTimeoutSec(newValue)
                            setTimeoutPreset(
                              determinePreset({
                                request: requestTimeoutSec,
                                stream: streamIdleTimeoutSec,
                                chatRequest: newValue,
                                chatStream: chatStreamIdleTimeoutSec,
                                ragRequest: ragRequestTimeoutSec,
                                media: mediaRequestTimeoutSec,
                                upload: uploadRequestTimeoutSec
                              })
                            )
                          }}
                          suffix="s"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {t('settings:tldw.chatStreamIdle')}
                        </label>
                        <Input
                          type="number"
                          min={1}
                          value={chatStreamIdleTimeoutSec}
                          onChange={(e) => {
                            const newValue = parseSeconds(
                              e.target.value,
                              TIMEOUT_PRESETS.balanced.chatStream
                            )
                            setChatStreamIdleTimeoutSec(newValue)
                            setTimeoutPreset(
                              determinePreset({
                                request: requestTimeoutSec,
                                stream: streamIdleTimeoutSec,
                                chatRequest: chatRequestTimeoutSec,
                                chatStream: newValue,
                                ragRequest: ragRequestTimeoutSec,
                                media: mediaRequestTimeoutSec,
                                upload: uploadRequestTimeoutSec
                              })
                            )
                          }}
                          suffix="s"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {t('settings:tldw.ragRequest')}
                        </label>
                        <Input
                          type="number"
                          min={1}
                          value={ragRequestTimeoutSec}
                          onChange={(e) => {
                            const newValue = parseSeconds(
                              e.target.value,
                              TIMEOUT_PRESETS.balanced.ragRequest
                            )
                            setRagRequestTimeoutSec(newValue)
                            setTimeoutPreset(
                              determinePreset({
                                request: requestTimeoutSec,
                                stream: streamIdleTimeoutSec,
                                chatRequest: chatRequestTimeoutSec,
                                chatStream: chatStreamIdleTimeoutSec,
                                ragRequest: newValue,
                                media: mediaRequestTimeoutSec,
                                upload: uploadRequestTimeoutSec
                              })
                            )
                          }}
                          suffix="s"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {t('settings:tldw.mediaRequest')}
                        </label>
                        <Input
                          type="number"
                          min={1}
                          value={mediaRequestTimeoutSec}
                          onChange={(e) => {
                            const newValue = parseSeconds(
                              e.target.value,
                              TIMEOUT_PRESETS.balanced.media
                            )
                            setMediaRequestTimeoutSec(newValue)
                            setTimeoutPreset(
                              determinePreset({
                                request: requestTimeoutSec,
                                stream: streamIdleTimeoutSec,
                                chatRequest: chatRequestTimeoutSec,
                                chatStream: chatStreamIdleTimeoutSec,
                                ragRequest: ragRequestTimeoutSec,
                                media: newValue,
                                upload: uploadRequestTimeoutSec
                              })
                            )
                          }}
                          suffix="s"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1">
                          {t('settings:tldw.uploadRequest')}
                        </label>
                        <Input
                          type="number"
                          min={1}
                          value={uploadRequestTimeoutSec}
                          onChange={(e) => {
                            const newValue = parseSeconds(
                              e.target.value,
                              TIMEOUT_PRESETS.balanced.upload
                            )
                            setUploadRequestTimeoutSec(newValue)
                            setTimeoutPreset(
                              determinePreset({
                                request: requestTimeoutSec,
                                stream: streamIdleTimeoutSec,
                                chatRequest: chatRequestTimeoutSec,
                                chatStream: chatStreamIdleTimeoutSec,
                                ragRequest: ragRequestTimeoutSec,
                                media: mediaRequestTimeoutSec,
                                upload: newValue
                              })
                            )
                          }}
                          suffix="s"
                        />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <Button
                        onClick={() => {
                          applyTimeoutPreset('balanced')
                          message.success(t('settings:tldw.resetDone'))
                        }}
                      >
                        {t('settings:tldw.reset')}
                      </Button>
                    </div>
                  </div>
                )
              }
            ]}
          />
        </Form>

        {authMode === 'multi-user' && isLoggedIn && (
          <div className="mt-6 rounded-lg border border-border bg-surface2 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-text">
                  {t('settings:tldw.billing.title', 'Billing & usage')}
                </h3>
                <p className="text-xs text-text-muted">
                  {t(
                    'settings:tldw.billing.subtitle',
                    'Manage your plan, billing cycle, and usage limits.'
                  )}
                </p>
              </div>
              <Space>
                <Button onClick={() => void loadBilling()} loading={billingLoading}>
                  {t('settings:tldw.billing.refresh', 'Refresh')}
                </Button>
                <Button onClick={handleBillingPortal} loading={billingLoading}>
                  {t('settings:tldw.billing.portal', 'Billing portal')}
                </Button>
              </Space>
            </div>

            {billingError && (
              <Alert
                type="error"
                showIcon
                className="mt-4"
                message={t('settings:tldw.billing.errorTitle', 'Billing unavailable')}
                description={billingError}
              />
            )}

            {!billingError && (
              <div className="mt-4 space-y-4">
                {billingStatus && (
                  <div className="rounded border border-border bg-surface p-3">
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium">
                        {t('settings:tldw.billing.currentPlan', 'Current plan')}
                      </span>
                      <Tag color={billingStatusColor(billingStatus.status)}>
                        {billingStatusLabel(billingStatus.status)}
                      </Tag>
                      <span className="text-text">
                        {billingStatus.plan_display_name || billingStatus.plan_name}
                      </span>
                      {billingStatus.billing_cycle && (
                        <Tag>
                          {billingStatus.billing_cycle === 'yearly'
                            ? t('settings:tldw.billing.cycle.yearly', 'Yearly')
                            : t('settings:tldw.billing.cycle.monthly', 'Monthly')}
                        </Tag>
                      )}
                    </div>
                    <div className="mt-2 text-xs text-text-muted flex flex-wrap gap-4">
                      <span>
                        {t('settings:tldw.billing.renewal', 'Renews')}:{" "}
                        {formatDate(billingStatus.current_period_end)}
                      </span>
                      {billingStatus.trial_end && (
                        <span>
                          {t('settings:tldw.billing.trialEnds', 'Trial ends')}:{" "}
                          {formatDate(billingStatus.trial_end)}
                        </span>
                      )}
                    </div>
                    {billingStatus.cancel_at_period_end && (
                      <Alert
                        type="warning"
                        showIcon
                        className="mt-3"
                        message={t(
                          'settings:tldw.billing.cancelAtPeriodEnd',
                          'Subscription will cancel at period end.'
                        )}
                      />
                    )}
                  </div>
                )}

                {billingUsage?.has_exceeded && (
                  <Alert
                    type="error"
                    showIcon
                    message={t(
                      'settings:tldw.billing.limitExceeded',
                      'Usage has exceeded one or more plan limits.'
                    )}
                  />
                )}
                {!billingUsage?.has_exceeded && billingUsage?.has_warnings && (
                  <Alert
                    type="warning"
                    showIcon
                    message={t(
                      'settings:tldw.billing.limitWarning',
                      'Approaching plan limits for some resources.'
                    )}
                  />
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="rounded border border-border bg-surface p-3">
                    <div className="text-sm font-medium mb-2">
                      {t('settings:tldw.billing.selectPlan', 'Select a plan')}
                    </div>
                    <Select
                      className="w-full"
                      placeholder={t('settings:tldw.billing.choosePlan', 'Choose a plan')}
                      options={planOptions}
                      value={selectedPlan || undefined}
                      onChange={(value) => setSelectedPlan(value)}
                      disabled={billingPlans.length === 0}
                    />
                    <div className="mt-3">
                      <span className="text-xs text-text-muted">
                        {t('settings:tldw.billing.billingCycle', 'Billing cycle')}
                      </span>
                      <div className="mt-2">
                        <Segmented
                          options={[
                            { label: t('settings:tldw.billing.cycle.monthly', 'Monthly'), value: 'monthly' },
                            { label: t('settings:tldw.billing.cycle.yearly', 'Yearly'), value: 'yearly' }
                          ]}
                          value={billingCycle}
                          onChange={(value) => {
                            if (value === 'monthly' || value === 'yearly') {
                              setBillingCycle(value)
                            }
                          }}
                        />
                      </div>
                    </div>
                    {selectedPlanDetails && (
                      <div className="mt-3 text-xs text-text-muted space-y-1">
                        <div className="font-medium text-text">
                          {selectedPlanDetails.display_name}
                        </div>
                        {selectedPlanDetails.description && (
                          <div>{selectedPlanDetails.description}</div>
                        )}
                        <div>
                          {t('settings:tldw.billing.price', 'Price')}:{" "}
                          {formatPlanPrice(selectedPlanDetails, billingCycle)}
                        </div>
                      </div>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        type="primary"
                        onClick={handleCheckout}
                        loading={billingLoading}
                        disabled={!selectedPlan || (isSamePlan && isSameCycle)}
                      >
                        {isSamePlan && isSameCycle
                          ? t('settings:tldw.billing.currentPlanCta', 'Current plan')
                          : t('settings:tldw.billing.checkout', 'Continue to checkout')}
                      </Button>
                      {billingPlans.length === 0 && !billingLoading && (
                        <span className="text-xs text-text-subtle">
                          {t('settings:tldw.billing.noPlans', 'No plans available yet.')}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="rounded border border-border bg-surface p-3">
                    <div className="text-sm font-medium mb-2">
                      {t('settings:tldw.billing.usageTitle', 'Usage')}
                    </div>
                    {sortedUsageEntries.length === 0 && (
                      <span className="text-xs text-text-muted">
                        {t('settings:tldw.billing.usageEmpty', 'Usage data will appear after activity.')}
                      </span>
                    )}
                    {sortedUsageEntries.length > 0 && (
                      <div className="space-y-2">
                        {sortedUsageEntries.map(([key, value]) => {
                          const check = usageChecks[key] || {}
                          const limit = typeof check.limit !== 'undefined'
                            ? check.limit
                            : billingUsage?.limits?.[key]
                          const statusColor = check.exceeded
                            ? 'red'
                            : check.warning
                              ? 'orange'
                              : 'green'
                          return (
                            <div key={key} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                              <span className="text-text">{formatUsageLabel(key)}</span>
                              <div className="flex items-center gap-2">
                                <span className="text-text-muted">
                                  {formatNumber(value)} / {formatLimitValue(limit, check.unlimited)}
                                </span>
                                {typeof check.percent_used === 'number' && !check.unlimited && (
                                  <Tag color={statusColor}>
                                    {Math.round(check.percent_used)}%
                                  </Tag>
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Spin>
  )
}
