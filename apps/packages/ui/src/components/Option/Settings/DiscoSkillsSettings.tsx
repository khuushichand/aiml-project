import React, { useCallback, useMemo } from "react"
import { Collapse, InputNumber, Select, Slider, Switch } from "antd"
import { useTranslation } from "react-i18next"
import { SettingRow } from "@/components/Common/SettingRow"
import { useDiscoSkills } from "@/hooks/useDiscoSkills"
import {
  DISCO_SKILLS_BY_CATEGORY,
  DISCO_CATEGORY_INFO,
  DISCO_SKILLS_PRESETS,
  createDefaultStats
} from "@/constants/disco-skills"
import type { DiscoSkill, DiscoSkillCategory } from "@/types/disco-skills"

const SELECT_CLASSNAME = "w-[200px]"

interface SkillSliderProps {
  skill: DiscoSkill
  value: number
  onChange: (skillId: string, value: number) => void
  disabled?: boolean
}

const SkillSlider: React.FC<SkillSliderProps> = ({
  skill,
  value,
  onChange,
  disabled
}) => {
  const handleSliderChange = useCallback(
    (newValue: number) => {
      onChange(skill.id, newValue)
    },
    [skill.id, onChange]
  )

  const handleInputChange = useCallback(
    (newValue: number | null) => {
      if (newValue !== null) {
        onChange(skill.id, newValue)
      }
    },
    [skill.id, onChange]
  )

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex-shrink-0 w-40">
        <span
          className="text-sm font-medium"
          style={{ color: skill.color }}
          title={skill.personality}
        >
          {skill.name}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <Slider
          min={1}
          max={10}
          value={value}
          onChange={handleSliderChange}
          disabled={disabled}
          trackStyle={{ backgroundColor: skill.color }}
          tooltip={{ formatter: (val) => `${val}` }}
        />
      </div>
      <InputNumber
        min={1}
        max={10}
        value={value}
        onChange={handleInputChange}
        disabled={disabled}
        className="!w-14"
        size="small"
      />
    </div>
  )
}

interface CategoryPanelProps {
  category: DiscoSkillCategory
  skills: DiscoSkill[]
  stats: Record<string, number>
  onStatChange: (skillId: string, value: number) => void
  disabled?: boolean
}

const CategoryPanel: React.FC<CategoryPanelProps> = ({
  category,
  skills,
  stats,
  onStatChange,
  disabled
}) => {
  const info = DISCO_CATEGORY_INFO[category]

  return (
    <div className="space-y-1">
      <p className="text-xs text-text-muted mb-2">{info.description}</p>
      {skills.map((skill) => (
        <SkillSlider
          key={skill.id}
          skill={skill}
          value={stats[skill.id] ?? 5}
          onChange={onStatChange}
          disabled={disabled}
        />
      ))}
    </div>
  )
}

export const DiscoSkillsSettings: React.FC = () => {
  const { t } = useTranslation("settings")

  const {
    enabled,
    setEnabled,
    stats,
    triggerProbabilityBase,
    setTriggerProbabilityBase,
    persistComments,
    setPersistComments,
    updateSkillStat,
    applyPreset,
    resetStats
  } = useDiscoSkills()

  const presetOptions = useMemo(
    () =>
      DISCO_SKILLS_PRESETS.map((preset) => ({
        label: preset.name,
        value: preset.id,
        description: preset.description
      })),
    []
  )

  const handlePresetChange = useCallback(
    (presetId: string) => {
      const preset = DISCO_SKILLS_PRESETS.find((p) => p.id === presetId)
      if (preset) {
        applyPreset(preset.stats)
      }
    },
    [applyPreset]
  )

  const handleProbabilityChange = useCallback(
    (value: number) => {
      setTriggerProbabilityBase(value / 100)
    },
    [setTriggerProbabilityBase]
  )

  const collapseItems = useMemo(() => {
    const categories: DiscoSkillCategory[] = [
      "intellect",
      "psyche",
      "physique",
      "motorics"
    ]

    return categories.map((category) => {
      const info = DISCO_CATEGORY_INFO[category]
      const skills = DISCO_SKILLS_BY_CATEGORY[category]

      return {
        key: category,
        label: (
          <div className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: info.color }}
            />
            <span className="font-medium">{info.name}</span>
            <span className="text-xs text-text-muted">({skills.length})</span>
          </div>
        ),
        children: (
          <CategoryPanel
            category={category}
            skills={skills}
            stats={stats}
            onStatChange={updateSkillStat}
            disabled={!enabled}
          />
        )
      }
    })
  }, [stats, updateSkillStat, enabled])

  const isBalanced = useMemo(() => {
    const defaultStats = createDefaultStats()
    return Object.keys(defaultStats).every(
      (key) => stats[key] === defaultStats[key]
    )
  }, [stats])

  return (
    <div className="flex flex-col space-y-6 text-sm">
      <div>
        <h2 className="text-base font-semibold leading-7 text-text">
          {t("discoSkills.title", "Disco Skills")}
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          {t(
            "discoSkills.description",
            "Generate personality-driven skill commentary on AI responses, inspired by Disco Elysium's inner voice system."
          )}
        </p>
        <div className="border-b border-border mt-3" />
      </div>

      <SettingRow
        label={t("discoSkills.enable.label", "Enable Disco Skills")}
        description={t(
          "discoSkills.enable.description",
          "When enabled, skill checks may trigger after AI responses"
        )}
        control={
          <Switch
            checked={enabled}
            onChange={setEnabled}
            aria-label={t("discoSkills.enable.label", "Enable Disco Skills")}
          />
        }
      />

      {enabled && (
        <>
          <div>
            <h3 className="text-sm font-semibold leading-6 text-text mb-4">
              {t("discoSkills.general.heading", "General Settings")}
            </h3>

            <div className="space-y-4">
              <div className="flex sm:flex-row flex-col space-y-4 sm:space-y-0 sm:justify-between sm:items-center">
                <div className="flex flex-col gap-0.5">
                  <label className="text-text" htmlFor="disco-trigger-probability">
                    {t("discoSkills.triggerProbability.label", "Trigger Probability")}
                  </label>
                  <span className="text-xs text-text-subtle">
                    {t(
                      "discoSkills.triggerProbability.description",
                      "How often skills attempt to comment (modified by stat level)"
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-4 sm:mt-0">
                  <Slider
                    id="disco-trigger-probability"
                    min={10}
                    max={100}
                    step={5}
                    value={Math.round(triggerProbabilityBase * 100)}
                    onChange={handleProbabilityChange}
                    className="!w-32"
                    tooltip={{ formatter: (val) => `${val}%` }}
                  />
                  <span className="text-sm text-text-muted w-10">
                    {Math.round(triggerProbabilityBase * 100)}%
                  </span>
                </div>
              </div>

              <SettingRow
                label={t("discoSkills.persistComments.label", "Persist Comments")}
                description={t(
                  "discoSkills.persistComments.description",
                  "Save skill comments with messages (otherwise ephemeral)"
                )}
                control={
                  <Switch
                    checked={persistComments}
                    onChange={setPersistComments}
                    aria-label={t(
                      "discoSkills.persistComments.label",
                      "Persist Comments"
                    )}
                  />
                }
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold leading-6 text-text">
                {t("discoSkills.skillStats.heading", "Skill Stats")}
              </h3>
              <div className="flex items-center gap-2">
                <Select
                  className={SELECT_CLASSNAME}
                  placeholder={t("discoSkills.presets.placeholder", "Apply preset...")}
                  options={presetOptions}
                  onChange={handlePresetChange}
                  value={null}
                  allowClear
                />
                {!isBalanced && (
                  <button
                    type="button"
                    onClick={resetStats}
                    className="text-xs text-primary hover:text-primaryStrong"
                  >
                    {t("discoSkills.resetStats", "Reset to default")}
                  </button>
                )}
              </div>
            </div>

            <p className="text-xs text-text-muted mb-4">
              {t(
                "discoSkills.skillStats.description",
                "Higher stats increase both trigger frequency and success rate. Hover over skill names for personality descriptions."
              )}
            </p>

            <Collapse
              items={collapseItems}
              bordered={false}
              className="bg-transparent"
              expandIconPlacement="start"
            />
          </div>
        </>
      )}
    </div>
  )
}

export default DiscoSkillsSettings
