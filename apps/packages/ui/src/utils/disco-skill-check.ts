/**
 * Disco Elysium Skill Check Logic
 *
 * Implements trigger probability calculations and skill selection
 * for generating in-character skill comments.
 */

import type {
  DiscoSkill,
  DiscoSkillCheckResult,
  DiscoSkillComment
} from "@/types/disco-skills"
import { DISCO_SKILLS } from "@/constants/disco-skills"

/**
 * Determines if a skill should trigger and whether it "passes" its check.
 *
 * @param statLevel - The skill's current stat level (1-10)
 * @param baseProbability - Base probability for triggering (0.1-1.0)
 * @returns Object with shouldTrigger and passed booleans
 */
export function shouldSkillTrigger(
  statLevel: number,
  baseProbability: number
): DiscoSkillCheckResult {
  const clampedStat = Math.max(1, Math.min(10, statLevel))
  // Normalize stat level to 0-1 range
  const normalizedStat = clampedStat / 10

  // Calculate trigger probability: base * (stat / 10)
  // Higher stat = more likely to trigger
  const triggerProbability = baseProbability * normalizedStat

  // Roll for trigger
  const triggerRoll = Math.random()
  const shouldTrigger = triggerRoll < triggerProbability

  if (!shouldTrigger) {
    return { shouldTrigger: false, passed: false }
  }

  // If triggered, roll for pass/fail
  // Higher stat = more likely to pass
  // Pass threshold: 0.5 - (stat - 5) * 0.08
  // At stat 5: 50% pass rate
  // At stat 10: 90% pass rate
  // At stat 1: 18% pass rate
  const passThreshold = 0.5 - (clampedStat - 5) * 0.08
  const passRoll = Math.random()
  const passed = passRoll > passThreshold

  return { shouldTrigger, passed }
}

/**
 * Calculates keyword match score for a message against a skill's trigger keywords.
 *
 * @param message - The message to check
 * @param keywords - Array of trigger keywords
 * @returns Match score (0 = no matches, higher = more matches)
 */
function calculateKeywordScore(message: string, keywords?: string[]): number {
  if (!keywords || keywords.length === 0) return 0

  const lowerMessage = message.toLowerCase()
  let score = 0

  for (const keyword of keywords) {
    // Check for word boundary matches to avoid partial matches
    const regex = new RegExp(`\\b${keyword.toLowerCase()}\\b`, "g")
    const matches = lowerMessage.match(regex)
    if (matches) {
      score += matches.length
    }
  }

  return score
}

/**
 * Selects a skill to generate a comment for, using weighted random selection.
 *
 * @param message - The AI response message to comment on
 * @param stats - Current stat levels for all skills
 * @param skills - Array of skills to choose from (defaults to all skills)
 * @returns Selected skill or null if none selected
 */
export function selectSkillForComment(
  message: string,
  stats: Record<string, number>,
  skills: DiscoSkill[] = DISCO_SKILLS
): DiscoSkill | null {
  if (!message || message.trim().length === 0) return null
  if (skills.length === 0) return null

  // Calculate weights for each skill
  const weightedSkills = skills.map((skill) => {
    const statLevel = stats[skill.id] ?? 5

    // Base weight is the stat level
    let weight = statLevel

    // Boost weight for keyword matches
    const keywordScore = calculateKeywordScore(message, skill.triggerKeywords)
    if (keywordScore > 0) {
      // Each keyword match adds 2 to the weight, capped at stat level
      weight += Math.min(keywordScore * 2, statLevel)
    }

    return { skill, weight }
  })

  // Calculate total weight
  const totalWeight = weightedSkills.reduce((sum, ws) => sum + ws.weight, 0)

  if (totalWeight === 0) {
    // Fallback to random selection if all weights are 0
    return skills[Math.floor(Math.random() * skills.length)]
  }

  // Weighted random selection
  let random = Math.random() * totalWeight
  for (const { skill, weight } of weightedSkills) {
    random -= weight
    if (random <= 0) {
      return skill
    }
  }

  // Fallback (should not reach here)
  return weightedSkills[weightedSkills.length - 1].skill
}

/**
 * Generates the prompt for the LLM to create a skill comment.
 *
 * @param skill - The skill generating the comment
 * @param assistantMessage - The AI response to comment on
 * @param passed - Whether the skill "passed" its check
 * @returns Prompt string for the LLM
 */
export function buildSkillPrompt(
  skill: DiscoSkill,
  assistantMessage: string,
  passed: boolean
): string {
  const passedText = passed
    ? "This is a SUCCESSFUL skill check - the observation should be insightful, helpful, or provide useful perspective."
    : "This is a FAILED skill check - the observation should be slightly off, paranoid, unhelpful, or miss the point in a way characteristic of this skill."

  return `You are "${skill.name}" from Disco Elysium, one of the player's inner voices.
Skill personality: ${skill.personality}

An AI assistant just said this to the user:
---
${assistantMessage.slice(0, 1500)}${assistantMessage.length > 1500 ? "..." : ""}
---

${passedText}

Generate a brief in-character observation (1-3 sentences max) as this skill reacting to the AI's response.
- Stay in character as this skill's personality
- React to the content, tone, or implications of the AI's message
- Keep it concise and punchy like the game's skill checks
- Do NOT use quotation marks around your response
- Do NOT prefix with the skill name

Respond with ONLY the skill comment, nothing else.`
}

/**
 * Creates a DiscoSkillComment object from the generated comment.
 *
 * @param skill - The skill that generated the comment
 * @param comment - The generated comment text
 * @param passed - Whether the skill passed its check
 * @param messageId - Optional ID of the message this is attached to
 * @returns DiscoSkillComment object
 */
export function createSkillComment(
  skill: DiscoSkill,
  comment: string,
  passed: boolean,
  messageId?: string
): DiscoSkillComment {
  return {
    skillId: skill.id,
    skillName: skill.name,
    comment: comment.trim(),
    category: skill.category,
    color: skill.color,
    passed,
    timestamp: Date.now(),
    messageId
  }
}

/**
 * Full workflow: select skill, check trigger, return skill if should trigger.
 *
 * @param message - The AI response message
 * @param stats - Current stat levels
 * @param baseProbability - Base trigger probability
 * @returns Object with skill and passed status, or null if no trigger
 */
export function attemptSkillTrigger(
  message: string,
  stats: Record<string, number>,
  baseProbability: number
): { skill: DiscoSkill; passed: boolean } | null {
  // First select which skill would comment
  const skill = selectSkillForComment(message, stats)
  if (!skill) return null

  // Then check if it triggers
  const statLevel = stats[skill.id] ?? 5
  const result = shouldSkillTrigger(statLevel, baseProbability)

  if (!result.shouldTrigger) return null

  return { skill, passed: result.passed }
}
