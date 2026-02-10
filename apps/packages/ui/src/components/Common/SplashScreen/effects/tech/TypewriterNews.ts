import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const NEWS_ITEMS = [
  "System boot sequence initialized successfully...",
  "Media processing engine online and operational.",
  "RAG pipeline calibration complete. Accuracy: 97.3%",
  "Whisper transcription module loaded. GPU detected.",
  "Vector store connected. 1,247,892 embeddings indexed.",
  "LLM providers configured: 16 active connections.",
  "Authentication module: multi-user JWT mode active.",
  "All systems nominal. Ready for operations.",
  "Breaking: New media batch queued for processing...",
  "Advisory: Cache hit rate at 94.2% - optimal range.",
];

export default class TypewriterNews implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private displayedLines: string[] = [];
  private currentLine = 0;
  private charIndex = 0;
  private lastCharTime = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    if (this.currentLine >= NEWS_ITEMS.length) {
      this.currentLine = 0;
      this.displayedLines = [];
    }

    const charDelay = 35;
    if (elapsed - this.lastCharTime >= charDelay) {
      this.lastCharTime = elapsed;
      const line = NEWS_ITEMS[this.currentLine];
      if (this.charIndex < line.length) {
        this.charIndex++;
      } else {
        // Line complete, pause then advance
        if (elapsed - this.lastCharTime >= 600) {
          this.displayedLines.push(line);
          this.currentLine++;
          this.charIndex = 0;
          this.lastCharTime = elapsed;
        }
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Header
    const headerLine = "=".repeat(80);
    grid.writeString(0, 0, headerLine, "#ff4444");
    grid.writeCentered(1, "BREAKING: TLDW INTELLIGENCE WIRE", "#ff6666");
    grid.writeString(0, 2, headerLine, "#ff4444");

    // Timestamp
    const secs = Math.floor(this.elapsed / 1000);
    const timestamp = `[${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}]`;
    grid.writeString(0, 3, timestamp, "#666666");

    // Completed lines
    const maxVisible = 16;
    const startIdx = Math.max(0, this.displayedLines.length - maxVisible);
    const visibleLines = this.displayedLines.slice(startIdx);

    let row = 5;
    for (const line of visibleLines) {
      if (row >= 22) break;
      grid.writeString(2, row, "> " + line.slice(0, 76), "#00cc88");
      row++;
    }

    // Current typing line
    if (this.currentLine < NEWS_ITEMS.length && row < 22) {
      const partial = NEWS_ITEMS[this.currentLine].slice(0, this.charIndex);
      const cursor = this.elapsed % 600 < 300 ? "_" : " ";
      grid.writeString(2, row, "> " + partial + cursor, "#ffffff");
    }

    // Footer
    grid.writeString(0, 23, headerLine, "#ff4444");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.displayedLines = [];
    this.currentLine = 0;
    this.charIndex = 0;
    this.lastCharTime = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.displayedLines = [];
    this.grid.clear();
  }
}
