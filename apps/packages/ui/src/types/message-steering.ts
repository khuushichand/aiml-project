export type MessageSteeringMode =
  | "none"
  | "continue_as_user"
  | "impersonate_user"

export type MessageSteeringState = {
  mode: MessageSteeringMode
  forceNarrate: boolean
}

export type MessageSteeringFlags = {
  continueAsUser: boolean
  impersonateUser: boolean
  forceNarrate: boolean
}

export type ResolvedMessageSteering = MessageSteeringFlags & {
  mode: MessageSteeringMode
  hadConflict: boolean
}
