import React from "react"
import { Code, FileText, Search } from "lucide-react"

type StarterPrompt = {
  icon: React.ReactNode
  title: string
  description: string
  system_prompt: string
  user_prompt: string
  keywords: string[]
}

const STARTER_PROMPTS: StarterPrompt[] = [
  {
    icon: <Code className="size-5 text-primary" />,
    title: "Code Review Assistant",
    description: "Reviews code for bugs, style, and best practices",
    system_prompt:
      "You are an expert code reviewer. Analyze code for bugs, performance issues, security vulnerabilities, and adherence to best practices. Provide specific, actionable feedback with line references.",
    user_prompt: "Review the following code:\n\n{{code}}",
    keywords: ["code", "review", "development"],
  },
  {
    icon: <FileText className="size-5 text-primary" />,
    title: "Meeting Summary",
    description: "Extracts key points and action items from meeting notes",
    system_prompt:
      "You are a professional meeting summarizer. Extract key decisions, action items with owners, open questions, and important discussion points. Format the output clearly with sections.",
    user_prompt:
      "Summarize the following meeting notes:\n\n{{meeting_notes}}",
    keywords: ["meeting", "summary", "notes"],
  },
  {
    icon: <Search className="size-5 text-primary" />,
    title: "Research Analyst",
    description: "Analyzes topics with structured research methodology",
    system_prompt:
      "You are a thorough research analyst. When given a topic, provide a balanced analysis covering key facts, different perspectives, recent developments, and areas of uncertainty. Cite reasoning clearly.",
    user_prompt: "Research and analyze the following topic:\n\n{{topic}}",
    keywords: ["research", "analysis", "study"],
  },
]

type Props = {
  onUse: (prompt: {
    name: string
    system_prompt: string
    user_prompt: string
    keywords: string[]
  }) => void
}

export const PromptStarterCards: React.FC<Props> = ({ onUse }) => {
  return (
    <div className="grid gap-3 sm:grid-cols-3" data-testid="prompt-starter-cards">
      {STARTER_PROMPTS.map((sp) => (
        <div
          key={sp.title}
          className="flex flex-col rounded-lg border border-border bg-surface p-4 transition-colors hover:border-primary/40"
        >
          <div className="mb-2 flex items-center gap-2">
            {sp.icon}
            <h4 className="text-sm font-medium text-text">{sp.title}</h4>
          </div>
          <p className="mb-3 flex-1 text-xs text-text-muted">
            {sp.description}
          </p>
          <button
            type="button"
            onClick={() =>
              onUse({
                name: sp.title,
                system_prompt: sp.system_prompt,
                user_prompt: sp.user_prompt,
                keywords: sp.keywords,
              })
            }
            className="rounded bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20"
            data-testid={`starter-use-${sp.title.toLowerCase().replace(/\s+/g, "-")}`}
          >
            Use this template
          </button>
        </div>
      ))}
    </div>
  )
}
