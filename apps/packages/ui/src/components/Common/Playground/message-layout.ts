export type MessageRenderSide = "left" | "right"

type ResolveMessageRenderSideParams = {
  isBot: boolean
  isSystemMessage: boolean
}

export const resolveMessageRenderSide = ({
  isBot,
  isSystemMessage
}: ResolveMessageRenderSideParams): MessageRenderSide => {
  if (isBot || isSystemMessage) return "left"
  return "right"
}

export const resolveAvatarColumnAlignment = (
  side: MessageRenderSide
): "items-end" | "items-start" => {
  if (side === "left") return "items-end"
  return "items-start"
}
