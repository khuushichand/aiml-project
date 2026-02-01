/**
 * Disco Elysium Skills System Types
 *
 * A client-side "inner voice" system that generates personality-driven
 * skill commentary on AI chat responses, inspired by Disco Elysium's skill system.
 */

/** The four skill categories from Disco Elysium */
export type DiscoSkillCategory = "intellect" | "psyche" | "physique" | "motorics"

/** A single Disco Elysium skill definition */
export interface DiscoSkill {
  /** Unique skill identifier (e.g., "logic", "empathy") */
  id: string
  /** Display name (e.g., "Logic", "Empathy") */
  name: string
  /** Which of the four categories this skill belongs to */
  category: DiscoSkillCategory
  /** CSS color for the skill's UI elements */
  color: string
  /** Personality description that defines how this skill "speaks" */
  personality: string
  /** Optional keywords that boost this skill's selection probability */
  triggerKeywords?: string[]
}

/** Result of a skill check */
export interface DiscoSkillCheckResult {
  /** Whether the skill should trigger at all */
  shouldTrigger: boolean
  /** Whether the skill "passed" its check (affects tone of comment) */
  passed: boolean
}

/** A generated skill comment to display */
export interface DiscoSkillComment {
  /** ID of the skill that generated this comment */
  skillId: string
  /** Display name of the skill */
  skillName: string
  /** The generated comment text */
  comment: string
  /** Category of the skill (for styling) */
  category: DiscoSkillCategory
  /** Color for the skill annotation */
  color: string
  /** Whether the skill "passed" its check */
  passed: boolean
  /** When this comment was generated */
  timestamp: number
  /** Optional: ID of the message this comment is attached to */
  messageId?: string
}

/** User configuration for the Disco Skills feature */
export interface DiscoSkillsConfig {
  /** Master toggle for the feature */
  enabled: boolean
  /** Stat levels for each skill (1-10) */
  stats: Record<string, number>
  /** Base probability for skill triggers (0.1-1.0) */
  triggerProbabilityBase: number
  /** Whether to persist comments with messages */
  persistComments: boolean
}

/** Default configuration values */
export const DEFAULT_DISCO_SKILLS_CONFIG: DiscoSkillsConfig = {
  enabled: false,
  stats: {},
  triggerProbabilityBase: 0.5,
  persistComments: false
}

/** Preset configurations for quick setup */
export interface DiscoSkillsPreset {
  id: string
  name: string
  description: string
  stats: Record<string, number>
}
