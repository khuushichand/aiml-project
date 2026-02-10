import React from "react";
import { getAsciiArt } from "../../../data/splash-ascii-art";

interface AsciiArtOverlayProps {
  artKey?: string;
  title?: string;
  message: string;
  reducedMotion?: boolean;
}

/**
 * HTML overlay for ASCII art + loading message.
 * Positioned on top of the canvas for accessibility (screen readers can read it).
 */
const AsciiArtOverlay: React.FC<AsciiArtOverlayProps> = ({ artKey, title, message, reducedMotion = false }) => {
  const art = artKey ? getAsciiArt(artKey) : null;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        pointerEvents: "none",
        zIndex: 2,
        padding: "2rem",
      }}
    >
      {art && (
        <pre
          style={{
            fontFamily: '"Courier New", Consolas, monospace',
            fontSize: "clamp(6px, 1.1vw, 14px)",
            lineHeight: 1.2,
            color: "rgb(var(--color-text) / 0.9)",
            textAlign: "center",
            whiteSpace: "pre",
            margin: 0,
            textShadow: "0 0 8px rgb(var(--color-primary) / 0.35)",
            maxWidth: "100%",
            overflow: "hidden",
          }}
          aria-label="TLDW Chatbook splash art"
        >
          {art}
        </pre>
      )}

      {title && (
        <h1
          style={{
            fontFamily: '"Courier New", Consolas, monospace',
            fontSize: "clamp(16px, 2.5vw, 28px)",
            color: "rgb(var(--color-primary))",
            marginTop: "1rem",
            textShadow: "0 0 12px rgb(var(--color-primary) / 0.45)",
            letterSpacing: "0.1em",
          }}
        >
          {title}
        </h1>
      )}

      {message && (
        <p
          style={{
            fontFamily: '"Courier New", Consolas, monospace',
            fontSize: "clamp(10px, 1.4vw, 16px)",
            color: "rgb(var(--color-text-muted) / 0.95)",
            marginTop: "0.75rem",
            fontStyle: "italic",
            animation: reducedMotion ? "none" : "splashFadeIn 0.8s ease-in",
          }}
        >
          {message}
        </p>
      )}

      <p
        style={{
          position: "absolute",
          bottom: "1.5rem",
          fontFamily: '"Courier New", Consolas, monospace',
          fontSize: "clamp(9px, 1vw, 13px)",
          color: "rgb(var(--color-text-subtle) / 0.9)",
          animation: reducedMotion ? "none" : "splashPulse 2s ease-in-out infinite",
        }}
      >
        Click anywhere or press any key to continue
      </p>
    </div>
  );
};

export default AsciiArtOverlay;
