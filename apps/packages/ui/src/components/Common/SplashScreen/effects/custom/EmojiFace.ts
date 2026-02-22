import type { SplashEffect } from "../../engine/types";
import { CharGrid } from "../../engine/CharGrid";

interface FaceExpression {
  name: string;
  leftEye: string[];
  rightEye: string[];
  mouth: string[];
  mouthY: number;
}

const EXPRESSIONS: FaceExpression[] = [
  {
    name: "happy",
    leftEye: ["  O  "],
    rightEye: ["  O  "],
    mouth: ["  \\______/  "],
    mouthY: 0,
  },
  {
    name: "surprised",
    leftEye: ["  O  "],
    rightEye: ["  O  "],
    mouth: ["    OOOO    "],
    mouthY: 0,
  },
  {
    name: "winking",
    leftEye: ["  -  "],
    rightEye: ["  O  "],
    mouth: ["  \\______/  "],
    mouthY: 0,
  },
  {
    name: "sad",
    leftEye: ["  O  "],
    rightEye: ["  O  "],
    mouth: ["  /^^^^^^\\  "],
    mouthY: 0,
  },
  {
    name: "cool",
    leftEye: [" |==|"],
    rightEye: ["|==| "],
    mouth: ["   ______   "],
    mouthY: 0,
  },
  {
    name: "sleepy",
    leftEye: ["  -  "],
    rightEye: ["  -  "],
    mouth: ["   ~~~~~~   "],
    mouthY: 0,
  },
];

export default class EmojiFace implements SplashEffect {
  private grid!: CharGrid;
  private cellW = 0;
  private cellH = 0;
  private canvasW = 0;
  private canvasH = 0;
  private currentExpr = 0;
  private exprTimer = 0;
  private transitionAlpha = 1;

  init(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.canvasW = width;
    this.canvasH = height;
    this.grid = new CharGrid(80, 24);
    this.cellW = width / 80;
    this.cellH = height / 24;
    this.currentExpr = 0;
    this.exprTimer = 0;
    this.transitionAlpha = 1;
  }

  update(elapsed: number, dt: number): void {
    this.exprTimer += dt;

    // Switch expression every 2 seconds
    if (this.exprTimer > 2000) {
      this.currentExpr = (this.currentExpr + 1) % EXPRESSIONS.length;
      this.exprTimer = 0;
      this.transitionAlpha = 0;
    }

    // Transition fade-in
    if (this.transitionAlpha < 1) {
      this.transitionAlpha = Math.min(1, this.transitionAlpha + dt / 400);
    }

    this.grid.clear("#000");
    const expr = EXPRESSIONS[this.currentExpr];
    const cx = 40;
    const faceTop = 4;

    // Yellow color with brightness based on transition
    const bright = Math.floor(50 + this.transitionAlpha * 50);
    const yellow = `hsl(50,100%,${bright}%)`;
    const dimYellow = `hsl(50,80%,${Math.floor(bright * 0.6)}%)`;

    // Face outline (circle approximation)
    const faceRadius = 8;
    for (let angle = 0; angle < 360; angle += 3) {
      const rad = (angle * Math.PI) / 180;
      const fx = Math.round(cx + Math.cos(rad) * faceRadius * 2);
      const fy = Math.round(faceTop + 7 + Math.sin(rad) * faceRadius * 0.7);
      if (fx >= 0 && fx < 80 && fy >= 0 && fy < 24) {
        this.grid.setCell(fx, fy, "*", dimYellow);
      }
    }

    // Eyes
    const eyeY = faceTop + 5;
    const leftEyeX = cx - 6;
    const rightEyeX = cx + 3;
    for (const line of expr.leftEye) {
      this.grid.writeString(leftEyeX, eyeY, line, yellow);
    }
    for (const line of expr.rightEye) {
      this.grid.writeString(rightEyeX, eyeY, line, yellow);
    }

    // Mouth
    const mouthY = faceTop + 10;
    for (let i = 0; i < expr.mouth.length; i++) {
      const mx = cx - Math.floor(expr.mouth[i].length / 2);
      this.grid.writeString(mx, mouthY + i, expr.mouth[i], yellow);
    }

    // Expression label
    const label = `[ ${expr.name.toUpperCase()} ]`;
    this.grid.writeCentered(faceTop + 15, label, dimYellow);

    // Decorative sparkle around face
    const sparkleChars = "*.+";
    const sparkleCount = 8;
    for (let i = 0; i < sparkleCount; i++) {
      const sAngle = (i / sparkleCount) * Math.PI * 2 + elapsed * 0.002;
      const sx = Math.round(cx + Math.cos(sAngle) * 22);
      const sy = Math.round(faceTop + 7 + Math.sin(sAngle) * 10);
      if (sx >= 0 && sx < 80 && sy >= 0 && sy < 24) {
        const ch = sparkleChars[Math.floor((elapsed / 200 + i) % sparkleChars.length)];
        this.grid.setCell(sx, sy, ch, `hsl(50,100%,${60 + Math.sin(elapsed * 0.005 + i) * 30}%)`);
      }
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, this.canvasW, this.canvasH);
    this.grid.renderToCanvas(ctx, this.cellW, this.cellH);
  }

  reset(): void {
    this.currentExpr = 0;
    this.exprTimer = 0;
    this.transitionAlpha = 1;
  }

  dispose(): void {}
}
