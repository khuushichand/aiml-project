import type {
  ChatRichTextColorOption,
  ChatRichTextFontOption,
  ChatRichTextStylePreset
} from "@/types/chat-settings"

export const CHAT_RICH_TEXT_STYLE_PRESET_VALUES: readonly ChatRichTextStylePreset[] = [
  "default",
  "muted",
  "high_contrast",
  "custom"
] as const

export const CHAT_RICH_TEXT_COLOR_VALUES: readonly ChatRichTextColorOption[] = [
  "default",
  "text",
  "muted",
  "primary",
  "accent",
  "success",
  "warn",
  "danger"
] as const

export const CHAT_RICH_TEXT_FONT_VALUES: readonly ChatRichTextFontOption[] = [
  "default",
  "sans",
  "serif",
  "mono"
] as const

export type ChatRichTextStyleTokens = {
  chatRichItalicColor: ChatRichTextColorOption
  chatRichItalicFont: ChatRichTextFontOption
  chatRichBoldColor: ChatRichTextColorOption
  chatRichBoldFont: ChatRichTextFontOption
  chatRichQuoteTextColor: ChatRichTextColorOption
  chatRichQuoteFont: ChatRichTextFontOption
  chatRichQuoteBorderColor: ChatRichTextColorOption
  chatRichQuoteBackgroundColor: ChatRichTextColorOption
}

const RGB_COLOR_TOKEN: Record<Exclude<ChatRichTextColorOption, "default">, string> = {
  text: "--color-text",
  muted: "--color-text-muted",
  primary: "--color-primary",
  accent: "--color-accent",
  success: "--color-success",
  warn: "--color-warn",
  danger: "--color-danger"
}

const FONT_VALUE: Record<Exclude<ChatRichTextFontOption, "default">, string> = {
  sans: "ui-sans-serif, system-ui, -apple-system, sans-serif",
  serif: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
  mono: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"
}

const toRgbVar = (tokenName: string): string => `rgb(var(${tokenName}))`
const toRgbaVar = (tokenName: string, alpha: number): string =>
  `rgba(var(${tokenName}), ${alpha})`

const resolveColor = (
  option: ChatRichTextColorOption,
  fallback: string,
  alpha?: number
): string => {
  if (option === "default") return fallback
  const token = RGB_COLOR_TOKEN[option]
  if (!token) return fallback
  if (typeof alpha === "number") {
    return toRgbaVar(token, alpha)
  }
  return toRgbVar(token)
}

const resolveFont = (option: ChatRichTextFontOption): string => {
  if (option === "default") return "inherit"
  return FONT_VALUE[option] ?? "inherit"
}

export const CHAT_RICH_TEXT_STYLE_PRESETS: Record<
  Exclude<ChatRichTextStylePreset, "custom">,
  ChatRichTextStyleTokens
> = {
  default: {
    chatRichItalicColor: "default",
    chatRichItalicFont: "default",
    chatRichBoldColor: "default",
    chatRichBoldFont: "default",
    chatRichQuoteTextColor: "default",
    chatRichQuoteFont: "default",
    chatRichQuoteBorderColor: "default",
    chatRichQuoteBackgroundColor: "default"
  },
  muted: {
    chatRichItalicColor: "muted",
    chatRichItalicFont: "default",
    chatRichBoldColor: "text",
    chatRichBoldFont: "default",
    chatRichQuoteTextColor: "muted",
    chatRichQuoteFont: "serif",
    chatRichQuoteBorderColor: "muted",
    chatRichQuoteBackgroundColor: "muted"
  },
  high_contrast: {
    chatRichItalicColor: "warn",
    chatRichItalicFont: "serif",
    chatRichBoldColor: "primary",
    chatRichBoldFont: "sans",
    chatRichQuoteTextColor: "text",
    chatRichQuoteFont: "default",
    chatRichQuoteBorderColor: "danger",
    chatRichQuoteBackgroundColor: "primary"
  }
}

export const normalizeChatRichTextStylePreset = (
  value: unknown,
  fallback: ChatRichTextStylePreset = "default"
): ChatRichTextStylePreset => {
  if (
    value === "default" ||
    value === "muted" ||
    value === "high_contrast" ||
    value === "custom"
  ) {
    return value
  }
  return fallback
}

export const normalizeChatRichTextColor = (
  value: unknown,
  fallback: ChatRichTextColorOption = "default"
): ChatRichTextColorOption => {
  if (CHAT_RICH_TEXT_COLOR_VALUES.includes(value as ChatRichTextColorOption)) {
    return value as ChatRichTextColorOption
  }
  return fallback
}

export const normalizeChatRichTextFont = (
  value: unknown,
  fallback: ChatRichTextFontOption = "default"
): ChatRichTextFontOption => {
  if (CHAT_RICH_TEXT_FONT_VALUES.includes(value as ChatRichTextFontOption)) {
    return value as ChatRichTextFontOption
  }
  return fallback
}

export const resolveChatRichTextStyleCssVars = (
  tokens: ChatRichTextStyleTokens
): Record<string, string> => ({
  "--rt-italic-color": resolveColor(tokens.chatRichItalicColor, "inherit"),
  "--rt-italic-font": resolveFont(tokens.chatRichItalicFont),
  "--rt-bold-color": resolveColor(tokens.chatRichBoldColor, "inherit"),
  "--rt-bold-font": resolveFont(tokens.chatRichBoldFont),
  "--rt-quote-text-color": resolveColor(tokens.chatRichQuoteTextColor, "inherit"),
  "--rt-quote-font": resolveFont(tokens.chatRichQuoteFont),
  "--rt-quote-border-color": resolveColor(
    tokens.chatRichQuoteBorderColor,
    toRgbVar("--color-border"),
    0.6
  ),
  "--rt-quote-bg-color": resolveColor(
    tokens.chatRichQuoteBackgroundColor,
    toRgbaVar("--color-surface-2", 0.4),
    0.16
  )
})
