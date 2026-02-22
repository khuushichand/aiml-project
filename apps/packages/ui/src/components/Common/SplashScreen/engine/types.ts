/** Base interface for all splash screen effects — mirrors Python's BaseEffect. */
export interface SplashEffect {
  /** Initialize the effect with canvas context and dimensions. */
  init(ctx: CanvasRenderingContext2D, width: number, height: number, config?: Record<string, unknown>): void;
  /** Called each animation frame. elapsed = ms since start, dt = ms since last frame. */
  update(elapsed: number, dt: number): void;
  /** Render the current state to the canvas. */
  render(ctx: CanvasRenderingContext2D): void;
  /** Reset the effect to its initial state. */
  reset(): void;
  /** Clean up resources (cancel timers, release buffers, etc). */
  dispose(): void;
}

/** A splash card pairs an effect with ASCII art and configuration. */
export interface SplashCard {
  name: string;
  /** Key into the effect registry (e.g. "matrix_rain"), or null for static source cards. */
  effect: string | null;
  /** Key into the ASCII art variants (e.g. "default", "compact"). */
  asciiArt?: string;
  /** Title text rendered over the canvas. */
  title?: string;
  /** Subtitle / loading message. */
  subtitle?: string;
  /** Override default display duration in ms. */
  duration?: number;
  /** Passed to effect.init() as config. */
  effectConfig?: Record<string, unknown>;
}

/** Loader function type — returns a module with a default SplashEffect constructor. */
export type EffectLoader = () => Promise<{ default: new () => SplashEffect }>;
