import type {
  MessageSteeringFlags,
  MessageSteeringMode,
  MessageSteeringPromptTemplates,
  MessageSteeringState,
  ResolvedMessageSteering
} from "@/types/message-steering"

type ResolveMessageSteeringInput = {
  mode?: MessageSteeringMode | null
  continueAsUser?: boolean
  impersonateUser?: boolean
  forceNarrate?: boolean
}

export const EMPTY_MESSAGE_STEERING_STATE: MessageSteeringState = {
  mode: "none",
  forceNarrate: false
}

export const MESSAGE_STEERING_PROMPTS_STORAGE_KEY = "messageSteeringPrompts"

export const DEFAULT_MESSAGE_STEERING_PROMPTS: MessageSteeringPromptTemplates = {
  continueAsUser:
    "Continue the user's current thought in the same voice and perspective.",
  impersonateUser:
    "Write this reply as if it is authored by the user, in first person, while preserving the user's intent.",
  forceNarrate: "Use narrative prose style for this reply."
}

const normalizePromptText = (value: unknown, fallback: string): string => {
  if (typeof value !== "string") return fallback
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : fallback
}

export const normalizeMessageSteeringPrompts = (
  input?: Partial<MessageSteeringPromptTemplates> | null
): MessageSteeringPromptTemplates => ({
  continueAsUser: normalizePromptText(
    input?.continueAsUser,
    DEFAULT_MESSAGE_STEERING_PROMPTS.continueAsUser
  ),
  impersonateUser: normalizePromptText(
    input?.impersonateUser,
    DEFAULT_MESSAGE_STEERING_PROMPTS.impersonateUser
  ),
  forceNarrate: normalizePromptText(
    input?.forceNarrate,
    DEFAULT_MESSAGE_STEERING_PROMPTS.forceNarrate
  )
})

export const toMessageSteeringPromptPayload = (
  input?: Partial<MessageSteeringPromptTemplates> | null
): {
  continue_as_user: string
  impersonate_user: string
  force_narrate: string
} => {
  const prompts = normalizeMessageSteeringPrompts(input)
  return {
    continue_as_user: prompts.continueAsUser,
    impersonate_user: prompts.impersonateUser,
    force_narrate: prompts.forceNarrate
  }
}

export const resolveMessageSteering = (
  input: ResolveMessageSteeringInput
): ResolvedMessageSteering => {
  const mode = input.mode ?? "none"
  const modeContinue = mode === "continue_as_user"
  const modeImpersonate = mode === "impersonate_user"
  const continueAsUser = Boolean(input.continueAsUser || modeContinue)
  const impersonateUser = Boolean(input.impersonateUser || modeImpersonate)
  const forceNarrate = Boolean(input.forceNarrate)

  const hadConflict = continueAsUser && impersonateUser
  if (hadConflict) {
    return {
      mode: "impersonate_user",
      continueAsUser: false,
      impersonateUser: true,
      forceNarrate,
      hadConflict: true
    }
  }

  if (impersonateUser) {
    return {
      mode: "impersonate_user",
      continueAsUser: false,
      impersonateUser: true,
      forceNarrate,
      hadConflict: false
    }
  }

  if (continueAsUser) {
    return {
      mode: "continue_as_user",
      continueAsUser: true,
      impersonateUser: false,
      forceNarrate,
      hadConflict: false
    }
  }

  return {
    mode: "none",
    continueAsUser: false,
    impersonateUser: false,
    forceNarrate,
    hadConflict: false
  }
}

export const buildMessageSteeringSnippet = (
  steering: MessageSteeringFlags,
  promptTemplates?: Partial<MessageSteeringPromptTemplates> | null
): string | null => {
  const prompts = normalizeMessageSteeringPrompts(promptTemplates)
  const instructions: string[] = []

  if (steering.impersonateUser) {
    instructions.push(prompts.impersonateUser)
  } else if (steering.continueAsUser) {
    instructions.push(prompts.continueAsUser)
  }

  if (steering.forceNarrate) {
    instructions.push(prompts.forceNarrate)
  }

  if (instructions.length === 0) {
    return null
  }

  return `Steering instruction (single response): ${instructions.join(" ")}`
}

export const hasActiveMessageSteering = (
  steering: MessageSteeringFlags
): boolean =>
  Boolean(
    steering.continueAsUser ||
      steering.impersonateUser ||
      steering.forceNarrate
  )
