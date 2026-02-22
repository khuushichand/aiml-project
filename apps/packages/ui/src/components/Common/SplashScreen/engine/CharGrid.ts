/**
 * 80×24 character grid helper for ASCII-art style canvas rendering.
 * Used by ~60% of effects that operate on a character grid.
 */
export class CharGrid {
  readonly cols: number;
  readonly rows: number;
  chars: string[][];
  colors: string[][];

  constructor(cols = 80, rows = 24) {
    this.cols = cols;
    this.rows = rows;
    this.chars = [];
    this.colors = [];
    this.clear();
  }

  /** Reset every cell to space + default color. */
  clear(defaultColor = "#aaaaaa"): void {
    this.chars = Array.from({ length: this.rows }, () => Array(this.cols).fill(" "));
    this.colors = Array.from({ length: this.rows }, () => Array(this.cols).fill(defaultColor));
  }

  /** Set a single cell. Out-of-bounds calls are silently ignored. */
  setCell(x: number, y: number, char: string, color: string): void {
    if (x >= 0 && x < this.cols && y >= 0 && y < this.rows) {
      this.chars[y][x] = char;
      this.colors[y][x] = color;
    }
  }

  /** Get the character at (x, y). Returns " " if out of bounds. */
  getChar(x: number, y: number): string {
    if (x >= 0 && x < this.cols && y >= 0 && y < this.rows) {
      return this.chars[y][x];
    }
    return " ";
  }

  /** Write a string starting at (x, y), clipping at grid edge. */
  writeString(x: number, y: number, text: string, color: string): void {
    for (let i = 0; i < text.length; i++) {
      this.setCell(x + i, y, text[i], color);
    }
  }

  /** Write centered text at row y. */
  writeCentered(y: number, text: string, color: string): void {
    const x = Math.floor((this.cols - text.length) / 2);
    this.writeString(x, y, text, color);
  }

  /** Fill an entire row with a character and color. */
  fillRow(y: number, char: string, color: string): void {
    if (y >= 0 && y < this.rows) {
      this.chars[y].fill(char);
      this.colors[y].fill(color);
    }
  }

  /**
   * Render the grid onto a canvas.
   * Each cell occupies cellW × cellH pixels.
   * Uses monospace fillText for characters.
   */
  renderToCanvas(ctx: CanvasRenderingContext2D, cellW: number, cellH: number): void {
    const fontSize = Math.floor(cellH * 0.85);
    ctx.font = `${fontSize}px "Courier New", "Consolas", monospace`;
    ctx.textBaseline = "top";

    for (let y = 0; y < this.rows; y++) {
      for (let x = 0; x < this.cols; x++) {
        const ch = this.chars[y][x];
        if (ch === " ") continue;
        ctx.fillStyle = this.colors[y][x];
        ctx.fillText(ch, x * cellW, y * cellH + (cellH - fontSize) * 0.5);
      }
    }
  }
}
