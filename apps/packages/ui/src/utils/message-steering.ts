import type {
  MessageSteeringFlags,
  MessageSteeringMode,
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
  steering: MessageSteeringFlags
): string | null => {
  const instructions: string[] = []

  if (steering.impersonateUser) {
    instructions.push(
      "Write this reply as if it is authored by the user, in first person, while preserving the user's intent."
    )
  } else if (steering.continueAsUser) {
    instructions.push(
      "Continue the user's current thought in the same voice and perspective."
    )
  }

  if (steering.forceNarrate) {
    instructions.push(
      "Use narrative prose style for this reply."
    )
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

