import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

interface Node {
  x: number;
  y: number;
  layer: number;
  active: number;
}

export default class NeuralNetwork implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;
  private nodes: Node[] = [];
  private layers = [4, 6, 8, 6, 4, 2];
  private signalTime = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
    this.nodes = [];

    const layerSpacing = Math.floor(70 / (this.layers.length + 1));

    for (let l = 0; l < this.layers.length; l++) {
      const count = this.layers[l];
      const x = 5 + (l + 1) * layerSpacing;
      const vertSpacing = Math.floor(20 / (count + 1));
      for (let n = 0; n < count; n++) {
        const y = 2 + (n + 1) * vertSpacing;
        this.nodes.push({ x, y, layer: l, active: 0 });
      }
    }
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
    this.signalTime = (elapsed / 800) % (this.layers.length + 1);

    for (const node of this.nodes) {
      const dist = Math.abs(node.layer - this.signalTime);
      node.active = dist < 1.0 ? 1.0 - dist : 0;
    }
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    // Draw connections between adjacent layers
    for (const n1 of this.nodes) {
      for (const n2 of this.nodes) {
        if (n2.layer !== n1.layer + 1) continue;
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const steps = Math.max(Math.abs(dx), Math.abs(dy));
        if (steps === 0) continue;

        for (let s = 1; s < steps; s++) {
          const px = Math.round(n1.x + (dx * s) / steps);
          const py = Math.round(n1.y + (dy * s) / steps);
          if (px >= 0 && px < 80 && py >= 0 && py < 24) {
            const signal = Math.max(n1.active, n2.active) * 0.3;
            const bright = Math.floor(20 + signal * 60);
            grid.setCell(px, py, ".", `hsl(200,60%,${bright}%)`);
          }
        }
      }
    }

    // Draw nodes
    for (const node of this.nodes) {
      if (node.x >= 0 && node.x < 80 && node.y >= 0 && node.y < 24) {
        const bright = Math.floor(40 + node.active * 60);
        const hue = node.active > 0.5 ? 60 : 200;
        grid.setCell(node.x, node.y, "O", `hsl(${hue},80%,${bright}%)`);
      }
    }

    grid.writeCentered(0, "Neural Network Inference", "#ffffff");
    grid.writeCentered(23, "tldw AI Engine", "#00ccff");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.nodes = [];
    this.grid.clear();
  }
}
