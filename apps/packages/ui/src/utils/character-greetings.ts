export type CharacterGreetingFields = {
  greeting?: unknown
  first_message?: unknown
  firstMessage?: unknown
  greet?: unknown
  alternate_greetings?: unknown
  alternateGreetings?: unknown
}

export type GreetingOption = {
  id: string
  text: string
  index: number
  sourceKey?: string
  sourceLabel?: string
}

export type GreetingEntry = {
  text: string
  sourceKey: string
  sourceLabel: string
}

const normalizeStringEntries = (value: unknown[]): string[] =>
  value
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter((entry) => entry.length > 0)

const tryParseStringifiedGreetingList = (value: string): string[] | null => {
  try {
    const parsed = JSON.parse(value)
    if (Array.isArray(parsed)) {
      return normalizeStringEntries(parsed)
    }
    if (typeof parsed === "string") {
      const nestedParsed = JSON.parse(parsed)
      if (Array.isArray(nestedParsed)) {
        return normalizeStringEntries(nestedParsed)
      }
    }
  } catch {
    return null
  }
  return null
}

export const normalizeGreetingValue = (value: unknown): string[] => {
  if (!value) return []
  if (Array.isArray(value)) {
    return normalizeStringEntries(value)
  }
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (trimmed.length === 0) return []
    const parsedList = tryParseStringifiedGreetingList(trimmed)
    if (parsedList) return parsedList
    return [trimmed]
  }
  return []
}

const GREETING_SOURCES: Array<{ key: keyof CharacterGreetingFields; label: string }> =
  [
    { key: "greeting", label: "Greeting" },
    { key: "first_message", label: "First message" },
    { key: "firstMessage", label: "First message" },
    { key: "greet", label: "Greeting" },
    { key: "alternate_greetings", label: "Alternate greeting" },
    { key: "alternateGreetings", label: "Alternate greeting" }
  ]

export const collectGreetings = (
  character: CharacterGreetingFields | null | undefined
): string[] => {
  const greetings = [
    ...normalizeGreetingValue(character?.greeting),
    ...normalizeGreetingValue(character?.first_message),
    ...normalizeGreetingValue(character?.firstMessage),
    ...normalizeGreetingValue(character?.greet),
    ...normalizeGreetingValue(character?.alternate_greetings),
    ...normalizeGreetingValue(character?.alternateGreetings)
  ]
  return Array.from(new Set(greetings))
}

export const collectGreetingEntries = (
  character: CharacterGreetingFields | null | undefined
): GreetingEntry[] => {
  if (!character) return []
  const entries: GreetingEntry[] = []
  GREETING_SOURCES.forEach(({ key, label }) => {
    const values = normalizeGreetingValue(
      character[key as keyof CharacterGreetingFields]
    )
    values.forEach((text) => {
      entries.push({
        text,
        sourceKey: String(key),
        sourceLabel: label
      })
    })
  })

  const seen = new Set<string>()
  const deduped: GreetingEntry[] = []
  entries.forEach((entry) => {
    if (seen.has(entry.text)) return
    seen.add(entry.text)
    deduped.push(entry)
  })

  return deduped
}

const hashString = (value: string): string => {
  let hash = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i)
    hash +=
      (hash << 1) +
      (hash << 4) +
      (hash << 7) +
      (hash << 8) +
      (hash << 24)
  }
  return (hash >>> 0).toString(36)
}

export const buildGreetingId = (text: string, index: number): string =>
  `greeting:${index}:${hashString(text)}`

export const buildGreetingOptions = (greetings: string[]): GreetingOption[] =>
  greetings.map((text, index) => ({
    id: buildGreetingId(text, index),
    text,
    index
  }))

export const buildGreetingOptionsFromEntries = (
  entries: GreetingEntry[]
): GreetingOption[] =>
  entries.map((entry, index) => ({
    id: buildGreetingId(entry.text, index),
    text: entry.text,
    index,
    sourceKey: entry.sourceKey,
    sourceLabel: entry.sourceLabel
  }))

export const buildGreetingsChecksumFromOptions = (
  options: GreetingOption[]
): string =>
  hashString(
    options
      .map((option) => `${option.id}:${option.text}`)
      .join("\u001f")
  )

export const buildGreetingsChecksum = (greetings: string[]): string =>
  buildGreetingsChecksumFromOptions(buildGreetingOptions(greetings))

export const isGreetingMessageType = (messageType?: string | null): boolean =>
  messageType === "character:greeting" || messageType === "greeting"

export const pickGreeting = (greetings: string[]): string => {
  if (greetings.length === 0) return ""
  if (greetings.length === 1) return greetings[0]
  const index = Math.floor(Math.random() * greetings.length)
  return greetings[index]
}
