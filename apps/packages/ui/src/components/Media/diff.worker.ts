type DiffLine = { type: 'same' | 'add' | 'del'; text: string }

type DiffWorkerRequest = {
  leftText: string
  rightText: string
}

type DiffWorkerResult = {
  type: 'result'
  lines: DiffLine[]
}

type DiffWorkerError = {
  type: 'error'
  message: string
}

const computeDiff = (oldStr: string, newStr: string): DiffLine[] => {
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

self.onmessage = (event: MessageEvent<DiffWorkerRequest>) => {
  try {
    const request = event.data
    const result: DiffWorkerResult = {
      type: 'result',
      lines: computeDiff(request?.leftText || '', request?.rightText || '')
    }
    self.postMessage(result)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown diff worker error'
    const payload: DiffWorkerError = { type: 'error', message }
    self.postMessage(payload)
  }
}

export {}

