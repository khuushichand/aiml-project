import React, { useEffect, useMemo, useRef, useState } from "react";
import { useAnimationFrame } from "./engine/useAnimationFrame";
import { loadEffect } from "./engine/registry";
import type { SplashEffect } from "./engine/types";

interface SplashCanvasProps {
  effectName: string;
  effectConfig?: Record<string, unknown>;
  active: boolean;
}

const resolveTokenColor = (tokenName: string, fallbackRgb: string): string => {
  if (typeof window === "undefined") return fallbackRgb;
  const tokenValue = getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim();
  return tokenValue ? `rgb(${tokenValue})` : fallbackRgb;
};

/**
 * Canvas element that loads and runs a single splash effect.
 * Fills its parent container and runs a RAF animation loop.
 */
const SplashCanvas: React.FC<SplashCanvasProps> = ({ effectName, effectConfig, active }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const effectRef = useRef<SplashEffect | null>(null);
  const [ready, setReady] = useState(false);
  const canvasBackgroundColor = useMemo(
    () => resolveTokenColor("--color-bg", "rgb(0 0 0)"),
    []
  );

  // Load the effect module
  useEffect(() => {
    let cancelled = false;
    loadEffect(effectName).then((effect) => {
      if (cancelled || !effect) return;
      effectRef.current = effect;
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          // Size canvas to fill parent
          const rect = canvas.parentElement?.getBoundingClientRect();
          canvas.width = rect?.width ?? window.innerWidth;
          canvas.height = rect?.height ?? window.innerHeight;
          effect.init(ctx, canvas.width, canvas.height, effectConfig);
          setReady(true);
        }
      }
    });
    return () => {
      cancelled = true;
      effectRef.current?.dispose();
      effectRef.current = null;
      setReady(false);
    };
  }, [effectName, effectConfig]);

  // Resize handler
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onResize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      canvas.width = rect?.width ?? window.innerWidth;
      canvas.height = rect?.height ?? window.innerHeight;
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Animation loop
  useAnimationFrame((elapsed, dt) => {
    const effect = effectRef.current;
    const canvas = canvasRef.current;
    if (!effect || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear
    ctx.fillStyle = canvasBackgroundColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    effect.update(elapsed, dt);
    effect.render(ctx);
  }, active && ready);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        display: "block",
      }}
    />
  );
};

export default SplashCanvas;
