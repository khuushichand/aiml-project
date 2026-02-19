const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const normalizeEmailAddress = (value: string): string => value.trim().toLowerCase()

export const isValidEmailAddress = (value: string): boolean => {
  const normalized = normalizeEmailAddress(value)
  if (!normalized) return false
  return EMAIL_PATTERN.test(normalized)
}

export const findInvalidEmailRecipients = (recipients: string[]): string[] => (
  recipients
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)
    .filter((entry) => !isValidEmailAddress(entry))
)
