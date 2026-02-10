import { useCallback, useEffect, useRef } from "react";

/**
 * requestAnimationFrame hook.
 * Calls `callback(elapsed, deltaTime)` each frame.
 * Automatically starts/stops with the component lifecycle.
 * Respects `prefers-reduced-motion`.
 */
export function useAnimationFrame(
  callback: (elapsed: number, dt: number) => void,
  active = true
): void {
  const cbRef = useRef(callback);
  cbRef.current = callback;

  const rafRef = useRef(0);
  const startRef = useRef(0);
  const prevRef = useRef(0);

  const loop = useCallback((now: number) => {
    if (!startRef.current) {
      startRef.current = now;
      prevRef.current = now;
    }
    const elapsed = now - startRef.current;
    const dt = now - prevRef.current;
    prevRef.current = now;
    cbRef.current(elapsed, dt);
    rafRef.current = requestAnimationFrame(loop);
  }, []);

  useEffect(() => {
    if (!active) return;

    // Skip animation for users who prefer reduced motion
    const reducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) {
      // Fire one frame so the effect can render a static state
      cbRef.current(0, 0);
      return;
    }

    startRef.current = 0;
    prevRef.current = 0;
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [active, loop]);
}
