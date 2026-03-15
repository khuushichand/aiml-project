# TTS Listen Tab UX Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the Listen (TTS) tab from a single vertical scroll into a two-zone layout with a focused Workspace (Zone 1) and collapsible Inspector Panel (Zone 2), adding a sticky action bar, character progress bar, voice preview, and labeled segment navigation.

**Architecture:** Extract ~800 lines of inline JSX from SpeechPlaygroundPage into 8 focused components. Zone 1 contains the core type-and-play loop. Zone 2 (Ant Design Drawer on tablet/mobile, side panel on desktop) holds all configuration organized into three tabs. A sticky action bar keeps Play/Stop/Download always visible. No business logic changes — hooks, services, and API calls are untouched.

**Tech Stack:** React 18, TypeScript, Ant Design 5, TailwindCSS, Vitest + React Testing Library, @plasmohq/storage/hook for persisted state.

**Design doc:** `Docs/Plans/2026-03-06-tts-listen-tab-ux-redesign.md`

---

## Task 1: CharacterProgressBar Component

The simplest new component. No dependencies on other new code. Good first commit to validate the test setup.

**Files:**
- Create: `apps/packages/ui/src/components/Common/CharacterProgressBar.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/CharacterProgressBar.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Common/__tests__/CharacterProgressBar.test.tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { CharacterProgressBar } from "../CharacterProgressBar"

describe("CharacterProgressBar", () => {
  it("renders count and max", () => {
    render(<CharacterProgressBar count={1240} max={8000} />)
    expect(screen.getByText("1,240 / 8,000 chars")).toBeInTheDocument()
  })

  it("applies green color when under warning threshold", () => {
    const { container } = render(
      <CharacterProgressBar count={500} max={8000} warnAt={2000} />
    )
    const bar = container.querySelector("[role='progressbar']")
    expect(bar).toHaveAttribute("aria-valuenow", "500")
    expect(bar?.querySelector("[data-color]")?.getAttribute("data-color")).toBe("green")
  })

  it("applies amber color when between warn and danger", () => {
    const { container } = render(
      <CharacterProgressBar count={3000} max={8000} warnAt={2000} dangerAt={6000} />
    )
    const bar = container.querySelector("[role='progressbar']")
    expect(bar?.querySelector("[data-color]")?.getAttribute("data-color")).toBe("amber")
  })

  it("applies red color when over danger threshold", () => {
    const { container } = render(
      <CharacterProgressBar count={7000} max={8000} warnAt={2000} dangerAt={6000} />
    )
    const bar = container.querySelector("[role='progressbar']")
    expect(bar?.querySelector("[data-color]")?.getAttribute("data-color")).toBe("red")
  })

  it("has correct ARIA attributes", () => {
    const { container } = render(
      <CharacterProgressBar count={1240} max={8000} />
    )
    const bar = container.querySelector("[role='progressbar']")
    expect(bar).toHaveAttribute("aria-valuenow", "1240")
    expect(bar).toHaveAttribute("aria-valuemax", "8000")
    expect(bar).toHaveAttribute("aria-label", "Character count")
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Common/__tests__/CharacterProgressBar.test.tsx`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```tsx
// apps/packages/ui/src/components/Common/CharacterProgressBar.tsx
import React from "react"

type Props = {
  count: number
  max: number
  warnAt?: number
  dangerAt?: number
}

const getColor = (count: number, warnAt: number, dangerAt: number) => {
  if (count >= dangerAt) return "red"
  if (count >= warnAt) return "amber"
  return "green"
}

const COLOR_CLASSES: Record<string, string> = {
  green: "bg-green-500",
  amber: "bg-amber-500",
  red: "bg-red-500"
}

export const CharacterProgressBar: React.FC<Props> = ({
  count,
  max,
  warnAt = 2000,
  dangerAt = 6000
}) => {
  const pct = Math.min((count / max) * 100, 100)
  const color = getColor(count, warnAt, dangerAt)

  return (
    <div className="space-y-1">
      <div
        role="progressbar"
        aria-valuenow={count}
        aria-valuemax={max}
        aria-label="Character count"
        className="h-0.5 w-full rounded-full bg-border overflow-hidden"
      >
        <div
          data-color={color}
          className={`h-full transition-all duration-300 ${COLOR_CLASSES[color]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="text-right text-xs text-text-subtle">
        {count.toLocaleString()} / {max.toLocaleString()} chars
      </div>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Common/__tests__/CharacterProgressBar.test.tsx`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/CharacterProgressBar.tsx apps/packages/ui/src/components/Common/__tests__/CharacterProgressBar.test.tsx
git commit -m "feat(tts): add CharacterProgressBar component with ARIA and color thresholds"
```

---

## Task 2: VoicePreviewButton Component

Small component. Depends on `tldwClient.synthesizeSpeech` which we'll mock.

**Files:**
- Create: `apps/packages/ui/src/components/Common/VoicePreviewButton.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/VoicePreviewButton.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Common/__tests__/VoicePreviewButton.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { VoicePreviewButton } from "../VoicePreviewButton"

const synthesizeMock = vi.fn()

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    synthesizeSpeech: (...args: any[]) => synthesizeMock(...args)
  }
}))

// Mock HTMLAudioElement.play
const playMock = vi.fn().mockResolvedValue(undefined)
const pauseMock = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(window, "Audio").mockImplementation(
    () =>
      ({
        play: playMock,
        pause: pauseMock,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        src: ""
      }) as unknown as HTMLAudioElement
  )
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock")
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {})
})

describe("VoicePreviewButton", () => {
  it("renders a preview button", () => {
    render(<VoicePreviewButton model="kokoro" voice="af_heart" provider="tldw" />)
    expect(screen.getByRole("button", { name: /preview/i })).toBeInTheDocument()
  })

  it("is disabled when no voice is provided", () => {
    render(<VoicePreviewButton model="kokoro" voice="" provider="tldw" />)
    expect(screen.getByRole("button", { name: /preview/i })).toBeDisabled()
  })

  it("calls synthesizeSpeech on click and plays audio", async () => {
    const fakeBuffer = new ArrayBuffer(16)
    synthesizeMock.mockResolvedValue(fakeBuffer)

    render(<VoicePreviewButton model="kokoro" voice="af_heart" provider="tldw" />)
    fireEvent.click(screen.getByRole("button", { name: /preview/i }))

    await waitFor(() => {
      expect(synthesizeMock).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ model: "kokoro", voice: "af_heart" })
      )
    })
    expect(playMock).toHaveBeenCalled()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Common/__tests__/VoicePreviewButton.test.tsx`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```tsx
// apps/packages/ui/src/components/Common/VoicePreviewButton.tsx
import React, { useState, useRef, useCallback } from "react"
import { Button, Tooltip } from "antd"
import { Play, Square } from "lucide-react"
import { tldwClient } from "@/services/tldw/TldwApiClient"

const PREVIEW_TEXT = "Hello, this is a preview of the selected voice."

type Props = {
  model: string
  voice: string
  provider: string
  className?: string
}

export const VoicePreviewButton: React.FC<Props> = ({
  model,
  voice,
  provider,
  className
}) => {
  const [loading, setLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const urlRef = useRef<string | null>(null)

  const cleanup = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
    setPlaying(false)
  }, [])

  const handleClick = useCallback(async () => {
    if (playing) {
      cleanup()
      return
    }
    if (!voice || provider === "browser") return
    setLoading(true)
    try {
      const buffer = await tldwClient.synthesizeSpeech(PREVIEW_TEXT, {
        model,
        voice,
        responseFormat: "mp3"
      })
      const blob = new Blob([buffer], { type: "audio/mpeg" })
      const url = URL.createObjectURL(blob)
      urlRef.current = url
      const audio = new Audio(url)
      audioRef.current = audio
      audio.addEventListener("ended", cleanup)
      setPlaying(true)
      await audio.play()
    } catch {
      cleanup()
    } finally {
      setLoading(false)
    }
  }, [cleanup, model, playing, provider, voice])

  React.useEffect(() => () => cleanup(), [cleanup])

  const disabled = !voice || provider === "browser"

  return (
    <Tooltip title={disabled ? "Select a voice first" : "Preview voice"}>
      <Button
        size="small"
        type="text"
        icon={
          playing ? (
            <Square className="h-3.5 w-3.5" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )
        }
        loading={loading && !playing}
        disabled={disabled}
        onClick={handleClick}
        aria-label="Preview voice"
        className={className}
      >
        {playing ? "Stop" : "Preview"}
      </Button>
    </Tooltip>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Common/__tests__/VoicePreviewButton.test.tsx`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/VoicePreviewButton.tsx apps/packages/ui/src/components/Common/__tests__/VoicePreviewButton.test.tsx
git commit -m "feat(tts): add VoicePreviewButton with synthesize-and-play"
```

---

## Task 3: TtsStickyActionBar Component

The sticky bottom bar with Play, Stop, Download, status dot, and gear toggle.

**Files:**
- Create: `apps/packages/ui/src/components/Option/Speech/TtsStickyActionBar.tsx`
- Create: `apps/packages/ui/src/components/Option/Speech/__tests__/TtsStickyActionBar.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Option/Speech/__tests__/TtsStickyActionBar.test.tsx
import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TtsStickyActionBar } from "../TtsStickyActionBar"

// Minimal antd/i18n mocks — adjust if vitest.setup.ts already handles this
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

const defaultProps = {
  onPlay: vi.fn(),
  onStop: vi.fn(),
  onDownloadSegment: vi.fn(),
  onDownloadAll: vi.fn(),
  onToggleInspector: vi.fn(),
  isPlayDisabled: false,
  isStopDisabled: true,
  isDownloadDisabled: true,
  playDisabledReason: null as string | null,
  stopDisabledReason: null as string | null,
  downloadDisabledReason: null as string | null,
  streamStatus: "idle" as const,
  inspectorOpen: false,
  inspectorBadge: "none" as const,
  segmentCount: 0,
  provider: "tldw"
}

describe("TtsStickyActionBar", () => {
  it("renders Play, Stop, Download buttons", () => {
    render(<TtsStickyActionBar {...defaultProps} />)
    expect(screen.getByRole("button", { name: /play/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /download/i })).toBeInTheDocument()
  })

  it("has toolbar role", () => {
    render(<TtsStickyActionBar {...defaultProps} />)
    expect(screen.getByRole("toolbar")).toBeInTheDocument()
  })

  it("calls onPlay when Play is clicked", () => {
    const onPlay = vi.fn()
    render(<TtsStickyActionBar {...defaultProps} onPlay={onPlay} />)
    fireEvent.click(screen.getByRole("button", { name: /play/i }))
    expect(onPlay).toHaveBeenCalledOnce()
  })

  it("disables Play when isPlayDisabled is true", () => {
    render(<TtsStickyActionBar {...defaultProps} isPlayDisabled />)
    expect(screen.getByRole("button", { name: /play/i })).toBeDisabled()
  })

  it("shows disabled reason text when Play is disabled", () => {
    render(
      <TtsStickyActionBar
        {...defaultProps}
        isPlayDisabled
        playDisabledReason="Enter text to enable Play."
      />
    )
    expect(screen.getByText("Enter text to enable Play.")).toBeInTheDocument()
  })

  it("calls onToggleInspector when gear button is clicked", () => {
    const onToggle = vi.fn()
    render(<TtsStickyActionBar {...defaultProps} onToggleInspector={onToggle} />)
    fireEvent.click(screen.getByRole("button", { name: /configuration/i }))
    expect(onToggle).toHaveBeenCalledOnce()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsStickyActionBar.test.tsx`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```tsx
// apps/packages/ui/src/components/Option/Speech/TtsStickyActionBar.tsx
import React from "react"
import { Button, Dropdown, Tooltip } from "antd"
import { Download, Play, Settings, Square } from "lucide-react"
import { useTranslation } from "react-i18next"

type StreamStatus = "idle" | "connecting" | "streaming" | "complete" | "error"
type BadgeType = "none" | "gray" | "amber" | "red"

type Props = {
  onPlay: () => void
  onStop: () => void
  onDownloadSegment: () => void
  onDownloadAll: () => void
  onToggleInspector: () => void
  isPlayDisabled: boolean
  isStopDisabled: boolean
  isDownloadDisabled: boolean
  playDisabledReason: string | null
  stopDisabledReason: string | null
  downloadDisabledReason: string | null
  streamStatus: StreamStatus
  inspectorOpen: boolean
  inspectorBadge: BadgeType
  segmentCount: number
  provider: string
}

const STATUS_COLORS: Record<StreamStatus, string> = {
  idle: "bg-gray-400",
  connecting: "bg-blue-400 animate-pulse",
  streaming: "bg-blue-500 animate-pulse",
  complete: "bg-green-500",
  error: "bg-red-500"
}

const BADGE_COLORS: Record<BadgeType, string> = {
  none: "",
  gray: "bg-gray-400",
  amber: "bg-amber-500",
  red: "bg-red-500"
}

export const TtsStickyActionBar: React.FC<Props> = ({
  onPlay,
  onStop,
  onDownloadSegment,
  onDownloadAll,
  isPlayDisabled,
  isStopDisabled,
  isDownloadDisabled,
  playDisabledReason,
  stopDisabledReason,
  downloadDisabledReason,
  streamStatus,
  onToggleInspector,
  inspectorOpen,
  inspectorBadge,
  segmentCount,
  provider
}) => {
  const { t } = useTranslation("playground")

  const downloadMenu = {
    items: [
      {
        key: "download-active",
        label: t("speech.downloadCurrent", "Download current segment"),
        disabled: segmentCount === 0 || provider === "browser"
      },
      {
        key: "download-all",
        label: t("speech.downloadAll", "Download all segments"),
        disabled: segmentCount <= 1 || provider === "browser"
      }
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === "download-active") onDownloadSegment()
      if (key === "download-all") onDownloadAll()
    }
  }

  const activeReason = isPlayDisabled
    ? playDisabledReason
    : isStopDisabled
      ? stopDisabledReason
      : null

  return (
    <div
      role="toolbar"
      aria-label="Playback controls"
      className="sticky bottom-0 z-20 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-surface/85"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Tooltip title={playDisabledReason}>
          <Button
            type="primary"
            icon={<Play className="h-4 w-4" />}
            disabled={isPlayDisabled}
            onClick={onPlay}
            aria-label="Play"
          >
            {t("tts.play", "Play")}
          </Button>
        </Tooltip>

        <Tooltip title={stopDisabledReason}>
          <Button
            icon={<Square className="h-4 w-4" />}
            disabled={isStopDisabled}
            onClick={onStop}
            aria-label="Stop"
          >
            {t("tts.stop", "Stop")}
          </Button>
        </Tooltip>

        <Tooltip title={downloadDisabledReason}>
          <Dropdown menu={downloadMenu} disabled={isDownloadDisabled}>
            <Button
              icon={<Download className="h-4 w-4" />}
              disabled={isDownloadDisabled}
              aria-label="Download"
            >
              {t("tts.download", "Download")}
            </Button>
          </Dropdown>
        </Tooltip>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${STATUS_COLORS[streamStatus]}`}
            aria-hidden="true"
          />
          <span className="text-xs text-text-subtle" aria-live="polite">
            {streamStatus === "idle" ? "" : streamStatus}
          </span>
        </div>

        <div className="relative">
          <Button
            type="text"
            icon={<Settings className="h-4 w-4" />}
            onClick={onToggleInspector}
            aria-label="Toggle configuration panel"
            aria-expanded={inspectorOpen}
          />
          {inspectorBadge !== "none" && !inspectorOpen && (
            <span
              className={`absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full ${BADGE_COLORS[inspectorBadge]}`}
            />
          )}
        </div>
      </div>

      {activeReason && (
        <div className="mt-1 text-xs text-text-subtle">{activeReason}</div>
      )}
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsStickyActionBar.test.tsx`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Speech/TtsStickyActionBar.tsx apps/packages/ui/src/components/Option/Speech/__tests__/TtsStickyActionBar.test.tsx
git commit -m "feat(tts): add TtsStickyActionBar with Play/Stop/Download and status"
```

---

## Task 4: TtsProviderStrip Component

Compact horizontal summary replacing the verbose TtsProviderPanel in Zone 1.

**Files:**
- Create: `apps/packages/ui/src/components/Option/Speech/TtsProviderStrip.tsx`
- Create: `apps/packages/ui/src/components/Option/Speech/__tests__/TtsProviderStrip.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Option/Speech/__tests__/TtsProviderStrip.test.tsx
import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TtsProviderStrip } from "../TtsProviderStrip"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

const defaultProps = {
  provider: "tldw",
  model: "kokoro",
  voice: "af_heart",
  format: "mp3",
  speed: 1.0,
  presetValue: "balanced" as const,
  onPresetChange: vi.fn(),
  onLabelClick: vi.fn(),
  onGearClick: vi.fn()
}

describe("TtsProviderStrip", () => {
  it("renders provider config summary as tags", () => {
    render(<TtsProviderStrip {...defaultProps} />)
    expect(screen.getByText("kokoro")).toBeInTheDocument()
    expect(screen.getByText("af_heart")).toBeInTheDocument()
    expect(screen.getByText("mp3")).toBeInTheDocument()
  })

  it("calls onLabelClick with field name when a tag is clicked", () => {
    const onLabelClick = vi.fn()
    render(<TtsProviderStrip {...defaultProps} onLabelClick={onLabelClick} />)
    fireEvent.click(screen.getByText("kokoro"))
    expect(onLabelClick).toHaveBeenCalledWith("voice", "model")
  })

  it("simplifies display for browser provider", () => {
    render(<TtsProviderStrip {...defaultProps} provider="browser" model="" format="" />)
    expect(screen.getByText(/browser/i)).toBeInTheDocument()
    expect(screen.queryByText("mp3")).not.toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsProviderStrip.test.tsx`
Expected: FAIL

**Step 3: Write minimal implementation**

```tsx
// apps/packages/ui/src/components/Option/Speech/TtsProviderStrip.tsx
import React from "react"
import { Button, Segmented, Tag, Tooltip } from "antd"
import { Settings, Volume2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { TtsPresetKey } from "@/hooks/useTtsPlayground"

type Props = {
  provider: string
  model: string
  voice: string
  format: string
  speed: number
  presetValue: TtsPresetKey
  onPresetChange: (preset: TtsPresetKey) => void
  onLabelClick: (tab: "voice" | "output" | "advanced", field?: string) => void
  onGearClick: () => void
}

const PRESET_TOOLTIPS: Record<string, string> = {
  fast: "Streaming on, mp3, punctuation split, 1.2x",
  balanced: "No streaming, mp3, punctuation split, 1.0x",
  quality: "No streaming, wav, paragraph split, 0.9x"
}

export const TtsProviderStrip: React.FC<Props> = ({
  provider,
  model,
  voice,
  format,
  speed,
  presetValue,
  onPresetChange,
  onLabelClick,
  onGearClick
}) => {
  const { t } = useTranslation("playground")

  if (provider === "browser") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Volume2 className="h-4 w-4 text-text-subtle" />
        <Tag className="cursor-pointer" onClick={() => onLabelClick("voice", "voice")}>
          Browser TTS
        </Tag>
        {voice && (
          <Tag className="cursor-pointer" onClick={() => onLabelClick("voice", "voice")}>
            {voice}
          </Tag>
        )}
        <div className="flex-1" />
        <Button
          type="text"
          size="small"
          icon={<Settings className="h-3.5 w-3.5" />}
          onClick={onGearClick}
          aria-label="Open configuration"
        />
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Volume2 className="h-4 w-4 text-text-subtle" />
      {model && (
        <Tooltip title={`Model: ${model}`}>
          <Tag className="cursor-pointer" onClick={() => onLabelClick("voice", "model")}>
            {model}
          </Tag>
        </Tooltip>
      )}
      {voice && (
        <Tooltip title={`Voice: ${voice}`}>
          <Tag className="cursor-pointer" onClick={() => onLabelClick("voice", "voice")}>
            {voice}
          </Tag>
        </Tooltip>
      )}
      {format && (
        <Tooltip title={`Format: ${format}`}>
          <Tag className="cursor-pointer" onClick={() => onLabelClick("output", "format")}>
            {format}
          </Tag>
        </Tooltip>
      )}
      {typeof speed === "number" && speed !== 1 && (
        <Tag className="cursor-pointer" onClick={() => onLabelClick("output", "speed")}>
          {speed.toFixed(1)}x
        </Tag>
      )}

      <div className="flex-1" />

      <Segmented
        size="small"
        value={presetValue}
        onChange={(value) => onPresetChange(value as TtsPresetKey)}
        options={[
          { label: <Tooltip title={PRESET_TOOLTIPS.fast}>Fast</Tooltip>, value: "fast" },
          { label: <Tooltip title={PRESET_TOOLTIPS.balanced}>Balanced</Tooltip>, value: "balanced" },
          { label: <Tooltip title={PRESET_TOOLTIPS.quality}>Quality</Tooltip>, value: "quality" }
        ]}
      />

      <Button
        type="text"
        size="small"
        icon={<Settings className="h-3.5 w-3.5" />}
        onClick={onGearClick}
        aria-label="Open configuration"
      />
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsProviderStrip.test.tsx`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Speech/TtsProviderStrip.tsx apps/packages/ui/src/components/Option/Speech/__tests__/TtsProviderStrip.test.tsx
git commit -m "feat(tts): add TtsProviderStrip compact config summary"
```

---

## Task 5: Inspector Panel Tabs — TtsVoiceTab, TtsOutputTab, TtsAdvancedTab

Three tab content components. These are primarily JSX extraction from SpeechPlaygroundPage — the logic already exists. Testing focuses on rendering and interaction rather than business logic.

**Files:**
- Create: `apps/packages/ui/src/components/Option/Speech/TtsVoiceTab.tsx`
- Create: `apps/packages/ui/src/components/Option/Speech/TtsOutputTab.tsx`
- Create: `apps/packages/ui/src/components/Option/Speech/TtsAdvancedTab.tsx`
- Create: `apps/packages/ui/src/components/Option/Speech/__tests__/TtsInspectorTabs.test.tsx`

**Step 1: Write failing tests for all three tabs**

```tsx
// apps/packages/ui/src/components/Option/Speech/__tests__/TtsInspectorTabs.test.tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TtsVoiceTab } from "../TtsVoiceTab"
import { TtsOutputTab } from "../TtsOutputTab"
import { TtsAdvancedTab } from "../TtsAdvancedTab"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

describe("TtsVoiceTab", () => {
  it("renders provider, model, and voice selectors", () => {
    render(
      <TtsVoiceTab
        provider="tldw"
        model="kokoro"
        voice="af_heart"
        onProviderChange={vi.fn()}
        onModelChange={vi.fn()}
        onVoiceChange={vi.fn()}
        modelOptions={[{ label: "kokoro", value: "kokoro" }]}
        voiceOptions={[{ label: "af_heart", value: "af_heart" }]}
        focusField={null}
        onFocusHandled={vi.fn()}
      />
    )
    expect(screen.getByText("Provider")).toBeInTheDocument()
    expect(screen.getByText("Model")).toBeInTheDocument()
    expect(screen.getByText("Voice")).toBeInTheDocument()
  })
})

describe("TtsOutputTab", () => {
  it("renders format, speed, and splitting controls", () => {
    render(
      <TtsOutputTab
        format="mp3"
        synthesisSpeed={1}
        playbackSpeed={1}
        responseSplitting="punctuation"
        streaming={false}
        canStream={true}
        streamFormatSupported={true}
        onFormatChange={vi.fn()}
        onSynthesisSpeedChange={vi.fn()}
        onPlaybackSpeedChange={vi.fn()}
        onResponseSplittingChange={vi.fn()}
        onStreamingChange={vi.fn()}
        formatOptions={[{ label: "mp3", value: "mp3" }]}
        normalize={true}
        onNormalizeChange={vi.fn()}
        normalizeUnits={false}
        onNormalizeUnitsChange={vi.fn()}
        normalizeUrls={true}
        onNormalizeUrlsChange={vi.fn()}
        normalizeEmails={true}
        onNormalizeEmailsChange={vi.fn()}
        normalizePhones={true}
        onNormalizePhonesChange={vi.fn()}
        normalizePlurals={true}
        onNormalizePluralsChange={vi.fn()}
        focusField={null}
        onFocusHandled={vi.fn()}
      />
    )
    expect(screen.getByText("Format")).toBeInTheDocument()
    expect(screen.getByText("Synthesis Speed")).toBeInTheDocument()
    expect(screen.getByText("Playback Speed")).toBeInTheDocument()
    expect(screen.getByText("Response Splitting")).toBeInTheDocument()
  })
})

describe("TtsAdvancedTab", () => {
  it("renders draft editor and SSML toggles", () => {
    render(
      <TtsAdvancedTab
        useDraftEditor={false}
        onDraftEditorChange={vi.fn()}
        useTtsJob={false}
        onTtsJobChange={vi.fn()}
        ssmlEnabled={false}
        onSsmlChange={vi.fn()}
        removeReasoning={true}
        onRemoveReasoningChange={vi.fn()}
        isTldw={true}
        onOpenVoiceCloning={vi.fn()}
      />
    )
    expect(screen.getByText("Draft editor")).toBeInTheDocument()
    expect(screen.getByText(/SSML/)).toBeInTheDocument()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsInspectorTabs.test.tsx`
Expected: FAIL — modules not found

**Step 3: Write implementations**

Each tab is a presentational component receiving values and callbacks as props. The full JSX is extracted from `SpeechPlaygroundPage.tsx` lines ~2113-2200+ (TTS card content). I'll show the structure — implementation fills in the existing Ant Design form fields.

```tsx
// apps/packages/ui/src/components/Option/Speech/TtsVoiceTab.tsx
import React, { useEffect, useRef } from "react"
import { Select, Slider } from "antd"
import { useTranslation } from "react-i18next"
import { VoicePreviewButton } from "@/components/Common/VoicePreviewButton"
import { TTS_PROVIDER_OPTIONS } from "@/services/tts-providers"

type Props = {
  provider: string
  model: string
  voice: string
  onProviderChange: (value: string) => void
  onModelChange: (value: string) => void
  onVoiceChange: (value: string) => void
  modelOptions: { label: string; value: string }[]
  voiceOptions: { label: string; value: string }[]
  // Optional fields shown conditionally
  language?: string
  onLanguageChange?: (value: string) => void
  languageOptions?: { label: string; value: string }[]
  emotion?: string
  onEmotionChange?: (value: string) => void
  emotionIntensity?: number
  onEmotionIntensityChange?: (value: number) => void
  supportsEmotion?: boolean
  // Voice roles
  useVoiceRoles?: boolean
  onVoiceRolesChange?: (value: boolean) => void
  voiceRolesContent?: React.ReactNode
  // Focus management
  focusField: string | null
  onFocusHandled: () => void
}

export const TtsVoiceTab: React.FC<Props> = (props) => {
  const { t } = useTranslation("playground")
  const modelRef = useRef<any>(null)
  const voiceRef = useRef<any>(null)

  useEffect(() => {
    if (!props.focusField) return
    const timer = setTimeout(() => {
      if (props.focusField === "model") modelRef.current?.focus?.()
      if (props.focusField === "voice") voiceRef.current?.focus?.()
      props.onFocusHandled()
    }, 100)
    return () => clearTimeout(timer)
  }, [props.focusField, props.onFocusHandled])

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm text-text mb-1 block">Provider</label>
        <Select
          className="w-full"
          value={props.provider}
          onChange={props.onProviderChange}
          options={TTS_PROVIDER_OPTIONS.map(({ label, value }) => ({ label, value }))}
        />
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Model</label>
        <Select
          ref={modelRef}
          className="w-full"
          value={props.model}
          onChange={props.onModelChange}
          options={props.modelOptions}
          showSearch
          optionFilterProp="label"
        />
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Voice</label>
        <Select
          ref={voiceRef}
          className="w-full"
          value={props.voice}
          onChange={props.onVoiceChange}
          options={props.voiceOptions}
          showSearch
          optionFilterProp="label"
        />
        <div className="mt-1">
          <VoicePreviewButton model={props.model} voice={props.voice} provider={props.provider} />
        </div>
      </div>
      {props.languageOptions && props.languageOptions.length > 0 && (
        <div>
          <label className="text-sm text-text mb-1 block">Language</label>
          <Select
            className="w-full"
            value={props.language}
            onChange={props.onLanguageChange}
            options={props.languageOptions}
            allowClear
            placeholder="Auto"
          />
        </div>
      )}
      {props.supportsEmotion && (
        <>
          <div>
            <label className="text-sm text-text mb-1 block">Emotion preset</label>
            <Select
              className="w-full"
              value={props.emotion}
              onChange={props.onEmotionChange}
              allowClear
              placeholder="Default"
              options={[
                { label: "Neutral", value: "neutral" },
                { label: "Calm", value: "calm" },
                { label: "Energetic", value: "energetic" },
                { label: "Happy", value: "happy" },
                { label: "Sad", value: "sad" },
                { label: "Angry", value: "angry" }
              ]}
            />
          </div>
          <div>
            <label className="text-sm text-text mb-1 block">Emotion intensity</label>
            <Slider
              min={0.1}
              max={2}
              step={0.1}
              value={props.emotionIntensity ?? 1}
              onChange={props.onEmotionIntensityChange}
            />
          </div>
        </>
      )}
    </div>
  )
}
```

```tsx
// apps/packages/ui/src/components/Option/Speech/TtsOutputTab.tsx
import React, { useEffect, useRef } from "react"
import { Select, Slider, Switch, Tooltip } from "antd"
import { useTranslation } from "react-i18next"

type Props = {
  format: string
  synthesisSpeed: number
  playbackSpeed: number
  responseSplitting: string
  streaming: boolean
  canStream: boolean
  streamFormatSupported: boolean
  onFormatChange: (value: string) => void
  onSynthesisSpeedChange: (value: number) => void
  onPlaybackSpeedChange: (value: number) => void
  onResponseSplittingChange: (value: string) => void
  onStreamingChange: (value: boolean) => void
  formatOptions: { label: string; value: string }[]
  normalize: boolean
  onNormalizeChange: (value: boolean) => void
  normalizeUnits: boolean
  onNormalizeUnitsChange: (value: boolean) => void
  normalizeUrls: boolean
  onNormalizeUrlsChange: (value: boolean) => void
  normalizeEmails: boolean
  onNormalizeEmailsChange: (value: boolean) => void
  normalizePhones: boolean
  onNormalizePhonesChange: (value: boolean) => void
  normalizePlurals: boolean
  onNormalizePluralsChange: (value: boolean) => void
  focusField: string | null
  onFocusHandled: () => void
}

export const TtsOutputTab: React.FC<Props> = (props) => {
  const { t } = useTranslation("playground")
  const formatRef = useRef<any>(null)

  useEffect(() => {
    if (!props.focusField) return
    const timer = setTimeout(() => {
      if (props.focusField === "format") formatRef.current?.focus?.()
      props.onFocusHandled()
    }, 100)
    return () => clearTimeout(timer)
  }, [props.focusField, props.onFocusHandled])

  const streamingDisabledReason = !props.canStream
    ? "Provider does not support streaming"
    : !props.streamFormatSupported
      ? `Format does not support streaming`
      : null

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm text-text mb-1 block">Format</label>
        <Select
          ref={formatRef}
          className="w-full"
          value={props.format}
          onChange={props.onFormatChange}
          options={props.formatOptions}
        />
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Synthesis Speed</label>
        <div className="flex items-center gap-3">
          <Slider
            className="flex-1"
            min={0.25}
            max={4}
            step={0.05}
            value={props.synthesisSpeed}
            onChange={props.onSynthesisSpeedChange}
          />
          <span className="text-xs text-text-subtle w-10 text-right">
            {props.synthesisSpeed.toFixed(2)}
          </span>
        </div>
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Playback Speed</label>
        <div className="flex items-center gap-3">
          <Slider
            className="flex-1"
            min={0.25}
            max={2}
            step={0.05}
            value={props.playbackSpeed}
            onChange={props.onPlaybackSpeedChange}
          />
          <span className="text-xs text-text-subtle w-10 text-right">
            {props.playbackSpeed.toFixed(2)}
          </span>
        </div>
      </div>
      <div>
        <label className="text-sm text-text mb-1 block">Response Splitting</label>
        <Select
          className="w-full"
          value={props.responseSplitting}
          onChange={props.onResponseSplittingChange}
          options={[
            { label: "None", value: "none" },
            { label: "Punctuation", value: "punctuation" },
            { label: "Paragraph", value: "paragraph" }
          ]}
        />
      </div>
      <div className="flex items-center justify-between">
        <div>
          <label className="text-sm text-text">Stream audio (WebSocket)</label>
          <div className="text-xs text-text-subtle">Low-latency playback while audio generates.</div>
        </div>
        <Tooltip title={streamingDisabledReason}>
          <Switch
            checked={props.streaming}
            onChange={props.onStreamingChange}
            disabled={Boolean(streamingDisabledReason)}
          />
        </Tooltip>
      </div>
      <div className="rounded-md border border-border p-3 space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm text-text">Smart normalization</label>
          <Switch checked={props.normalize} onChange={props.onNormalizeChange} />
        </div>
        <div className="text-xs text-text-subtle">
          Expands units, URLs, emails, and phone numbers to improve pronunciation.
        </div>
        {props.normalize && (
          <div className="grid gap-2 sm:grid-cols-2">
            {[
              { label: "Units", checked: props.normalizeUnits, onChange: props.onNormalizeUnitsChange },
              { label: "URLs", checked: props.normalizeUrls, onChange: props.onNormalizeUrlsChange },
              { label: "Emails", checked: props.normalizeEmails, onChange: props.onNormalizeEmailsChange },
              { label: "Phone", checked: props.normalizePhones, onChange: props.onNormalizePhonesChange },
              { label: "Pluralization", checked: props.normalizePlurals, onChange: props.onNormalizePluralsChange }
            ].map(({ label, checked, onChange }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs text-text-subtle">{label}</span>
                <Switch size="small" checked={checked} onChange={onChange} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

```tsx
// apps/packages/ui/src/components/Option/Speech/TtsAdvancedTab.tsx
import React from "react"
import { Button, Switch, Typography } from "antd"
import { useTranslation } from "react-i18next"
import { TTS_PRESETS } from "@/hooks/useTtsPlayground"

const { Text } = Typography

type Props = {
  useDraftEditor: boolean
  onDraftEditorChange: (value: boolean) => void
  useTtsJob: boolean
  onTtsJobChange: (value: boolean) => void
  ssmlEnabled: boolean
  onSsmlChange: (value: boolean) => void
  removeReasoning: boolean
  onRemoveReasoningChange: (value: boolean) => void
  isTldw: boolean
  onOpenVoiceCloning: () => void
}

const TOGGLE_ITEMS = (props: Props) => [
  {
    label: "Draft editor",
    description: "Outline + transcript mode for longform content.",
    checked: props.useDraftEditor,
    onChange: props.onDraftEditorChange
  },
  {
    label: "Use TTS Job",
    description: "Server-side job queue for long content. Progress tracked live.",
    checked: props.useTtsJob,
    onChange: props.onTtsJobChange,
    hidden: !props.isTldw
  },
  {
    label: "Enable SSML",
    description: "Speech Synthesis Markup Language tags.",
    checked: props.ssmlEnabled,
    onChange: props.onSsmlChange
  },
  {
    label: "Remove <think> tags",
    description: "Strip reasoning blocks before speaking.",
    checked: props.removeReasoning,
    onChange: props.onRemoveReasoningChange
  }
]

export const TtsAdvancedTab: React.FC<Props> = (props) => {
  const { t } = useTranslation("playground")

  return (
    <div className="space-y-4">
      {TOGGLE_ITEMS(props)
        .filter((item) => !item.hidden)
        .map(({ label, description, checked, onChange }) => (
          <div key={label} className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm text-text">{label}</div>
              <div className="text-xs text-text-subtle">{description}</div>
            </div>
            <Switch checked={checked} onChange={onChange} />
          </div>
        ))}

      {props.isTldw && (
        <div className="border-t border-border pt-3">
          <div className="text-sm text-text mb-2">Voice Cloning</div>
          <Button size="small" onClick={props.onOpenVoiceCloning}>
            Manage custom voices
          </Button>
        </div>
      )}

      <div className="border-t border-border pt-3">
        <div className="text-sm text-text mb-2">Preset Reference</div>
        <div className="space-y-1">
          {Object.entries(TTS_PRESETS).map(([key, preset]) => (
            <div key={key} className="flex items-baseline gap-2">
              <Text strong className="text-xs capitalize w-16">
                {key}:
              </Text>
              <Text className="text-xs text-text-subtle">
                {preset.streaming ? "stream" : "no stream"}, {preset.responseFormat},{" "}
                {preset.splitBy}, {preset.speed}x
              </Text>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsInspectorTabs.test.tsx`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Speech/TtsVoiceTab.tsx apps/packages/ui/src/components/Option/Speech/TtsOutputTab.tsx apps/packages/ui/src/components/Option/Speech/TtsAdvancedTab.tsx apps/packages/ui/src/components/Option/Speech/__tests__/TtsInspectorTabs.test.tsx
git commit -m "feat(tts): add Voice, Output, and Advanced inspector tab components"
```

---

## Task 6: TtsInspectorPanel Container

Wraps the three tabs in Ant Design Drawer (tablet/mobile) or inline panel (desktop).

**Files:**
- Create: `apps/packages/ui/src/components/Option/Speech/TtsInspectorPanel.tsx`
- Create: `apps/packages/ui/src/components/Option/Speech/__tests__/TtsInspectorPanel.test.tsx`

**Step 1: Write the failing test**

```tsx
// apps/packages/ui/src/components/Option/Speech/__tests__/TtsInspectorPanel.test.tsx
import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TtsInspectorPanel } from "../TtsInspectorPanel"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

describe("TtsInspectorPanel", () => {
  const voiceTab = <div data-testid="voice-tab">Voice content</div>
  const outputTab = <div data-testid="output-tab">Output content</div>
  const advancedTab = <div data-testid="advanced-tab">Advanced content</div>

  it("renders with Voice tab active by default", () => {
    render(
      <TtsInspectorPanel
        open
        activeTab="voice"
        onTabChange={vi.fn()}
        onClose={vi.fn()}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    expect(screen.getByTestId("voice-tab")).toBeInTheDocument()
  })

  it("switches to Output tab on click", () => {
    const onTabChange = vi.fn()
    render(
      <TtsInspectorPanel
        open
        activeTab="voice"
        onTabChange={onTabChange}
        onClose={vi.fn()}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    fireEvent.click(screen.getByText("Output"))
    expect(onTabChange).toHaveBeenCalledWith("output")
  })

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn()
    render(
      <TtsInspectorPanel
        open
        activeTab="voice"
        onTabChange={vi.fn()}
        onClose={onClose}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: /close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it("does not render content when closed", () => {
    render(
      <TtsInspectorPanel
        open={false}
        activeTab="voice"
        onTabChange={vi.fn()}
        onClose={vi.fn()}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    expect(screen.queryByTestId("voice-tab")).not.toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsInspectorPanel.test.tsx`
Expected: FAIL

**Step 3: Write implementation**

```tsx
// apps/packages/ui/src/components/Option/Speech/TtsInspectorPanel.tsx
import React from "react"
import { Button, Drawer, Segmented } from "antd"
import { X } from "lucide-react"
import { useTranslation } from "react-i18next"

type InspectorTab = "voice" | "output" | "advanced"

type Props = {
  open: boolean
  activeTab: InspectorTab
  onTabChange: (tab: InspectorTab) => void
  onClose: () => void
  voiceTab: React.ReactNode
  outputTab: React.ReactNode
  advancedTab: React.ReactNode
  useDrawer?: boolean
}

const TAB_OPTIONS: { label: string; value: InspectorTab }[] = [
  { label: "Voice", value: "voice" },
  { label: "Output", value: "output" },
  { label: "Advanced", value: "advanced" }
]

const PanelContent: React.FC<{
  activeTab: InspectorTab
  onTabChange: (tab: InspectorTab) => void
  onClose: () => void
  voiceTab: React.ReactNode
  outputTab: React.ReactNode
  advancedTab: React.ReactNode
}> = ({ activeTab, onTabChange, onClose, voiceTab, outputTab, advancedTab }) => {
  const { t } = useTranslation("playground")

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-medium text-text">
          {t("tts.configuration", "Configuration")}
        </span>
        <Button
          type="text"
          size="small"
          icon={<X className="h-4 w-4" />}
          onClick={onClose}
          aria-label="Close configuration panel"
        />
      </div>
      <div className="px-4 py-3 border-b border-border">
        <Segmented
          block
          size="small"
          value={activeTab}
          onChange={(value) => onTabChange(value as InspectorTab)}
          options={TAB_OPTIONS}
        />
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {activeTab === "voice" && voiceTab}
        {activeTab === "output" && outputTab}
        {activeTab === "advanced" && advancedTab}
      </div>
    </div>
  )
}

export const TtsInspectorPanel: React.FC<Props> = ({
  open,
  activeTab,
  onTabChange,
  onClose,
  voiceTab,
  outputTab,
  advancedTab,
  useDrawer = false
}) => {
  if (useDrawer) {
    return (
      <Drawer
        placement="right"
        open={open}
        onClose={onClose}
        closable={false}
        styles={{ body: { padding: 0 }, wrapper: { maxWidth: 360 } }}
        width={360}
      >
        <PanelContent
          activeTab={activeTab}
          onTabChange={onTabChange}
          onClose={onClose}
          voiceTab={voiceTab}
          outputTab={outputTab}
          advancedTab={advancedTab}
        />
      </Drawer>
    )
  }

  if (!open) return null

  return (
    <aside
      role="complementary"
      aria-label="TTS Configuration"
      className="w-[320px] min-w-[300px] max-w-[360px] border-l border-border bg-surface"
    >
      <PanelContent
        activeTab={activeTab}
        onTabChange={onTabChange}
        onClose={onClose}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    </aside>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/__tests__/TtsInspectorPanel.test.tsx`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Speech/TtsInspectorPanel.tsx apps/packages/ui/src/components/Option/Speech/__tests__/TtsInspectorPanel.test.tsx
git commit -m "feat(tts): add TtsInspectorPanel with tab switching and drawer mode"
```

---

## Task 7: Integrate Zone 1 + Zone 2 into SpeechPlaygroundPage

This is the main refactor — restructuring the Listen tab's JSX in `SpeechPlaygroundPage.tsx` to use the new components. No business logic changes.

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`

**Step 1: Add inspector state and useDrawer hook**

At the top of the component (after existing state declarations around line ~204), add:

```tsx
// Inspector panel state
const [inspectorOpen, setInspectorOpen] = useStorage<boolean>("ttsInspectorOpen", false)
const [inspectorTab, setInspectorTab] = useStorage<"voice" | "output" | "advanced">("ttsInspectorTab", "voice")
const [inspectorFocusField, setInspectorFocusField] = React.useState<string | null>(null)

const openInspectorAt = React.useCallback(
  (tab: "voice" | "output" | "advanced", field?: string) => {
    setInspectorOpen(true)
    setInspectorTab(tab)
    if (field) setInspectorFocusField(field)
  },
  [setInspectorOpen, setInspectorTab]
)

// Responsive: use drawer below 1024px
const [useDrawer, setUseDrawer] = React.useState(false)
React.useEffect(() => {
  const mq = window.matchMedia("(max-width: 1023px)")
  const handler = (e: MediaQueryListEvent | MediaQueryList) => setUseDrawer(e.matches)
  handler(mq)
  mq.addEventListener("change", handler)
  return () => mq.removeEventListener("change", handler)
}, [])
```

**Step 2: Replace the TTS card content in the `mode !== "speak"` block**

Find the block starting at approximately line 2113 (`{mode !== "speak" && (`). Replace the Card content with the two-zone layout:

```tsx
{mode !== "speak" && (
  <Card className="h-full overflow-hidden">
    <div className="flex h-full">
      {/* Zone 1: Workspace */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <TtsProviderStrip
            provider={provider}
            model={tldwModel || ttsSettings?.tldwTtsModel || ""}
            voice={tldwVoice || ttsSettings?.tldwTtsVoice || ""}
            format={tldwFormat || ttsSettings?.tldwTtsResponseFormat || "mp3"}
            speed={ttsSettings?.tldwTtsSpeed ?? 1}
            presetValue={ttsPreset as TtsPresetKey}
            onPresetChange={(preset) => void applyTtsPreset(preset)}
            onLabelClick={openInspectorAt}
            onGearClick={() => setInspectorOpen((prev) => !prev)}
          />

          {/* Text input area — keep existing textarea/draft editor JSX */}
          {/* ... existing text input code ... */}

          {/* Character progress bar — new */}
          <CharacterProgressBar
            count={previewCharCount}
            max={TTS_CHAR_LIMIT}
            warnAt={TTS_CHAR_WARNING}
            dangerAt={TTS_CHAR_LIMIT - 2000}
          />

          {/* Stats line */}
          <div className="text-xs text-text-subtle">
            {previewWordCount} words · {previewSegments.length} segments ({responseSplitting}) · Est. ~{formatDuration(estimatedDurationSeconds)}
          </div>

          {/* Streaming/Job status — existing code, relocated here */}
          {/* Waveform — existing WaveformCanvas */}
          {/* Segment navigation — updated with text previews */}
        </div>

        {/* Sticky action bar */}
        <TtsStickyActionBar
          onPlay={handlePlay}
          onStop={handleStop}
          onDownloadSegment={handleDownloadSegment}
          onDownloadAll={handleDownloadAll}
          onToggleInspector={() => setInspectorOpen((prev) => !prev)}
          isPlayDisabled={isPlayDisabled}
          isStopDisabled={!canStop}
          isDownloadDisabled={isDownloadDisabled}
          playDisabledReason={playDisabledReason}
          stopDisabledReason={stopDisabledReason as string | null}
          downloadDisabledReason={downloadDisabledReason}
          streamStatus={streamStatus}
          inspectorOpen={inspectorOpen ?? false}
          inspectorBadge={inspectorBadge}
          segmentCount={segments.length}
          provider={provider}
        />
      </div>

      {/* Zone 2: Inspector */}
      <TtsInspectorPanel
        open={inspectorOpen ?? false}
        activeTab={inspectorTab ?? "voice"}
        onTabChange={setInspectorTab}
        onClose={() => setInspectorOpen(false)}
        useDrawer={useDrawer}
        voiceTab={<TtsVoiceTab {/* ... props from existing state ... */} />}
        outputTab={<TtsOutputTab {/* ... props from existing state ... */} />}
        advancedTab={<TtsAdvancedTab {/* ... props from existing state ... */} />}
      />
    </div>
  </Card>
)}
```

**Step 3: Update segment buttons to show text previews**

Find the segment navigation JSX and update buttons:

```tsx
{segments.length > 1 && (
  <div className="flex gap-1.5 overflow-x-auto pb-1" role="tablist">
    {segments.map((seg, idx) => {
      const preview = seg.text
        ? seg.text.slice(0, 25) + (seg.text.length > 25 ? "..." : "")
        : `Segment ${idx + 1}`
      return (
        <Button
          key={seg.id}
          role="tab"
          aria-selected={activeSegmentIndex === idx}
          size="small"
          type={activeSegmentIndex === idx ? "primary" : "default"}
          onClick={() => handleSegmentSelect(idx)}
        >
          {idx + 1}: "{preview}"
        </Button>
      )
    })}
  </div>
)}
```

**Step 4: Remove relocated JSX**

Delete the following sections that have been moved to Zone 2 tabs:
- The inline `TtsProviderPanel` call (verbose provider card)
- The "Advanced controls" `<Collapse>` section
- The "Voice cloning & custom voices" `<Collapse>` section
- The inline Play/Stop/Download buttons (now in sticky bar)
- The Draft editor toggle from next to the text input

**Step 5: Add imports at top of file**

```tsx
import { CharacterProgressBar } from "@/components/Common/CharacterProgressBar"
import { TtsProviderStrip } from "@/components/Option/Speech/TtsProviderStrip"
import { TtsStickyActionBar } from "@/components/Option/Speech/TtsStickyActionBar"
import { TtsInspectorPanel } from "@/components/Option/Speech/TtsInspectorPanel"
import { TtsVoiceTab } from "@/components/Option/Speech/TtsVoiceTab"
import { TtsOutputTab } from "@/components/Option/Speech/TtsOutputTab"
import { TtsAdvancedTab } from "@/components/Option/Speech/TtsAdvancedTab"
```

**Step 6: Run existing tests to verify no regressions**

Run: `cd apps && bun run --cwd packages/ui vitest run src/components/Option/Speech/`
Expected: All existing tests PASS

**Step 7: Run E2E smoke test if available**

Run: `cd apps/extension && bun run test:e2e -- --grep "tts-playground" --headed`
Expected: Existing TTS E2E tests pass (or skip if server not available)

**Step 8: Commit**

```bash
git add apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx
git commit -m "refactor(tts): restructure Listen tab into two-zone layout with sticky action bar

Replaces single vertical scroll with Zone 1 (workspace) and Zone 2
(inspector panel). Play/Stop/Download now always visible in sticky bar.
Configuration moved to tabbed inspector. No business logic changes."
```

---

## Task 8: Add keyboard shortcuts

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`

**Step 1: Add keyboard handler**

Inside the component, after the inspector state declarations:

```tsx
React.useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    const mod = e.metaKey || e.ctrlKey
    // Ctrl/Cmd + Enter: Play or Stop
    if (mod && e.key === "Enter" && mode !== "speak") {
      e.preventDefault()
      if (isStreamingActive || isTtsJobRunning || segments.length > 0) {
        handleStop()
      } else if (!isPlayDisabled) {
        void handlePlay()
      }
    }
    // Escape: Stop
    if (e.key === "Escape") {
      handleStop()
    }
    // Ctrl/Cmd + .: Toggle inspector
    if (mod && e.key === ".") {
      e.preventDefault()
      setInspectorOpen((prev) => !prev)
    }
  }
  document.addEventListener("keydown", handler)
  return () => document.removeEventListener("keydown", handler)
}, [handlePlay, handleStop, isPlayDisabled, isStreamingActive, isTtsJobRunning, mode, segments.length, setInspectorOpen])
```

**Step 2: Add shortcut hints to button tooltips**

Update TtsStickyActionBar to accept optional shortcut labels and display them in tooltips. This is a minor prop addition.

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx
git commit -m "feat(tts): add keyboard shortcuts (Ctrl+Enter, Escape, Ctrl+.)"
```

---

## Task 9: Final verification and cleanup

**Step 1: Run full test suite**

Run: `cd apps && bun run --cwd packages/ui vitest run`
Expected: All tests PASS

**Step 2: Run TypeScript type check**

Run: `cd apps && bun run --cwd packages/ui tsc --noEmit`
Expected: No errors

**Step 3: Visual verification**

Run: `cd apps/tldw-frontend && bun run dev -- -p 8080`
Then open `http://localhost:8080/tts` and verify:
- [ ] Provider strip shows current config as clickable tags
- [ ] Text area has character progress bar
- [ ] Play/Stop/Download are visible in sticky bar without scrolling
- [ ] Gear icon opens inspector panel on right side (desktop) or drawer (narrow viewport)
- [ ] Inspector tabs switch correctly (Voice, Output, Advanced)
- [ ] Clicking a tag in provider strip opens inspector at correct tab/field
- [ ] Voice Preview button works
- [ ] Segment buttons show text previews
- [ ] Ctrl+Enter plays, Escape stops, Ctrl+. toggles inspector
- [ ] Mobile viewport: drawer opens full-width

**Step 4: Remove dead code**

If `TtsProviderPanel.tsx` is no longer imported anywhere after the refactor, delete it. Check with:

Run: `cd apps && grep -r "TtsProviderPanel" packages/ui/src/ --include="*.tsx" --include="*.ts" -l`

If only the old import in SpeechPlaygroundPage (now removed), delete the file.

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore(tts): cleanup dead code and verify two-zone layout"
```
