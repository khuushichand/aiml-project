import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../types";

interface CreditEntry {
  role?: string;
  name?: string;
  line?: string;
}

export default class ScrollingCreditsEffect implements SplashEffect {
  private grid!: CharGrid;
  private width = 0;
  private height = 0;
  private cellW = 0;
  private cellH = 0;
  private title = "tldw";
  private creditLines: string[] = [];
  private scrollSpeed = 4; // rows per second

  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void {
    this.width = width;
    this.height = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.title = (config?.title as string) ?? "tldw";
    this.scrollSpeed = (config?.scroll_speed as number) ?? 4;

    const creditsList: CreditEntry[] = (config?.credits_list as CreditEntry[]) ?? [
      { role: "Creator", name: "The tldw Team" },
      { line: "" },
      { role: "Backend", name: "FastAPI + Python" },
      { role: "Frontend", name: "Next.js + TypeScript" },
      { role: "Database", name: "SQLite + ChromaDB" },
      { line: "" },
      { role: "Audio", name: "faster_whisper + Kokoro" },
      { role: "LLMs", name: "16+ Providers" },
      { line: "" },
      { line: "Thank you for using tldw!" },
    ];

    this.creditLines = [];
    for (const entry of creditsList) {
      if (entry.line !== undefined) {
        this.creditLines.push(entry.line);
      } else if (entry.role && entry.name) {
        this.creditLines.push(`${entry.role}: ${entry.name}`);
      }
    }
  }

  update(elapsed: number, _dt: number): void {
    this.grid.clear();

    // Fixed title at top
    this.grid.writeCentered(1, this.title, "rgb(255,255,100)");
    this.grid.writeCentered(2, "=".repeat(this.title.length + 4), "rgb(100,100,100)");

    // Scroll credits upward
    const scrollOffset = (elapsed / 1000) * this.scrollSpeed;
    const startRow = 5;
    const visibleRows = 24 - startRow;

    for (let i = 0; i < this.creditLines.length; i++) {
      const row = startRow + i - Math.floor(scrollOffset);
      if (row >= startRow && row < 24) {
        const line = this.creditLines[i];
        const isRole = line.includes(":");
        const color = isRole ? "rgb(100,200,255)" : "rgb(200,200,200)";
        this.grid.writeCentered(row, line, color);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.width, this.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {}

  dispose(): void {
    this.creditLines = [];
  }
}
