const LOCAL_SINGLE_USER_DEMO_KEY = "THIS-IS-A-SECURE-KEY-123-REPLACE-ME"

const KNOWN_PLACEHOLDER_VALUES = new Set([
  "REPLACE-ME",
  "REPLACE_ME",
  "<REPLACE-ME>",
  "<REPLACE_ME>",
  "YOUR_API_KEY",
  "YOUR_API_KEY_HERE",
  "<YOUR_API_KEY>",
  "<YOUR_API_KEY_HERE>",
  "API_KEY",
  "CHANGE_ME",
  "CHANGEME"
])

export function isPlaceholderApiKey(key?: string | null): boolean {
  if (!key) return false
  const normalized = String(key).trim()
  if (!normalized) return false
  if (normalized === LOCAL_SINGLE_USER_DEMO_KEY) return false
  return KNOWN_PLACEHOLDER_VALUES.has(normalized.toUpperCase())
}
