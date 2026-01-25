import "katex/dist/katex.min.css"

import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import { Highlight } from "prism-react-renderer"

import "property-information"
import React from "react"
import { CodeBlock } from "./CodeBlock"
import { TableBlock } from "./TableBlock"
import { preprocessLaTeX } from "@/utils/latex"
import { useStorage } from "@plasmohq/storage/hook"
import { highlightText } from "@/utils/text-highlight"
import { DEFAULT_CHAT_SETTINGS } from "@/types/chat-settings"
import { normalizeLanguage, resolveTheme, safeLanguage } from "@/utils/code-theme"

function Markdown({
  message,
  className = "prose break-words dark:prose-invert prose-p:leading-relaxed prose-pre:p-0 dark:prose-dark",
  searchQuery,
  codeBlockVariant = "default",
  allowExternalImages,
}: {
  message: string
  className?: string
  searchQuery?: string
  codeBlockVariant?: "default" | "plain" | "compact"
  allowExternalImages?: boolean
}) {
  const [checkWideMode] = useStorage("checkWideMode", false)
  const [codeTheme] = useStorage("codeTheme", "auto")
  const [allowExternalImagesSetting] = useStorage("allowExternalImages", DEFAULT_CHAT_SETTINGS.allowExternalImages)
  const blockIndexRef = React.useRef(0)
  // Reset index each render pass to assign sequential indices to code blocks.
  blockIndexRef.current = 0
  const resolvedClassName = React.useMemo(() => {
    if (!checkWideMode) return className
    return `${className} max-w-none`
  }, [checkWideMode, className])
  const resolvedAllowExternalImages = typeof allowExternalImages === "boolean" ? allowExternalImages : allowExternalImagesSetting
  const paragraphClass = codeBlockVariant === "plain" || codeBlockVariant === "compact" ? "mb-2 last:mb-0 whitespace-pre-wrap" : "mb-2 last:mb-0"
  const renderHighlightedChildren = React.useCallback(
    (children: React.ReactNode): React.ReactNode => {
      if (!searchQuery) return children
      return React.Children.map(children, (child) => {
        if (typeof child === "string") {
          return highlightText(child, searchQuery)
        }
        if (React.isValidElement(child) && child.props?.children) {
          const nextChildren = renderHighlightedChildren(child.props.children)
          if (nextChildren === child.props.children) return child
          return React.cloneElement(child, { ...child.props }, nextChildren)
        }
        return child
      })
    },
    [searchQuery],
  )
  const processedMessage = React.useMemo(() => preprocessLaTeX(message), [message])
  return (
    <React.Fragment>
      <ReactMarkdown
        className={resolvedClassName}
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          pre({ children, ...props }) {
            const childArray = React.Children.toArray(children)
            const codeChild = childArray.find((child) => React.isValidElement(child) && child.type === "code") as React.ReactElement | undefined

            if (!codeChild) {
              return <pre {...props}>{children}</pre>
            }

            const codeClassName = codeChild.props?.className as string | undefined
            const match = /language-(\w+)/.exec(codeClassName || "")
            const blockIndex = blockIndexRef.current++
            const value = String(codeChild.props?.children ?? "").replace(/\n$/, "")

            if (codeBlockVariant === "plain") {
              return <div className="my-2 rounded-lg border border-border bg-surface2/70 px-3 py-2 text-xs font-mono leading-relaxed text-text whitespace-pre overflow-x-auto">{value}</div>
            }
            if (codeBlockVariant === "compact") {
              const rawLanguage = match ? match[1] : ""
              const normalizedLanguage = normalizeLanguage(rawLanguage)
              const highlightLanguage = rawLanguage ? normalizedLanguage : "markdown"
              return (
                <div className="not-prose my-2 rounded-lg border border-border bg-surface2/70 px-3 py-2 overflow-x-auto">
                  <Highlight code={value} language={safeLanguage(highlightLanguage)} theme={resolveTheme(codeTheme || "dracula")}>
                    {({ className: highlightClassName, style, tokens, getLineProps, getTokenProps }) => (
                      <pre
                        className={`${highlightClassName} m-0 text-xs font-mono leading-relaxed`}
                        style={{
                          ...style,
                          backgroundColor: "transparent",
                          fontFamily: "var(--font-mono)",
                        }}
                      >
                        {tokens.map((line, i) => (
                          <div key={i} {...getLineProps({ line, key: i })}>
                            {line.map((token, key) => (
                              <span key={key} {...getTokenProps({ token, key })} />
                            ))}
                          </div>
                        ))}
                      </pre>
                    )}
                  </Highlight>
                </div>
              )
            }
            return <CodeBlock language={match ? match[1] : ""} value={value} blockIndex={blockIndex} />
          },
          code({ className, children, ...props }) {
            const mergedClassName = className ? `${className} font-semibold` : "font-semibold"
            return (
              <code className={mergedClassName} {...props}>
                {children}
              </code>
            )
          },
          a({ ...props }) {
            return (
              <a target="_blank" rel="noopener noreferrer" className="text-blue-500 text-sm hover:underline" {...props}>
                {props.children}
              </a>
            )
          },
          img({ src, alt }) {
            const resolvedSrc = typeof src === "string" ? src : ""
            const isExternal = /^https?:\/\//i.test(resolvedSrc) || /^\/\/[^/]/.test(resolvedSrc)
            const isAllowed = !isExternal || resolvedAllowExternalImages
            if (!resolvedSrc) return null
            if (!isAllowed) {
              return (
                <span className="inline-flex items-center gap-2 rounded-md border border-border bg-surface2 px-2 py-1 text-[11px] text-text-muted">
                  <span>{alt ? `Image: ${alt}` : "External image blocked"}</span>
                  <a href={resolvedSrc} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    Open
                  </a>
                </span>
              )
            }
            return <img src={resolvedSrc} alt={alt || ""} loading="lazy" referrerPolicy="no-referrer" className="my-2 max-w-full rounded-md border border-border" />
          },
          table({ children }) {
            return <TableBlock>{children}</TableBlock>
          },
          p({ children, className, ...props }) {
            const content = renderHighlightedChildren(children)
            const mergedClassName = [paragraphClass, className].filter(Boolean).join(" ")
            return (
              <p className={mergedClassName} {...props}>
                {content}
              </p>
            )
          },
          li({ children, ...props }) {
            return <li {...props}>{renderHighlightedChildren(children)}</li>
          },
          td({ children, ...props }) {
            return <td {...props}>{renderHighlightedChildren(children)}</td>
          },
          th({ children, ...props }) {
            return <th {...props}>{renderHighlightedChildren(children)}</th>
          },
          h1({ children, ...props }) {
            return <h1 {...props}>{renderHighlightedChildren(children)}</h1>
          },
          h2({ children, ...props }) {
            return <h2 {...props}>{renderHighlightedChildren(children)}</h2>
          },
          h3({ children, ...props }) {
            return <h3 {...props}>{renderHighlightedChildren(children)}</h3>
          },
          h4({ children, ...props }) {
            return <h4 {...props}>{renderHighlightedChildren(children)}</h4>
          },
          h5({ children, ...props }) {
            return <h5 {...props}>{renderHighlightedChildren(children)}</h5>
          },
          h6({ children, ...props }) {
            return <h6 {...props}>{renderHighlightedChildren(children)}</h6>
          },
        }}
      >
        {processedMessage}
      </ReactMarkdown>
    </React.Fragment>
  )
}

export default Markdown
