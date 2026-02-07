import { useCallback, useMemo } from "react"
import { useStorage } from "@plasmohq/storage/hook"
import {
  DEFAULT_DISCO_SKILLS_CONFIG,
  type DiscoSkillsConfig
} from "@/types/disco-skills"
import { createDefaultStats } from "@/constants/disco-skills"

/** Storage keys for disco skills settings */
const STORAGE_KEYS = {
  enabled: "discoSkillsEnabled",
  stats: "discoSkillsStats",
  triggerProbability: "discoSkillsTriggerProbability",
  persistComments: "discoSkillsPersistComments"
} as const

/**
 * Hook for managing Disco Skills configuration.
 * Provides persistent storage for skill settings using @plasmohq/storage.
 */
export function useDiscoSkills() {
  const [enabled, setEnabled] = useStorage(
    STORAGE_KEYS.enabled,
    DEFAULT_DISCO_SKILLS_CONFIG.enabled
  )

  const [stats, setStats] = useStorage<Record<string, number>>(
    STORAGE_KEYS.stats,
    createDefaultStats()
  )

  const [triggerProbabilityBase, setTriggerProbabilityBase] = useStorage(
    STORAGE_KEYS.triggerProbability,
    DEFAULT_DISCO_SKILLS_CONFIG.triggerProbabilityBase
  )

  const [persistComments, setPersistComments] = useStorage(
    STORAGE_KEYS.persistComments,
    DEFAULT_DISCO_SKILLS_CONFIG.persistComments
  )

  /**
   * Update a single skill's stat level
   */
  const updateSkillStat = useCallback(
    (skillId: string, value: number) => {
      const clampedValue = Math.max(1, Math.min(10, value))
      setStats((prev) => ({
        ...prev,
        [skillId]: clampedValue
      }))
    },
    [setStats]
  )

  /**
   * Apply a preset configuration
   */
  const applyPreset = useCallback(
    (presetStats: Record<string, number>) => {
      setStats(presetStats)
    },
    [setStats]
  )

  /**
   * Reset all stats to default values
   */
  const resetStats = useCallback(() => {
    setStats(createDefaultStats())
  }, [setStats])

  /**
   * Get the full config object
   */
  const config = useMemo<DiscoSkillsConfig>(
    () => ({
      enabled,
      stats: stats ?? createDefaultStats(),
      triggerProbabilityBase,
      persistComments
    }),
    [enabled, stats, triggerProbabilityBase, persistComments]
  )

  /**
   * Update the full config at once
   */
  const updateConfig = useCallback(
    (updates: Partial<DiscoSkillsConfig>) => {
      if (updates.enabled !== undefined) {
        setEnabled(updates.enabled)
      }
      if (updates.stats !== undefined) {
        setStats(updates.stats)
      }
      if (updates.triggerProbabilityBase !== undefined) {
        setTriggerProbabilityBase(updates.triggerProbabilityBase)
      }
      if (updates.persistComments !== undefined) {
        setPersistComments(updates.persistComments)
      }
    },
    [setEnabled, setStats, setTriggerProbabilityBase, setPersistComments]
  )

  /**
   * Get a specific skill's stat value
   */
  const getSkillStat = useCallback(
    (skillId: string): number => {
      return stats?.[skillId] ?? 5
    },
    [stats]
  )

  return {
    // State
    enabled,
    stats: stats ?? createDefaultStats(),
    triggerProbabilityBase,
    persistComments,
    config,

    // Setters
    setEnabled,
    setTriggerProbabilityBase,
    setPersistComments,

    // Actions
    updateSkillStat,
    applyPreset,
    resetStats,
    updateConfig,
    getSkillStat
  }
}
