import React, { useEffect, useRef, useState } from "react"

type MermaidProps = {
  code: string
  className?: string
}

type MermaidTheme = "default" | "base" | "dark" | "forest" | "neutral" | "null"

const hashCode = (input: string) => {
  let hash = 0
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0
  }
  return hash.toString(36)
}

const resolveMermaidTheme = (): MermaidTheme => {
  try {
    if (typeof document !== "undefined") {
      const root = document.documentElement
      if (root.classList.contains("dark")) {
        return "dark"
      }
      if (root.classList.contains("light")) {
        return "default"
      }
    }
    if (typeof window !== "undefined") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "default"
    }
  } catch {
    return "default"
  }
  return "default"
}

const useMermaidTheme = () => {
  const [theme, setTheme] = useState<MermaidTheme>(() => resolveMermaidTheme())

  useEffect(() => {
    if (typeof window === "undefined" || typeof document === "undefined") {
      return
    }

    const updateTheme = () => {
      setTheme(resolveMermaidTheme())
    }

    updateTheme()

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
    const handleMediaChange = () => {
      updateTheme()
    }

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleMediaChange)
    } else {
      mediaQuery.addListener(handleMediaChange)
    }

    const observer = new MutationObserver(() => {
      updateTheme()
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"]
    })

    return () => {
      observer.disconnect()
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleMediaChange)
      } else {
        mediaQuery.removeListener(handleMediaChange)
      }
    }
  }, [])

  return theme
}

export const Mermaid: React.FC<MermaidProps> = ({ code, className }) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [error, setError] = useState<string | null>(null)
  const renderIdRef = useRef(0)
  const theme = useMermaidTheme()

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }

    let active = true
    const renderDiagram = async () => {
      if (!code?.trim()) {
        if (containerRef.current) {
          containerRef.current.textContent = ""
        }
        setError(null)
        return
      }

      try {
        const mermaidModule = await import("mermaid")
        const mermaid = mermaidModule.default
        mermaid.initialize({
          startOnLoad: false,
          theme,
          securityLevel: "strict"
        })
        const id = `mermaid-${hashCode(code)}-${renderIdRef.current++}`
        const { svg, bindFunctions } = await mermaid.render(id, code)

        if (!active || !containerRef.current) {
          return
        }

        containerRef.current.innerHTML = svg
        bindFunctions?.(containerRef.current)
        setError(null)
      } catch (err) {
        if (!active) return
        setError(
          err instanceof Error ? err.message : "Unable to render diagram."
        )
        if (containerRef.current) {
          containerRef.current.textContent = code
        }
      }
    }

    renderDiagram()
    return () => {
      active = false
    }
  }, [code, theme])

  if (typeof window === "undefined") {
    return (
      <pre className="whitespace-pre-wrap text-xs text-text">{code}</pre>
    )
  }

  return (
    <div className={className}>
      <div
        ref={containerRef}
        aria-label="Mermaid diagram"
        role="img"
        className="flex items-center justify-center"
      />
      {error && (
        <div className="mt-2 rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-muted">
          {error}
        </div>
      )}
    </div>
  )
}

export default Mermaid
