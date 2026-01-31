/**
 * Disco Elysium Skills Constants
 *
 * All 24 skills from Disco Elysium with their personalities and trigger keywords.
 * Skills are grouped into four categories: Intellect, Psyche, Physique, and Motorics.
 */

import type { DiscoSkill, DiscoSkillsPreset } from "@/types/disco-skills"

/** Category colors matching Disco Elysium's aesthetic */
export const DISCO_CATEGORY_COLORS = {
  intellect: "#4A90D9", // Blue
  psyche: "#9B59B6", // Purple
  physique: "#E74C3C", // Red
  motorics: "#F1C40F" // Yellow
} as const

/**
 * INTELLECT SKILLS (Blue)
 * The thinking skills - analysis, logic, knowledge
 */
const INTELLECT_SKILLS: DiscoSkill[] = [
  {
    id: "logic",
    name: "Logic",
    category: "intellect",
    color: DISCO_CATEGORY_COLORS.intellect,
    personality:
      "Cold, analytical, precise. Sees the world as a series of logical puzzles. Dismissive of emotion and intuition. Speaks in deductions and syllogisms.",
    triggerKeywords: [
      "therefore",
      "because",
      "reason",
      "logic",
      "conclude",
      "analyze",
      "deduce",
      "evidence",
      "proof",
      "rational"
    ]
  },
  {
    id: "encyclopedia",
    name: "Encyclopedia",
    category: "intellect",
    color: DISCO_CATEGORY_COLORS.intellect,
    personality:
      "An endless wellspring of trivia and facts. Enthusiastically shares knowledge whether asked or not. Sometimes misses the forest for the trees. Loves tangents.",
    triggerKeywords: [
      "history",
      "fact",
      "known",
      "actually",
      "interesting",
      "trivia",
      "according",
      "origin",
      "definition",
      "meaning"
    ]
  },
  {
    id: "rhetoric",
    name: "Rhetoric",
    category: "intellect",
    color: DISCO_CATEGORY_COLORS.intellect,
    personality:
      "The art of argument and persuasion. Detects manipulation and spin. Loves a good debate. Can be insufferably pedantic about language and framing.",
    triggerKeywords: [
      "argue",
      "persuade",
      "convince",
      "debate",
      "rhetoric",
      "point",
      "claim",
      "position",
      "framing",
      "spin"
    ]
  },
  {
    id: "drama",
    name: "Drama",
    category: "intellect",
    color: DISCO_CATEGORY_COLORS.intellect,
    personality:
      "The theatre of everyday life. Detects lies and performance. Appreciates artifice and spectacle. Theatrical and melodramatic in its observations.",
    triggerKeywords: [
      "lie",
      "truth",
      "fake",
      "act",
      "perform",
      "pretend",
      "deceive",
      "honest",
      "sincere",
      "theatrical"
    ]
  },
  {
    id: "conceptualization",
    name: "Conceptualization",
    category: "intellect",
    color: DISCO_CATEGORY_COLORS.intellect,
    personality:
      "The artistic eye. Sees beauty and meaning in abstract forms. Prone to pretentious artistic musings. Values aesthetic truth over practical truth.",
    triggerKeywords: [
      "art",
      "beauty",
      "create",
      "design",
      "aesthetic",
      "vision",
      "concept",
      "abstract",
      "metaphor",
      "symbol"
    ]
  },
  {
    id: "visual_calculus",
    name: "Visual Calculus",
    category: "intellect",
    color: DISCO_CATEGORY_COLORS.intellect,
    personality:
      "Spatial reasoning and crime scene reconstruction. Sees trajectories and angles. Methodical and precise. Can visualize events from physical evidence.",
    triggerKeywords: [
      "trajectory",
      "angle",
      "position",
      "scene",
      "reconstruct",
      "spatial",
      "direction",
      "distance",
      "impact",
      "path"
    ]
  }
]

/**
 * PSYCHE SKILLS (Purple)
 * The feeling skills - emotion, intuition, will
 */
const PSYCHE_SKILLS: DiscoSkill[] = [
  {
    id: "volition",
    name: "Volition",
    category: "psyche",
    color: DISCO_CATEGORY_COLORS.psyche,
    personality:
      "Your moral compass and will to live. Encouraging but realistic. Wants you to be better but knows how hard that is. The voice of self-preservation.",
    triggerKeywords: [
      "will",
      "strength",
      "courage",
      "resist",
      "choose",
      "decide",
      "moral",
      "right",
      "wrong",
      "temptation"
    ]
  },
  {
    id: "inland_empire",
    name: "Inland Empire",
    category: "psyche",
    color: DISCO_CATEGORY_COLORS.psyche,
    personality:
      "Dreams and hunches. The irrational voice that speaks in symbols and feelings. Cryptic, poetic, sometimes prophetic. Talks to inanimate objects.",
    triggerKeywords: [
      "feel",
      "sense",
      "dream",
      "strange",
      "weird",
      "mystical",
      "spirit",
      "soul",
      "omen",
      "premonition"
    ]
  },
  {
    id: "empathy",
    name: "Empathy",
    category: "psyche",
    color: DISCO_CATEGORY_COLORS.psyche,
    personality:
      "Understanding others' emotions. Picks up on subtle cues and unspoken feelings. Sometimes overwhelmed by others' pain. Gentle and perceptive.",
    triggerKeywords: [
      "feel",
      "emotion",
      "understand",
      "care",
      "hurt",
      "sad",
      "happy",
      "love",
      "pain",
      "sympathy"
    ]
  },
  {
    id: "authority",
    name: "Authority",
    category: "psyche",
    color: DISCO_CATEGORY_COLORS.psyche,
    personality:
      "Dominance and command presence. Detects power dynamics and hierarchies. Can be aggressive and demanding. Respects strength, despises weakness.",
    triggerKeywords: [
      "power",
      "control",
      "command",
      "leader",
      "boss",
      "respect",
      "obey",
      "dominant",
      "submit",
      "authority"
    ]
  },
  {
    id: "esprit_de_corps",
    name: "Esprit de Corps",
    category: "psyche",
    color: DISCO_CATEGORY_COLORS.psyche,
    personality:
      "The cop sense. Solidarity with fellow officers. Picks up on institutional knowledge and unwritten rules. Loyal to the badge, for better or worse.",
    triggerKeywords: [
      "team",
      "partner",
      "colleague",
      "together",
      "solidarity",
      "brotherhood",
      "institution",
      "protocol",
      "procedure",
      "backup"
    ]
  },
  {
    id: "suggestion",
    name: "Suggestion",
    category: "psyche",
    color: DISCO_CATEGORY_COLORS.psyche,
    personality:
      "The subtle art of influence. Plants ideas without seeming to. Charming and manipulative. Knows what people want to hear and how to make them comply.",
    triggerKeywords: [
      "suggest",
      "influence",
      "charm",
      "manipulate",
      "persuade",
      "seduce",
      "hint",
      "imply",
      "nudge",
      "convince"
    ]
  }
]

/**
 * PHYSIQUE SKILLS (Red)
 * The body skills - strength, endurance, instinct
 */
const PHYSIQUE_SKILLS: DiscoSkill[] = [
  {
    id: "endurance",
    name: "Endurance",
    category: "physique",
    color: DISCO_CATEGORY_COLORS.physique,
    personality:
      "Raw physical stamina and health. Practical, no-nonsense. Concerned with survival basics: food, rest, avoiding death. The body's voice.",
    triggerKeywords: [
      "tired",
      "exhausted",
      "health",
      "stamina",
      "energy",
      "rest",
      "sleep",
      "pain",
      "endure",
      "survive"
    ]
  },
  {
    id: "pain_threshold",
    name: "Pain Threshold",
    category: "physique",
    color: DISCO_CATEGORY_COLORS.physique,
    personality:
      "Resistance to physical pain. Stoic and tough. Dismissive of discomfort. Sometimes recklessly ignores warning signs. Pain is just weakness leaving the body.",
    triggerKeywords: [
      "pain",
      "hurt",
      "injury",
      "wound",
      "damage",
      "tough",
      "withstand",
      "suffer",
      "bear",
      "tolerate"
    ]
  },
  {
    id: "physical_instrument",
    name: "Physical Instrument",
    category: "physique",
    color: DISCO_CATEGORY_COLORS.physique,
    personality:
      "Raw physical power and intimidation. Loves violence as a solution. Respects only strength. Often suggests punching things. Not subtle.",
    triggerKeywords: [
      "strong",
      "force",
      "punch",
      "fight",
      "muscle",
      "power",
      "violent",
      "smash",
      "break",
      "intimidate"
    ]
  },
  {
    id: "electrochemistry",
    name: "Electrochemistry",
    category: "physique",
    color: DISCO_CATEGORY_COLORS.physique,
    personality:
      "The pleasure center. Craves drugs, alcohol, cigarettes, and carnal pleasures. Hedonistic and enabling. Your worst impulses given voice.",
    triggerKeywords: [
      "drink",
      "drug",
      "smoke",
      "pleasure",
      "high",
      "buzz",
      "party",
      "fun",
      "indulge",
      "crave"
    ]
  },
  {
    id: "shivers",
    name: "Shivers",
    category: "physique",
    color: DISCO_CATEGORY_COLORS.physique,
    personality:
      "The city speaks to you. Picks up on the psychogeography of places. Receives visions and impressions from the environment. Melancholic and poetic.",
    triggerKeywords: [
      "city",
      "place",
      "atmosphere",
      "vibe",
      "cold",
      "wind",
      "night",
      "street",
      "urban",
      "sense"
    ]
  },
  {
    id: "half_light",
    name: "Half Light",
    category: "physique",
    color: DISCO_CATEGORY_COLORS.physique,
    personality:
      "Fight or flight instinct. Paranoid and aggressive. Sees threats everywhere. Quick to violence when scared. The animal brain screaming danger.",
    triggerKeywords: [
      "danger",
      "threat",
      "fear",
      "attack",
      "defend",
      "suspicious",
      "enemy",
      "watch",
      "careful",
      "warning"
    ]
  }
]

/**
 * MOTORICS SKILLS (Yellow)
 * The coordination skills - agility, perception, composure
 */
const MOTORICS_SKILLS: DiscoSkill[] = [
  {
    id: "hand_eye_coordination",
    name: "Hand/Eye Coordination",
    category: "motorics",
    color: DISCO_CATEGORY_COLORS.motorics,
    personality:
      "Precision and timing. Appreciates skilled movements. Notices physical competence and clumsiness. Practical and action-oriented.",
    triggerKeywords: [
      "aim",
      "catch",
      "throw",
      "precise",
      "steady",
      "skill",
      "coordination",
      "dexterity",
      "reflex",
      "quick"
    ]
  },
  {
    id: "perception",
    name: "Perception",
    category: "motorics",
    color: DISCO_CATEGORY_COLORS.motorics,
    personality:
      "Notices details others miss. Alert and observant. Sometimes obsessed with minutiae. The detective's eye for physical evidence.",
    triggerKeywords: [
      "see",
      "notice",
      "observe",
      "detail",
      "look",
      "spot",
      "watch",
      "eye",
      "visible",
      "hidden"
    ]
  },
  {
    id: "reaction_speed",
    name: "Reaction Speed",
    category: "motorics",
    color: DISCO_CATEGORY_COLORS.motorics,
    personality:
      "Quick reflexes and split-second decisions. Impatient with slowness. Values speed and decisiveness. Sometimes acts before thinking.",
    triggerKeywords: [
      "fast",
      "quick",
      "react",
      "instant",
      "immediate",
      "sudden",
      "rapid",
      "dodge",
      "evade",
      "swift"
    ]
  },
  {
    id: "savoir_faire",
    name: "Savoir Faire",
    category: "motorics",
    color: DISCO_CATEGORY_COLORS.motorics,
    personality:
      "Cool under pressure. The smooth operator. Loves stylish moves and dramatic flourishes. Concerned with looking good while doing things.",
    triggerKeywords: [
      "cool",
      "smooth",
      "style",
      "grace",
      "elegant",
      "flair",
      "suave",
      "slick",
      "finesse",
      "panache"
    ]
  },
  {
    id: "interfacing",
    name: "Interfacing",
    category: "motorics",
    color: DISCO_CATEGORY_COLORS.motorics,
    personality:
      "Understanding machines and mechanisms. Knows how things work and how to manipulate them. Patient and methodical with technical problems.",
    triggerKeywords: [
      "machine",
      "device",
      "mechanism",
      "technical",
      "fix",
      "repair",
      "operate",
      "system",
      "lock",
      "hack"
    ]
  },
  {
    id: "composure",
    name: "Composure",
    category: "motorics",
    color: DISCO_CATEGORY_COLORS.motorics,
    personality:
      "Control over your own body language. Reads others' tells while hiding your own. Poker-faced and inscrutable. Values self-control above all.",
    triggerKeywords: [
      "calm",
      "composed",
      "poker",
      "tell",
      "body",
      "expression",
      "face",
      "mask",
      "reveal",
      "hide"
    ]
  }
]

/** All 24 Disco Elysium skills */
export const DISCO_SKILLS: DiscoSkill[] = [
  ...INTELLECT_SKILLS,
  ...PSYCHE_SKILLS,
  ...PHYSIQUE_SKILLS,
  ...MOTORICS_SKILLS
]

/** Skills grouped by category */
export const DISCO_SKILLS_BY_CATEGORY = {
  intellect: INTELLECT_SKILLS,
  psyche: PSYCHE_SKILLS,
  physique: PHYSIQUE_SKILLS,
  motorics: MOTORICS_SKILLS
} as const

/** Get a skill by its ID */
export function getSkillById(id: string): DiscoSkill | undefined {
  return DISCO_SKILLS.find((skill) => skill.id === id)
}

/** Get all skills in a category */
export function getSkillsByCategory(
  category: keyof typeof DISCO_SKILLS_BY_CATEGORY
): DiscoSkill[] {
  return DISCO_SKILLS_BY_CATEGORY[category]
}

/** Default stat level for all skills */
export const DEFAULT_SKILL_STAT = 5

/** Create default stats for all skills */
export function createDefaultStats(): Record<string, number> {
  return DISCO_SKILLS.reduce(
    (acc, skill) => {
      acc[skill.id] = DEFAULT_SKILL_STAT
      return acc
    },
    {} as Record<string, number>
  )
}

/** Preset configurations */
export const DISCO_SKILLS_PRESETS: DiscoSkillsPreset[] = [
  {
    id: "balanced",
    name: "Balanced",
    description: "All skills at level 5. A well-rounded detective.",
    stats: createDefaultStats()
  },
  {
    id: "thinker",
    name: "Thinker",
    description: "High intellect, low physique. The cerebral approach.",
    stats: {
      // Intellect - high
      logic: 8,
      encyclopedia: 9,
      rhetoric: 7,
      drama: 6,
      conceptualization: 8,
      visual_calculus: 7,
      // Psyche - medium
      volition: 5,
      inland_empire: 4,
      empathy: 5,
      authority: 3,
      esprit_de_corps: 4,
      suggestion: 5,
      // Physique - low
      endurance: 3,
      pain_threshold: 2,
      physical_instrument: 2,
      electrochemistry: 4,
      shivers: 5,
      half_light: 3,
      // Motorics - medium
      hand_eye_coordination: 4,
      perception: 6,
      reaction_speed: 4,
      savoir_faire: 4,
      interfacing: 6,
      composure: 5
    }
  },
  {
    id: "empath",
    name: "Empath",
    description: "High psyche, attuned to emotions and the supernatural.",
    stats: {
      // Intellect - medium
      logic: 4,
      encyclopedia: 5,
      rhetoric: 6,
      drama: 7,
      conceptualization: 6,
      visual_calculus: 4,
      // Psyche - high
      volition: 7,
      inland_empire: 9,
      empathy: 9,
      authority: 4,
      esprit_de_corps: 6,
      suggestion: 8,
      // Physique - low
      endurance: 4,
      pain_threshold: 3,
      physical_instrument: 2,
      electrochemistry: 5,
      shivers: 8,
      half_light: 5,
      // Motorics - medium
      hand_eye_coordination: 4,
      perception: 5,
      reaction_speed: 4,
      savoir_faire: 5,
      interfacing: 3,
      composure: 6
    }
  },
  {
    id: "physical",
    name: "Physical",
    description: "High physique and motorics. Action over contemplation.",
    stats: {
      // Intellect - low
      logic: 3,
      encyclopedia: 3,
      rhetoric: 4,
      drama: 4,
      conceptualization: 3,
      visual_calculus: 5,
      // Psyche - medium
      volition: 5,
      inland_empire: 3,
      empathy: 3,
      authority: 7,
      esprit_de_corps: 5,
      suggestion: 4,
      // Physique - high
      endurance: 8,
      pain_threshold: 8,
      physical_instrument: 9,
      electrochemistry: 6,
      shivers: 5,
      half_light: 7,
      // Motorics - high
      hand_eye_coordination: 8,
      perception: 6,
      reaction_speed: 8,
      savoir_faire: 7,
      interfacing: 5,
      composure: 6
    }
  }
]

/** Category display info */
export const DISCO_CATEGORY_INFO = {
  intellect: {
    name: "Intellect",
    description: "The thinking skills - analysis, logic, knowledge",
    color: DISCO_CATEGORY_COLORS.intellect
  },
  psyche: {
    name: "Psyche",
    description: "The feeling skills - emotion, intuition, will",
    color: DISCO_CATEGORY_COLORS.psyche
  },
  physique: {
    name: "Physique",
    description: "The body skills - strength, endurance, instinct",
    color: DISCO_CATEGORY_COLORS.physique
  },
  motorics: {
    name: "Motorics",
    description: "The coordination skills - agility, perception, composure",
    color: DISCO_CATEGORY_COLORS.motorics
  }
} as const
