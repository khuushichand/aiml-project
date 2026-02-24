export type DiffLine = { type: 'same' | 'add' | 'del'; text: string }

export const DIFF_SYNC_LINE_THRESHOLD = 4000
export const DIFF_HARD_CHAR_THRESHOLD = 300_000
export const DIFF_SAMPLED_CHAR_BUDGET = 120_000

type DiffWorkerRequest = {
  leftText: string
  rightText: string
}

type DiffWorkerResultMessage = {
  type: 'result'
  lines: DiffLine[]
}

type DiffWorkerErrorMessage = {
  type: 'error'
  message?: string
}

type DiffWorkerResponse = DiffWorkerResultMessage | DiffWorkerErrorMessage

export function computeDiffSync(oldStr: string, newStr: string): DiffLine[] {
  const a = String(oldStr || '').split('\n')
  const b = String(newStr || '').split('\n')
  const n = a.length
  const m = b.length

  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ type: 'same', text: a[i] })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: 'del', text: a[i] })
      i += 1
    } else {
      out.push({ type: 'add', text: b[j] })
      j += 1
    }
  }

  while (i < n) {
    out.push({ type: 'del', text: a[i] })
    i += 1
  }
  while (j < m) {
    out.push({ type: 'add', text: b[j] })
    j += 1
  }
  return out
}

const countLines = (text: string): number => String(text || '').split('\n').length
const countChars = (leftText: string, rightText: string): number =>
  String(leftText || '').length + String(rightText || '').length

export const shouldUseWorkerDiff = (
  leftText: string,
  rightText: string,
  threshold: number = DIFF_SYNC_LINE_THRESHOLD
): boolean => countLines(leftText) + countLines(rightText) > threshold

export const shouldRequireSampling = (
  leftText: string,
  rightText: string,
  threshold: number = DIFF_HARD_CHAR_THRESHOLD
): boolean => countChars(leftText, rightText) > threshold

export const sampleTextForDiff = (text: string, charBudget: number = DIFF_SAMPLED_CHAR_BUDGET): string => {
  const normalized = String(text || '')
  if (normalized.length <= charBudget) return normalized
  const half = Math.floor(charBudget / 2)
  const head = normalized.slice(0, half)
  const tail = normalized.slice(-half)
  return `${head}\n\n...[sampled middle omitted for performance]...\n\n${tail}`
}

export const createDiffWorker = (): Worker =>
  new Worker(new URL('./diff.worker.ts', import.meta.url), { type: 'module' })

export const computeDiffWithWorker = async (
  leftText: string,
  rightText: string
): Promise<DiffLine[]> => {
  return await new Promise<DiffLine[]>((resolve, reject) => {
    let settled = false
    const worker = createDiffWorker()

    const finalize = (fn: () => void) => {
      if (settled) return
      settled = true
      try {
        worker.terminate()
      } catch {
        // Ignore worker termination issues.
      }
      fn()
    }

    worker.onmessage = (event: MessageEvent<DiffWorkerResponse>) => {
      const payload = event.data
      if (!payload || typeof payload !== 'object') {
        finalize(() => reject(new Error('Diff worker returned invalid payload')))
        return
      }
      if (payload.type === 'result') {
        finalize(() => resolve(Array.isArray(payload.lines) ? payload.lines : []))
        return
      }
      if (payload.type === 'error') {
        finalize(() => reject(new Error(payload.message || 'Diff worker failed')))
        return
      }
      finalize(() => reject(new Error('Diff worker returned unknown response type')))
    }

    worker.onerror = () => {
      finalize(() => reject(new Error('Diff worker crashed')))
    }

    const request: DiffWorkerRequest = {
      leftText: String(leftText || ''),
      rightText: String(rightText || '')
    }
    worker.postMessage(request)
  })
}

