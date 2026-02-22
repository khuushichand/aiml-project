import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

type Piece = { shape: number[][]; color: string };

export default class TetrisEffect implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private w = 0;
  private h = 0;
  private board: (string | null)[][] = [];
  private currentPiece!: Piece;
  private pieceX = 0;
  private pieceY = 0;
  private dropTimer = 0;
  private score = 0;
  private lines = 0;
  private boardW = 10;
  private boardH = 20;
  private offsetX = 35;
  private offsetY = 2;

  private pieces: Piece[] = [
    { shape: [[1, 1, 1, 1]], color: "#0ff" },             // I
    { shape: [[1, 1], [1, 1]], color: "#ff0" },            // O
    { shape: [[0, 1, 0], [1, 1, 1]], color: "#a0f" },     // T
    { shape: [[1, 0], [1, 0], [1, 1]], color: "#fa0" },   // L
    { shape: [[0, 1], [0, 1], [1, 1]], color: "#00f" },   // J
    { shape: [[0, 1, 1], [1, 1, 0]], color: "#0f0" },     // S
    { shape: [[1, 1, 0], [0, 1, 1]], color: "#f00" },     // Z
  ];

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.w = width;
    this.h = height;
    this.board = Array.from({ length: this.boardH }, () => Array(this.boardW).fill(null));
    this.score = 0;
    this.lines = 0;
    this.spawnPiece();
  }

  private spawnPiece(): void {
    this.currentPiece = this.pieces[Math.floor(Math.random() * this.pieces.length)];
    this.pieceX = Math.floor((this.boardW - this.currentPiece.shape[0].length) / 2);
    this.pieceY = 0;
  }

  private collides(px: number, py: number, shape: number[][]): boolean {
    for (let r = 0; r < shape.length; r++) {
      for (let c = 0; c < shape[r].length; c++) {
        if (!shape[r][c]) continue;
        const bx = px + c;
        const by = py + r;
        if (bx < 0 || bx >= this.boardW || by >= this.boardH) return true;
        if (by >= 0 && this.board[by][bx]) return true;
      }
    }
    return false;
  }

  private lock(): void {
    const { shape, color } = this.currentPiece;
    for (let r = 0; r < shape.length; r++) {
      for (let c = 0; c < shape[r].length; c++) {
        if (!shape[r][c]) continue;
        const by = this.pieceY + r;
        const bx = this.pieceX + c;
        if (by >= 0 && by < this.boardH) this.board[by][bx] = color;
      }
    }
    this.clearLines();
    this.spawnPiece();
    if (this.collides(this.pieceX, this.pieceY, this.currentPiece.shape)) {
      this.board = Array.from({ length: this.boardH }, () => Array(this.boardW).fill(null));
      this.score = 0;
      this.lines = 0;
    }
  }

  private clearLines(): void {
    for (let r = this.boardH - 1; r >= 0; r--) {
      if (this.board[r].every(c => c !== null)) {
        this.board.splice(r, 1);
        this.board.unshift(Array(this.boardW).fill(null));
        this.score += 100;
        this.lines++;
        r++;
      }
    }
  }

  update(_elapsed: number, dt: number): void {
    this.dropTimer += dt;
    const speed = Math.max(80, 400 - this.lines * 20);
    if (this.dropTimer > speed) {
      this.dropTimer = 0;
      if (!this.collides(this.pieceX, this.pieceY + 1, this.currentPiece.shape)) {
        this.pieceY++;
      } else {
        this.lock();
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    this.grid.clear();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.w, this.h);

    // Board border
    for (let r = 0; r < this.boardH; r++) {
      const y = this.offsetY + r;
      if (y < 24) {
        this.grid.setCell(this.offsetX - 1, y, "│", "#555");
        this.grid.setCell(this.offsetX + this.boardW, y, "│", "#555");
      }
    }
    const botY = this.offsetY + this.boardH;
    if (botY < 24) {
      this.grid.writeString(this.offsetX - 1, botY, "└" + "─".repeat(this.boardW) + "┘", "#555");
    }

    // Board
    for (let r = 0; r < this.boardH; r++) {
      for (let c = 0; c < this.boardW; c++) {
        const y = this.offsetY + r;
        if (y < 24 && this.board[r][c]) {
          this.grid.setCell(this.offsetX + c, y, "█", this.board[r][c]!);
        }
      }
    }

    // Current piece
    const { shape, color } = this.currentPiece;
    for (let r = 0; r < shape.length; r++) {
      for (let c = 0; c < shape[r].length; c++) {
        if (!shape[r][c]) continue;
        const y = this.offsetY + this.pieceY + r;
        const x = this.offsetX + this.pieceX + c;
        if (y >= 0 && y < 24 && x >= 0 && x < 80) {
          this.grid.setCell(x, y, "█", color);
        }
      }
    }

    // Info panel
    this.grid.writeCentered(0, "T E T R I S", "#0ff");
    this.grid.writeString(5, 4, "SCORE", "#fff");
    this.grid.writeString(5, 5, `${this.score}`, "#ff0");
    this.grid.writeString(5, 8, "LINES", "#fff");
    this.grid.writeString(5, 9, `${this.lines}`, "#0f0");
    this.grid.writeString(55, 4, "LEVEL", "#fff");
    this.grid.writeString(55, 5, `${Math.floor(this.lines / 10) + 1}`, "#f0f");

    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.board = Array.from({ length: this.boardH }, () => Array(this.boardW).fill(null));
    this.score = 0;
    this.lines = 0;
    this.spawnPiece();
  }

  dispose(): void {
    this.board = [];
  }
}
