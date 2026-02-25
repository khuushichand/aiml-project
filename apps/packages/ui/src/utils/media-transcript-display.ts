const LEADING_TRANSCRIPT_TIMESTAMP_PATTERN =
  /^(\s*)(?:\[(\d{1,2}:\d{2}(?::\d{2})?)\]|(\d{1,2}:\d{2}(?::\d{2})?))(\s*[-–—:]?\s*)(.*)$/

const normalizeTranscriptContent = (content: string): string =>
  content.replace(/\r\n/g, '\n')

export interface LeadingTranscriptTimingMatch {
  leadingWhitespace: string
  timestamp: string
  separator: string
  text: string
}

export const parseLeadingTranscriptTiming = (
  line: string
): LeadingTranscriptTimingMatch | null => {
  const match = line.match(LEADING_TRANSCRIPT_TIMESTAMP_PATTERN)
  if (!match) return null
  return {
    leadingWhitespace: match[1] || '',
    timestamp: match[2] || match[3] || '',
    separator: match[4] || '',
    text: match[5] || ''
  }
}

export const hasLeadingTranscriptTimings = (content: string): boolean => {
  if (!content) return false
  const normalized = normalizeTranscriptContent(content)
  return normalized.split('\n').some((line) => parseLeadingTranscriptTiming(line) != null)
}

export const stripLeadingTranscriptTimings = (content: string): string => {
  if (!content) return ''
  const normalized = normalizeTranscriptContent(content)
  return normalized
    .split('\n')
    .map((line) => {
      const parsed = parseLeadingTranscriptTiming(line)
      if (!parsed) return line
      return `${parsed.leadingWhitespace}${parsed.text}`
    })
    .join('\n')
}
