import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const DIAL_ART = [
  "      .-------.      ",
  "     /  .---.  \\     ",
  "    /  / 1 2 \\  \\    ",
  "   |  | 3   4 |  |   ",
  "   |  | 5   6 |  |   ",
  "    \\  \\ 7 8 /  /    ",
  "     \\  '---'  /     ",
  "      '-------'      ",
];

const PHONE_NUMBER = "555-8675-309";

export default class PhoneboothsDialing implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private dialedDigits = "";
  private lastDialTime = 0;
  private currentDigitIdx = 0;
  private clickPhase = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    const dialInterval = 600;
    if (elapsed - this.lastDialTime >= dialInterval && this.currentDigitIdx < PHONE_NUMBER.length) {
      const ch = PHONE_NUMBER[this.currentDigitIdx];
      this.dialedDigits += ch;
      this.currentDigitIdx++;
      this.lastDialTime = elapsed;
      this.clickPhase = 1.0;
    }

    if (this.currentDigitIdx >= PHONE_NUMBER.length && elapsed - this.lastDialTime > 2000) {
      this.currentDigitIdx = 0;
      this.dialedDigits = "";
      this.lastDialTime = elapsed;
    }

    this.clickPhase *= 0.92;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Title
    grid.writeCentered(1, "CONNECTING...", "#ffcc00");

    // Rotary dial art
    const dialStartY = 4;
    const rotation = this.elapsed / 500;
    for (let i = 0; i < DIAL_ART.length; i++) {
      grid.writeCentered(dialStartY + i, DIAL_ART[i], "#ccaa66");
    }

    // Spinning indicator on the dial
    const spinChars = "|/-\\";
    const si = Math.floor(rotation) % 4;
    grid.setCell(40, dialStartY + 3, spinChars[si], "#ffffff");

    // Click visualization
    if (this.clickPhase > 0.1) {
      const clickBar = "*".repeat(Math.floor(this.clickPhase * 20));
      grid.writeCentered(13, clickBar, "#ff8800");
    }

    // Dialed number display
    grid.writeCentered(15, "DIALING:", "#888888");
    const displayNum = this.dialedDigits.padEnd(PHONE_NUMBER.length, "_");
    grid.writeCentered(16, `[ ${displayNum} ]`, "#00ff88");

    // Pulse rings
    const ringY = 19;
    const numRings = Math.min(this.dialedDigits.replace(/-/g, "").length, 10);
    let ringStr = "";
    for (let i = 0; i < numRings; i++) {
      const phase = Math.sin(this.elapsed / 300 + i * 0.5);
      ringStr += phase > 0 ? "(( " : " ) ";
    }
    grid.writeCentered(ringY, ringStr, "#44aaff");

    // Footer
    grid.writeCentered(22, "tldw Telecommunications", "#666666");

    // Border
    for (let y = 0; y < 24; y++) {
      grid.setCell(0, y, "|", "#554400");
      grid.setCell(79, y, "|", "#554400");
    }

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.dialedDigits = "";
    this.lastDialTime = 0;
    this.currentDigitIdx = 0;
    this.clickPhase = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.grid.clear();
  }
}
