import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const MESSAGES = [
  "root@tldw:~# nmap -sV 192.168.1.0/24",
  "Scanning 254 hosts... done",
  "[+] 192.168.1.42:8000  OPEN  tldw-api/1.0",
  "[+] 192.168.1.42:5432  OPEN  postgresql",
  "root@tldw:~# ssh admin@192.168.1.42",
  "Last login: Today from 10.0.0.1",
  "admin@tldw:~$ systemctl status tldw",
  "  tldw.service - TLDW Media Server",
  "  Active: active (running) since boot",
  "admin@tldw:~$ tail -f /var/log/tldw/access.log",
  "GET /api/v1/media 200 12ms",
  "POST /api/v1/chat/completions 200 847ms",
  "POST /api/v1/rag/search 200 156ms",
  "GET /api/v1/embeddings 200 23ms",
  "admin@tldw:~$ cat /proc/gpu/utilization",
  "GPU 0: 73% | VRAM: 18.2/24.0 GB",
  "admin@tldw:~$ python -c 'import tldw; tldw.status()'",
  "Models loaded: 4 | Cache: 94.2% hit | Queue: 0",
  "admin@tldw:~$ grep -c 'processed' /var/log/tldw/media.log",
  "47,832 media items processed",
];

export default class HackerTerminal implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private visibleLines: string[] = [];
  private lineIdx = 0;
  private charIdx = 0;
  private lastCharTime = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    const charDelay = 15;
    if (elapsed - this.lastCharTime >= charDelay && this.lineIdx < MESSAGES.length) {
      this.lastCharTime = elapsed;
      this.charIdx++;

      const line = MESSAGES[this.lineIdx];
      if (this.charIdx >= line.length) {
        this.visibleLines.push(line);
        this.lineIdx++;
        this.charIdx = 0;
        this.lastCharTime = elapsed + 100;
      }
    }

    if (this.lineIdx >= MESSAGES.length) {
      this.lineIdx = 0;
      this.visibleLines = [];
      this.charIdx = 0;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Header bar
    grid.writeString(0, 0, " TLDW Terminal v2.0 - root@tldw ".padEnd(80, " "), "#00ff00");

    // Progress bar at top
    const progress = (this.elapsed % 5000) / 5000;
    const barLen = 30;
    const filled = Math.floor(progress * barLen);
    const bar = "[" + "=".repeat(filled) + ">".padEnd(barLen - filled, " ") + "]";
    grid.writeString(48, 0, bar, "#00cc00");

    // Completed lines
    const maxVisible = 20;
    const startIdx = Math.max(0, this.visibleLines.length - maxVisible);
    const visible = this.visibleLines.slice(startIdx);

    let row = 2;
    for (const line of visible) {
      if (row >= 23) break;
      const color = line.startsWith("[+]") ? "#00ff88"
        : line.startsWith("root@") || line.startsWith("admin@") ? "#00ff00"
        : line.includes("OPEN") ? "#ffcc00"
        : "#008800";
      grid.writeString(0, row, line.slice(0, 80), color);
      row++;
    }

    // Current typing line
    if (this.lineIdx < MESSAGES.length && row < 23) {
      const partial = MESSAGES[this.lineIdx].slice(0, this.charIdx);
      const cursor = this.elapsed % 500 < 250 ? "_" : " ";
      grid.writeString(0, row, partial + cursor, "#00ff00");
    }

    // Bottom status bar
    const status = ` Lines: ${this.visibleLines.length} | PID: 1337 | MEM: 2.4G `;
    grid.writeString(0, 23, status.padEnd(80, " "), "#003300");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.visibleLines = [];
    this.lineIdx = 0;
    this.charIdx = 0;
    this.lastCharTime = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.visibleLines = [];
    this.grid.clear();
  }
}
