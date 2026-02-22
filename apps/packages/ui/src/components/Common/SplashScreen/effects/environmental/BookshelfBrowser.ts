import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface Book { title: string; width: number; color: string }

const BOOK_COLORS = [
  "#884422", "#225588", "#885522", "#228855", "#882244",
  "#448822", "#664488", "#886644", "#446688", "#884466",
];
const SHELF_COLOR = "#553311";
const BG_COLOR = "#1a0f08";
const HIGHLIGHT = "#ffdd88";
const TITLES = [
  "LOTR", "Dune", "1984", "Moby", "HHGTTG", "Neuromcr",
  "SnowCr", "Hobbit", "Fndtn", "Brave", "Fahrn", "Solaris",
  "Left", "DkTwr", "Hyperion", "Ender", "Contact", "Anathem",
];

export default class BookshelfBrowserEffect implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private cellW = 0;
  private cellH = 0;
  private time = 0;
  private books: Book[] = [];
  private cursor = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.cellW = width / this.grid.cols;
    this.cellH = height / this.grid.rows;
    this.time = 0;
    this.cursor = 0;
    this.books = TITLES.map((t, i) => ({
      title: t,
      width: 3 + t.length,
      color: BOOK_COLORS[i % BOOK_COLORS.length],
    }));
  }

  update(elapsed: number, _dt: number): void {
    this.time = elapsed / 1000;
    this.cursor = Math.floor(this.time * 0.5) % this.books.length;
    this.grid.clear(BG_COLOR);

    // draw 3 shelves
    for (let shelf = 0; shelf < 3; shelf++) {
      const shelfY = 6 + shelf * 7;
      this.grid.fillRow(shelfY, "=", SHELF_COLOR);
      this.grid.fillRow(shelfY + 1, "_", SHELF_COLOR);

      // books on shelf
      let x = 2;
      const startBook = shelf * 6;
      for (let b = 0; b < 6 && startBook + b < this.books.length; b++) {
        const book = this.books[startBook + b];
        const isSelected = startBook + b === this.cursor;
        const bookH = 5;
        for (let dy = 0; dy < bookH; dy++) {
          const by = shelfY - bookH + dy;
          if (by < 0) continue;
          // sides
          this.grid.setCell(x, by, "|", isSelected ? HIGHLIGHT : book.color);
          this.grid.setCell(x + book.width - 1, by, "|", isSelected ? HIGHLIGHT : book.color);
          // fill
          for (let dx = 1; dx < book.width - 1; dx++) {
            this.grid.setCell(x + dx, by, "\u2591", isSelected ? HIGHLIGHT : book.color);
          }
        }
        // title on spine (vertical)
        const titleY = shelfY - bookH + 1;
        const tx = x + 1;
        for (let ci = 0; ci < book.title.length && ci < bookH - 1; ci++) {
          if (titleY + ci >= 0 && titleY + ci < this.grid.rows) {
            this.grid.setCell(tx, titleY + ci, book.title[ci], isSelected ? "#000000" : "#ddccaa");
          }
        }

        if (isSelected) {
          const arrow = shelfY - bookH - 1;
          if (arrow >= 0) this.grid.setCell(x + Math.floor(book.width / 2), arrow, "v", HIGHLIGHT);
        }

        x += book.width + 1;
      }
    }

    this.grid.writeCentered(0, "[ Library ]", "#ddccaa");
    const sel = this.books[this.cursor];
    this.grid.writeCentered(this.grid.rows - 1, `> ${sel.title} <`, HIGHLIGHT);
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void { this.time = 0; this.cursor = 0; }
  dispose(): void { this.books = []; }
}
