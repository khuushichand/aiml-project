/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["../../packages/ui/src/**/*.{ts,tsx}", "./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        surface2: "rgb(var(--color-surface-2) / <alpha-value>)",
        elevated: "rgb(var(--color-elevated) / <alpha-value>)",
        primary: "rgb(var(--color-primary) / <alpha-value>)",
        primaryStrong: "rgb(var(--color-primary-strong) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        success: "rgb(var(--color-success) / <alpha-value>)",
        warn: "rgb(var(--color-warn) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        border: "rgb(var(--color-border) / <alpha-value>)",
        borderStrong: "rgb(var(--color-border-strong) / <alpha-value>)",
        "border-strong": "rgb(var(--color-border-strong) / <alpha-value>)",
        text: "rgb(var(--color-text) / <alpha-value>)",
        textMuted: "rgb(var(--color-text-muted) / <alpha-value>)",
        "text-muted": "rgb(var(--color-text-muted) / <alpha-value>)",
        textSubtle: "rgb(var(--color-text-subtle) / <alpha-value>)",
        "text-subtle": "rgb(var(--color-text-subtle) / <alpha-value>)",
        focus: "rgb(var(--color-focus) / <alpha-value>)"
      },
      fontFamily: {
        display: ["Space Grotesk", "Inter", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        arimo: ["Arimo", "sans-serif"]
      },
      fontSize: {
        body: ["14px", { lineHeight: "20px" }],
        message: ["15px", { lineHeight: "22px" }],
        caption: ["12px", { lineHeight: "16px" }],
        label: ["11px", { lineHeight: "14px", letterSpacing: "0.04em" }]
      },
      borderRadius: {
        card: "12px",
        pill: "9999px"
      },
      boxShadow: {
        card: "0 6px 18px rgba(0,0,0,0.16)",
        modal: "0 10px 30px rgba(0,0,0,0.28)"
      },
      backgroundImage: {
        "bottom-mask-light":
          "linear-gradient(0deg, transparent 0, #ffffff 160px)",
        "bottom-mask-dark":
          "linear-gradient(0deg, transparent 0, #171717 160px)"
      },
      maskImage: {
        "bottom-fade": "linear-gradient(0deg, transparent 0, #000 160px)"
      },
      keyframes: {
        shake: {
          "0%, 100%": { transform: "translateX(0)" },
          "10%, 30%, 50%, 70%, 90%": { transform: "translateX(-2px)" },
          "20%, 40%, 60%, 80%": { transform: "translateX(2px)" }
        }
      },
      animation: {
        shake: "shake 0.3s ease-in-out"
      }
    }
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/typography")]
}
