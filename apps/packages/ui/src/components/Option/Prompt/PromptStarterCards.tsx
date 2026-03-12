import React from "react"
import { Code, FileText, Search } from "lucide-react"
import type { PromptFormat, StructuredPromptDefinition } from "@/db/dexie/types"
import {
  createStructuredPromptDefinition,
  renderStructuredPromptLegacySnapshot
} from "./structured-prompt-utils"

type StarterPrompt = {
  icon: React.ReactNode
  title: string
  description: string
  structuredPromptDefinition: StructuredPromptDefinition
  keywords: string[]
}

const STARTER_PROMPTS: StarterPrompt[] = [
  {
    icon: <Code className="size-5 text-primary" />,
    title: "Code Review Assistant",
    description: "Reviews code for bugs, style, and best practices",
    structuredPromptDefinition: createStructuredPromptDefinition({
      variables: [
        {
          name: "code",
          label: "Code",
          description: "The source code or diff to review.",
          required: true,
          input_type: "textarea"
        }
      ],
      blocks: [
        {
          id: "role",
          name: "Role",
          role: "system",
          content:
            "You are an expert code reviewer. Deliver precise, actionable feedback."
        },
        {
          id: "review-focus",
          name: "Review Focus",
          role: "developer",
          content:
            "Check for correctness, regressions, security risks, performance issues, maintainability, and missing tests. Call out the most important findings first and cite exact evidence when possible."
        },
        {
          id: "task",
          name: "Task",
          role: "user",
          content: "Review the following code:\n\n{{code}}",
          is_template: true
        }
      ]
    }),
    keywords: ["code", "review", "development"],
  },
  {
    icon: <FileText className="size-5 text-primary" />,
    title: "Meeting Summary",
    description: "Extracts key points and action items from meeting notes",
    structuredPromptDefinition: createStructuredPromptDefinition({
      variables: [
        {
          name: "meeting_notes",
          label: "Meeting notes",
          description: "Raw meeting notes or transcript text.",
          required: true,
          input_type: "textarea"
        }
      ],
      blocks: [
        {
          id: "role",
          name: "Role",
          role: "system",
          content:
            "You are a professional meeting summarizer who extracts decisions and next steps."
        },
        {
          id: "output-format",
          name: "Output Format",
          role: "developer",
          content:
            "Return sections for key decisions, action items with owners, open questions, and notable discussion points."
        },
        {
          id: "task",
          name: "Task",
          role: "user",
          content: "Summarize the following meeting notes:\n\n{{meeting_notes}}",
          is_template: true
        }
      ]
    }),
    keywords: ["meeting", "summary", "notes"],
  },
  {
    icon: <Search className="size-5 text-primary" />,
    title: "Research Analyst",
    description: "Analyzes topics with structured research methodology",
    structuredPromptDefinition: createStructuredPromptDefinition({
      variables: [
        {
          name: "topic",
          label: "Topic",
          description: "The subject to research and analyze.",
          required: true,
          input_type: "text"
        }
      ],
      blocks: [
        {
          id: "role",
          name: "Role",
          role: "system",
          content:
            "You are a thorough research analyst who produces balanced, evidence-aware analysis."
        },
        {
          id: "analysis-frame",
          name: "Analysis Frame",
          role: "developer",
          content:
            "Cover the key facts, competing perspectives, recent developments, and the main uncertainties or gaps in the evidence."
        },
        {
          id: "task",
          name: "Task",
          role: "user",
          content: "Research and analyze the following topic:\n\n{{topic}}",
          is_template: true
        }
      ]
    }),
    keywords: ["research", "analysis", "study"],
  },
]

type Props = {
  onUse: (prompt: {
    name: string
    system_prompt: string
    user_prompt: string
    keywords: string[]
    promptFormat?: PromptFormat
    promptSchemaVersion?: number
    structuredPromptDefinition?: StructuredPromptDefinition
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
            onClick={() => {
              const legacySnapshot = renderStructuredPromptLegacySnapshot(
                sp.structuredPromptDefinition
              )
              onUse({
                name: sp.title,
                system_prompt: legacySnapshot.systemPrompt,
                user_prompt: legacySnapshot.userPrompt,
                keywords: sp.keywords,
                promptFormat: "structured",
                promptSchemaVersion: 1,
                structuredPromptDefinition: sp.structuredPromptDefinition
              })
            }}
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
