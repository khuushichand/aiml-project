import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const NEON_TEXT = [
  " ████████╗██╗     ██████╗ ██╗    ██╗ ",
  " ╚══██╔══╝██║     ██╔══██╗██║    ██║ ",
  "    ██║   ██║     ██║  ██║██║ █╗ ██║ ",
  "    ██║   ██║     ██║  ██║██║███╗██║ ",
  "    ██║   ███████╗██████╔╝╚███╔███╔╝ ",
  "    ╚═╝   ╚══════╝╚═════╝  ╚══╝╚══╝  ",
];

const SUBTITLE = "Too Long; Didn't Watch";

interface LetterState {
  on: boolean;
  nextFlicker: number;
  flickerDuration: number;
  hue: number;
}

export default class NeonSignFlicker implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private letterStates: LetterState[] = [];
  private subtitleStates: LetterState[] = [];

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.reset();
  }

  private initStates(count: number, baseHue: number): LetterState[] {
    const states: LetterState[] = [];
    for (let i = 0; i < count; i++) {
      states.push({
        on: true,
        nextFlicker: Math.random() * 3000,
        flickerDuration: 50 + Math.random() * 150,
        hue: baseHue + Math.random() * 30 - 15,
      });
    }
    return states;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;

    const updateState = (s: LetterState) => {
      if (elapsed > s.nextFlicker) {
        if (s.on) {
          s.on = false;
          s.nextFlicker = elapsed + s.flickerDuration;
        } else {
          s.on = true;
          s.nextFlicker = elapsed + 500 + Math.random() * 4000;
          s.flickerDuration = 30 + Math.random() * 200;
        }
      }
    };

    for (const s of this.letterStates) updateState(s);
    for (const s of this.subtitleStates) updateState(s);
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Background glow effect
    const glowY = 5;
    for (let y = glowY - 2; y < glowY + NEON_TEXT.length + 2; y++) {
      if (y < 0 || y >= 24) continue;
      for (let x = 15; x < 65; x++) {
        if (Math.random() < 0.05) {
          grid.setCell(x, y, ".", "#220022");
        }
      }
    }

    // Main neon text
    const startY = 6;
    let stateIdx = 0;
    for (let i = 0; i < NEON_TEXT.length; i++) {
      const line = NEON_TEXT[i];
      const sx = Math.floor((80 - line.length) / 2);
      for (let c = 0; c < line.length; c++) {
        if (line[c] === " ") continue;
        const si = stateIdx % this.letterStates.length;
        const state = this.letterStates[si];
        stateIdx++;

        if (state.on) {
          const buzz = Math.sin(this.elapsed / 50 + c) * 10;
          const lum = 60 + buzz;
          grid.setCell(sx + c, startY + i, line[c], `hsl(320,100%,${lum}%)`);
        } else {
          grid.setCell(sx + c, startY + i, line[c], "#330033");
        }
      }
    }

    // Subtitle in electric blue
    const subY = startY + NEON_TEXT.length + 2;
    const subX = Math.floor((80 - SUBTITLE.length) / 2);
    for (let c = 0; c < SUBTITLE.length; c++) {
      if (SUBTITLE[c] === " ") continue;
      const si = c % this.subtitleStates.length;
      const state = this.subtitleStates[si];

      if (state.on) {
        const buzz = Math.sin(this.elapsed / 60 + c * 0.5) * 8;
        const lum = 55 + buzz;
        grid.setCell(subX + c, subY, SUBTITLE[c], `hsl(200,100%,${lum}%)`);
      } else {
        grid.setCell(subX + c, subY, SUBTITLE[c], "#002233");
      }
    }

    // "OPEN" sign
    const openY = 18;
    const openOn = this.elapsed % 2000 < 1500;
    if (openOn) {
      grid.writeCentered(openY, "[ O P E N ]", "#00ff66");
    } else {
      grid.writeCentered(openY, "[ O P E N ]", "#003311");
    }

    // Decorative bracket frame
    grid.writeCentered(3, "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~", "#440044");
    grid.writeCentered(21, "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~", "#440044");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.letterStates = this.initStates(200, 320);
    this.subtitleStates = this.initStates(SUBTITLE.length, 200);
    this.grid.clear();
  }

  dispose(): void {
    this.letterStates = [];
    this.subtitleStates = [];
    this.grid.clear();
  }
}
