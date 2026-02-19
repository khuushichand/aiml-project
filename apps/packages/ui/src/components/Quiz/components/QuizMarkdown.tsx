import React from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { MarkdownErrorBoundary } from "@/components/Common/MarkdownErrorBoundary"

interface QuizMarkdownProps {
  content: string
  className?: string
}

/**
 * Lightweight markdown renderer for quiz question/explanation surfaces.
 * Uses react-markdown defaults (HTML escaped by default) plus GFM syntax.
 */
export const QuizMarkdown: React.FC<QuizMarkdownProps> = ({
  content,
  className = ""
}) => (
  <MarkdownErrorBoundary fallbackText={content}>
    <div className={`prose prose-sm max-w-none break-words dark:prose-invert ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            />
          ),
          img: ({ ...props }) => (
            <img
              {...props}
              alt={props.alt || "Quiz markdown image"}
              className="max-h-64 w-auto rounded border border-border"
              loading="lazy"
            />
          )
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  </MarkdownErrorBoundary>
)

export default QuizMarkdown

