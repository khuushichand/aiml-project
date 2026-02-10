import { CharGrid } from "../../engine/CharGrid";
import { richColorToCSS } from "../../engine/color-utils";
import type { SplashEffect } from "../../engine/types";

const DEFAULT_BOOT_SEQUENCE = [
  "TLDW BIOS v2.0.1 (c) 2025 tldw Project",
  "",
  "Performing POST...",
  "CPU: AI-Core x86_64 @ 4.2GHz .............. [OK]",
  "Memory test: 65536 MB ...................... [OK]",
  "GPU: NVIDIA RTX 4090 24GB VRAM ............ [OK]",
  "Storage: NVMe 2TB ......................... [OK]",
  "",
  "Detecting devices...",
  "  /dev/whisper0  - STT Engine .............. [FOUND]",
  "  /dev/chroma0   - Vector Store ............ [FOUND]",
  "  /dev/llm0      - LLM Accelerator ......... [FOUND]",
  "  /dev/tts0      - TTS Synthesizer ......... [FOUND]",
  "",
  "Loading kernel modules...",
  "  fastapi.ko ................................ loaded",
  "  rag_pipeline.ko ........................... loaded",
  "  auth_module.ko ............................ loaded",
  "  embedding_engine.ko ....................... loaded",
  "",
  "Starting services...",
  "  tldw-api     [port 8000] ................. [STARTED]",
  "  chromadb     [port 8001] ................. [STARTED]",
  "  redis-cache  [port 6379] ................. [STARTED]",
  "",
  "System ready. Welcome to TLDW.",
  "root@tldw:~# _",
];

interface BootSequenceLineInput {
  text?: string;
  style?: string;
  typeSpeed?: number;
  type_speed?: number;
  pauseAfter?: number;
  pause_after?: number;
  delayBefore?: number;
  delay_before?: number;
}

interface BootSequenceLine {
  text: string;
  style?: string;
  revealDelayMs: number;
}

export default class TerminalBoot implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private bootSequence: BootSequenceLine[] = [];
  private visibleLines = 0;
  private nextRevealAt = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.w = width;
    this.h = height;
    this.bootSequence = this.normalizeBootSequence(config?.boot_sequence);
    this.reset();
  }

  private normalizeBootSequence(input: unknown): BootSequenceLine[] {
    const sequence: Array<string | BootSequenceLineInput> = Array.isArray(input)
      ? (input as Array<string | BootSequenceLineInput>)
      : DEFAULT_BOOT_SEQUENCE;

    return sequence.map((entry) => {
      if (typeof entry === "string") {
        return { text: entry, revealDelayMs: 120 };
      }

      const text = typeof entry?.text === "string" ? entry.text : "";
      const style = typeof entry?.style === "string" ? entry.style : undefined;

      const typeSpeedRaw = entry?.typeSpeed ?? entry?.type_speed;
      const typeSpeed = typeof typeSpeedRaw === "number" && Number.isFinite(typeSpeedRaw)
        ? Math.max(typeSpeedRaw, 0)
        : 0;
      const typeDelayMs = typeSpeed > 0
        ? Math.max(40, Math.round(typeSpeed * 1000 * Math.max(text.length, 1)))
        : 120;

      const pauseAfterRaw = entry?.pauseAfter ?? entry?.pause_after;
      const pauseAfterMs = typeof pauseAfterRaw === "number" && Number.isFinite(pauseAfterRaw)
        ? Math.max(0, pauseAfterRaw > 10 ? pauseAfterRaw : pauseAfterRaw * 1000)
        : 0;

      const delayBeforeRaw = entry?.delayBefore ?? entry?.delay_before;
      const delayBeforeMs = typeof delayBeforeRaw === "number" && Number.isFinite(delayBeforeRaw)
        ? Math.max(0, delayBeforeRaw > 10 ? delayBeforeRaw : delayBeforeRaw * 1000)
        : 0;

      return {
        text,
        style,
        revealDelayMs: Math.max(40, typeDelayMs + pauseAfterMs + delayBeforeMs),
      };
    });
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    if (this.visibleLines < this.bootSequence.length && elapsed >= this.nextRevealAt) {
      const line = this.bootSequence[this.visibleLines];
      this.visibleLines++;
      this.nextRevealAt = elapsed + (line?.revealDelayMs ?? 120);
    }

    // Loop back after showing all + pause
    if (this.visibleLines >= this.bootSequence.length && elapsed > this.nextRevealAt + 3000) {
      this.visibleLines = 0;
      this.nextRevealAt = elapsed + 120;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    const maxVisible = 24;
    const startIdx = Math.max(0, this.visibleLines - maxVisible);
    const endIdx = this.visibleLines;

    let row = 0;
    for (let i = startIdx; i < endIdx && row < 24; i++) {
      const line = this.bootSequence[i];
      const lineText = line?.text ?? "";

      let color = "#aaaaaa";
      if (line?.style) {
        color = richColorToCSS(line.style);
      } else if (lineText.includes("[OK]") || lineText.includes("[STARTED]")) color = "#00ff00";
      else if (lineText.includes("[FOUND]")) color = "#00ccff";
      else if (lineText.includes("[FAIL]") || lineText.includes("[ERROR]")) color = "#ff4444";
      else if (lineText.startsWith("  ")) color = "#888888";
      else if (lineText.includes("...")) color = "#cccccc";
      else if (lineText.includes("BIOS") || lineText.includes("Welcome")) color = "#ffffff";
      else if (lineText.includes("root@")) color = "#00ff00";

      grid.writeString(0, row, lineText.slice(0, 80), color);
      row++;
    }

    // Blinking cursor on last line
    if (row > 0 && this.elapsed % 800 < 400) {
      const lastLine = this.bootSequence[Math.min(endIdx - 1, this.bootSequence.length - 1)]?.text ?? "";
      const cursorX = Math.min(lastLine.length, 79);
      grid.setCell(cursorX, row - 1, "_", "#00ff00");
    }

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.visibleLines = 0;
    this.nextRevealAt = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.bootSequence = [];
    this.grid.clear();
  }
}
