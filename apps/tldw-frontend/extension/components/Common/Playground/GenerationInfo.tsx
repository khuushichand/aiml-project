import type { GenerationInfo as GenerationInfoType } from "./types"

type Props = {
  generationInfo?: GenerationInfoType
}

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value)

const calculateTokensPerSecond = (
  evalCount?: number,
  evalDuration?: number
) => {
  if (!isFiniteNumber(evalCount) || !isFiniteNumber(evalDuration)) return 0
  if (evalDuration <= 0) return 0
  return (evalCount / evalDuration) * 1e9
}

const formatDuration = (nanoseconds?: number) => {
  if (!isFiniteNumber(nanoseconds)) return "0ms"
  const ms = nanoseconds / 1e6
  if (ms < 1) return `${ms.toFixed(3)}ms`
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

const EXCLUDED_KEYS = new Set(["model", "context", "response"])

export const GenerationInfo = ({ generationInfo }: Props) => {
  if (!generationInfo) return null

  const evalCount = generationInfo.eval_count
  const evalDuration = generationInfo.eval_duration
  const shouldShowTokensPerSecond =
    isFiniteNumber(evalCount) &&
    isFiniteNumber(evalDuration) &&
    evalDuration > 0

  const metricsToDisplay = {
    ...generationInfo,
    ...(shouldShowTokensPerSecond
      ? {
          tokens_per_second: calculateTokensPerSecond(
            evalCount,
            evalDuration
          ).toFixed(2)
        }
      : {})
  }

  return (
    <div className="p-2 w-full">
      <div className="flex flex-col gap-2">
        {Object.entries(metricsToDisplay)
          .filter(([key]) => !EXCLUDED_KEYS.has(key))
          .map(([key, value]) => (
            <div key={key} className="flex flex-wrap justify-between">
              <div className="font-medium text-xs">{key}</div>
              <div className="font-medium text-xs break-all">
                {key.includes("duration") && isFiniteNumber(value)
                  ? formatDuration(value)
                  : typeof value === "object" && value !== null
                    ? JSON.stringify(value)
                    : String(value)}
              </div>
            </div>
          ))}
      </div>
    </div>
  )
}
