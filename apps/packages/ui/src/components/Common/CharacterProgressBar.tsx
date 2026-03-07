import React from "react"

export interface CharacterProgressBarProps {
  count: number
  max: number
  warnAt?: number
  dangerAt?: number
}

function getColor(count: number, warnAt: number, dangerAt: number) {
  if (count >= dangerAt) return { name: "red" as const, cls: "bg-red-500" }
  if (count >= warnAt) return { name: "amber" as const, cls: "bg-amber-500" }
  return { name: "green" as const, cls: "bg-green-500" }
}

export const CharacterProgressBar: React.FC<CharacterProgressBarProps> = ({
  count,
  max,
  warnAt = 2000,
  dangerAt = 6000
}) => {
  const pct = Math.min((count / max) * 100, 100)
  const color = getColor(count, warnAt, dangerAt)

  return (
    <div>
      <div
        role="progressbar"
        aria-valuenow={count}
        aria-valuemax={max}
        aria-label="Character count"
        className="h-0.5 w-full rounded bg-border"
      >
        <div
          data-color={color.name}
          className={`h-full rounded transition-all ${color.cls}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1 text-right text-xs text-muted-foreground">
        {count.toLocaleString()} / {max.toLocaleString()} chars
      </p>
    </div>
  )
}

export default CharacterProgressBar
