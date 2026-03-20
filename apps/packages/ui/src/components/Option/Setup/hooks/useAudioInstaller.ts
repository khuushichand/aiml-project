import React from "react"

import { bgRequest } from "@/services/background-proxy"
import { toAllowedPath } from "@/services/tldw/path-utils"
import {
  deriveAdminGuardFromError,
  sanitizeAdminErrorMessage,
  type AdminGuardState
} from "@/components/Option/Admin/admin-error-utils"

const RECOMMENDATIONS_PATH = toAllowedPath("/api/v1/setup/admin/audio/recommendations")
const INSTALL_STATUS_PATH = toAllowedPath("/api/v1/setup/admin/install-status")
const PROVISION_PATH = toAllowedPath("/api/v1/setup/admin/audio/provision")
const VERIFY_PATH = toAllowedPath("/api/v1/setup/admin/audio/verify")

const POLL_INTERVAL_MS = 3000
const PROVISION_TIMEOUT_MS = 30 * 60 * 1000
const ACTIVE_INSTALL_STATUSES = new Set(["queued", "running", "in_progress"])

type MachineProfile = {
  platform?: string
  arch?: string
  apple_silicon?: boolean
  cuda_available?: boolean
  free_disk_gb?: number
  network_available_for_downloads?: boolean
}

type AudioResourceProfile = {
  profile_id: string
  label: string
  description?: string | null
  estimated_disk_gb?: number | null
  resource_class?: string | null
  stt_plan?: Array<Record<string, unknown>>
  tts_plan?: Array<Record<string, unknown>>
}

type AudioBundle = {
  bundle_id: string
  label: string
  description: string
  default_resource_profile?: string
  resource_profiles?: Record<string, AudioResourceProfile>
}

type AudioRecommendation = {
  bundle_id: string
  resource_profile?: string
  selection_key?: string
  label?: string
  reasons?: string[]
  bundle?: AudioBundle
  profile?: AudioResourceProfile
}

type InstallStep = {
  name?: string
  label?: string
  status?: string
}

type InstallStatusSnapshot = {
  status?: string
  steps?: InstallStep[]
  errors?: unknown[]
  bundle_id?: string
  resource_profile?: string
  safe_rerun?: boolean
}

type VerificationResult = {
  status?: string
  bundle_id?: string
  selected_resource_profile?: string
  targets_checked?: string[]
  remediation_items?: Array<{ code?: string; action?: string; message?: string } | string>
}

type RecommendationsResponse = {
  machine_profile?: MachineProfile
  recommendations?: AudioRecommendation[]
  excluded?: AudioRecommendation[]
  catalog?: AudioBundle[]
}

const toError = async (
  response: Awaited<ReturnType<typeof bgRequest>>
): Promise<Error> => {
  const detail =
    typeof response?.error === "string"
      ? response.error
      : typeof response?.data?.detail === "string"
        ? response.data.detail
        : typeof response?.data?.error === "string"
          ? response.data.error
          : ""
  const status = response?.status ?? 500
  const suffix = detail ? ` ${detail}` : ""
  return new Error(`Request failed: ${status}${suffix}`)
}

const requestJson = async <T,>(
  path: ReturnType<typeof toAllowedPath>,
  init?: {
    method?: string
    headers?: Record<string, string>
    body?: string
    timeoutMs?: number
    signal?: AbortSignal
    responseType?: "json" | "text" | "arrayBuffer"
  }
): Promise<T> => {
  const response = await bgRequest<any>({
    path,
    method: init?.method || "GET",
    headers: init?.headers,
    body: init?.body,
    timeoutMs: init?.timeoutMs,
    abortSignal: init?.signal,
    responseType: init?.responseType,
    returnResponse: true
  })
  if (!response.ok) {
    throw await toError(response)
  }
  return response.data as T
}

const deriveSelection = (
  recommendations: AudioRecommendation[],
  catalog: AudioBundle[],
  currentBundleId: string | null,
  currentResourceProfile: string | null
) => {
  const recommendedBundle = recommendations[0]?.bundle
  const fallbackBundle = catalog[0]
  const nextBundleId = currentBundleId || recommendedBundle?.bundle_id || fallbackBundle?.bundle_id || null
  const currentBundle =
    recommendations.find((entry) => entry.bundle_id === nextBundleId)?.bundle ||
    catalog.find((entry) => entry.bundle_id === nextBundleId) ||
    recommendedBundle ||
    fallbackBundle ||
    null

  const recommendedProfile = recommendations.find((entry) => entry.bundle_id === nextBundleId)?.resource_profile
  const defaultProfile =
    currentResourceProfile ||
    recommendedProfile ||
    currentBundle?.default_resource_profile ||
    Object.keys(currentBundle?.resource_profiles || {})[0] ||
    null

  return {
    bundleId: nextBundleId,
    resourceProfile: defaultProfile
  }
}

const logNonFatalRefreshError = (context: string, err: unknown) => {
  console.warn(`Audio installer status refresh failed during ${context}.`, err)
}

export const useAudioInstaller = () => {
  const selectionRef = React.useRef<{
    bundleId: string | null
    resourceProfile: string | null
  }>({ bundleId: null, resourceProfile: null })
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [adminGuard, setAdminGuard] = React.useState<AdminGuardState>(null)
  const [machineProfile, setMachineProfile] = React.useState<MachineProfile | null>(null)
  const [recommendations, setRecommendations] = React.useState<AudioRecommendation[]>([])
  const [catalog, setCatalog] = React.useState<AudioBundle[]>([])
  const [selectedBundleId, setSelectedBundleId] = React.useState<string | null>(null)
  const [selectedResourceProfile, setSelectedResourceProfile] = React.useState<string | null>(null)
  const [installStatus, setInstallStatus] = React.useState<InstallStatusSnapshot | null>(null)
  const [verification, setVerification] = React.useState<VerificationResult | null>(null)
  const [provisioning, setProvisioning] = React.useState(false)
  const [verifying, setVerifying] = React.useState(false)

  React.useEffect(() => {
    selectionRef.current = {
      bundleId: selectedBundleId,
      resourceProfile: selectedResourceProfile
    }
  }, [selectedBundleId, selectedResourceProfile])

  const refreshInstallStatus = React.useCallback(async () => {
    const snapshot = await requestJson<InstallStatusSnapshot>(INSTALL_STATUS_PATH)
    setInstallStatus(snapshot)
    return snapshot
  }, [])

  const load = React.useCallback(async () => {
    try {
      setLoading(true)
      const response = await requestJson<RecommendationsResponse>(RECOMMENDATIONS_PATH)
      const nextRecommendations = Array.isArray(response.recommendations) ? response.recommendations : []
      const nextCatalog = Array.isArray(response.catalog) ? response.catalog : []
      const nextSelection = deriveSelection(
        nextRecommendations,
        nextCatalog,
        selectionRef.current.bundleId,
        selectionRef.current.resourceProfile
      )

      setMachineProfile(response.machine_profile || null)
      setRecommendations(nextRecommendations)
      setCatalog(nextCatalog)
      setSelectedBundleId(nextSelection.bundleId)
      setSelectedResourceProfile(nextSelection.resourceProfile)
      setAdminGuard(null)
      setError(null)

      await refreshInstallStatus()
    } catch (err) {
      const guardState = deriveAdminGuardFromError(err)
      setAdminGuard(guardState)
      setError(
        sanitizeAdminErrorMessage(
          err,
          "Unable to load the admin audio installer for this server."
        )
      )
    } finally {
      setLoading(false)
    }
  }, [refreshInstallStatus])

  React.useEffect(() => {
    void load()
  }, [load])

  React.useEffect(() => {
    if (!installStatus?.status || !ACTIVE_INSTALL_STATUSES.has(installStatus.status)) {
      return
    }

    const timeout = window.setTimeout(() => {
      void refreshInstallStatus().catch((error) => {
        logNonFatalRefreshError("polling", error)
      })
    }, POLL_INTERVAL_MS)

    return () => {
      window.clearTimeout(timeout)
    }
  }, [installStatus, refreshInstallStatus])

  const selectedBundle = React.useMemo(
    () =>
      recommendations.find((entry) => entry.bundle_id === selectedBundleId)?.bundle ||
      catalog.find((entry) => entry.bundle_id === selectedBundleId) ||
      null,
    [catalog, recommendations, selectedBundleId]
  )

  const selectedProfile = React.useMemo(() => {
    const recommendedProfile = recommendations.find(
      (entry) =>
        entry.bundle_id === selectedBundleId &&
        entry.resource_profile === selectedResourceProfile
    )?.profile
    return (
      recommendedProfile ||
      (selectedBundle?.resource_profiles || {})[selectedResourceProfile || ""] ||
      null
    )
  }, [recommendations, selectedBundle, selectedBundleId, selectedResourceProfile])

  const bundleOptions = React.useMemo(
    () => {
      if (recommendations.length > 0) {
        const seenBundleIds = new Set<string>()
        return recommendations.flatMap((entry) => {
          if (seenBundleIds.has(entry.bundle_id)) {
            return []
          }
          seenBundleIds.add(entry.bundle_id)
          return [
            {
              value: entry.bundle_id,
              label: entry.bundle?.label || entry.label || entry.bundle_id
            }
          ]
        })
      }
      return catalog.map((entry) => ({ value: entry.bundle_id, label: entry.label }))
    },
    [catalog, recommendations]
  )

  const profileOptions = React.useMemo(
    () =>
      Object.values(selectedBundle?.resource_profiles || {}).map((profile) => ({
        value: profile.profile_id,
        label: profile.label
      })),
    [selectedBundle]
  )

  const handleBundleChange = React.useCallback(
    (bundleId: string) => {
      const bundle =
        recommendations.find((entry) => entry.bundle_id === bundleId)?.bundle ||
        catalog.find((entry) => entry.bundle_id === bundleId) ||
        null
      const recommendedProfile = recommendations.find(
        (entry) => entry.bundle_id === bundleId
      )?.resource_profile
      setSelectedBundleId(bundleId)
      setSelectedResourceProfile(
        recommendedProfile ||
          bundle?.default_resource_profile ||
          Object.keys(bundle?.resource_profiles || {})[0] ||
          null
      )
      setVerification(null)
    },
    [catalog, recommendations]
  )

  const handleResourceProfileChange = React.useCallback((profileId: string) => {
    setSelectedResourceProfile(profileId)
    setVerification(null)
  }, [])

  const handleProvision = React.useCallback(
    async (safeRerun = false) => {
      if (!selectedBundleId || !selectedResourceProfile) return
      setProvisioning(true)
      try {
        const result = await requestJson<InstallStatusSnapshot>(PROVISION_PATH, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          timeoutMs: PROVISION_TIMEOUT_MS,
          body: JSON.stringify({
            bundle_id: selectedBundleId,
            resource_profile: selectedResourceProfile,
            safe_rerun: safeRerun
          })
        })
        setInstallStatus(result)
        setVerification(null)
        setAdminGuard(null)
        setError(null)
        if (result?.status && ACTIVE_INSTALL_STATUSES.has(result.status)) {
          void refreshInstallStatus().catch((error) => {
            logNonFatalRefreshError("post-provision refresh", error)
          })
        }
      } catch (err) {
        setAdminGuard(deriveAdminGuardFromError(err))
        setError(
          sanitizeAdminErrorMessage(err, "Unable to provision the selected audio bundle.")
        )
      } finally {
        setProvisioning(false)
      }
    },
    [refreshInstallStatus, selectedBundleId, selectedResourceProfile]
  )

  const handleVerify = React.useCallback(async () => {
    if (!selectedBundleId || !selectedResourceProfile) return
    setVerifying(true)
    try {
      const result = await requestJson<VerificationResult>(VERIFY_PATH, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bundle_id: selectedBundleId,
          resource_profile: selectedResourceProfile
        })
      })
      setVerification(result)
      setAdminGuard(null)
      setError(null)
    } catch (err) {
      setAdminGuard(deriveAdminGuardFromError(err))
      setError(
        sanitizeAdminErrorMessage(err, "Unable to verify the selected audio bundle.")
      )
    } finally {
      setVerifying(false)
    }
  }, [selectedBundleId, selectedResourceProfile])

  return {
    adminGuard,
    bundleOptions,
    catalog,
    error,
    installStatus,
    loading,
    machineProfile,
    profileOptions,
    provisioning,
    recommendations,
    selectedBundle,
    selectedBundleId,
    selectedProfile,
    selectedResourceProfile,
    setSelectedResourceProfile,
    handleBundleChange,
    handleResourceProfileChange,
    handleProvision,
    handleVerify,
    refresh: load,
    verification,
    verifying
  }
}

export type UseAudioInstallerResult = ReturnType<typeof useAudioInstaller>
