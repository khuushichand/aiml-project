import type { LucideIcon } from "lucide-react"
import {
  BrainCircuit,
  BookMarked,
  BookOpen,
  BookText,
  Bot,
  ClipboardList,
  CogIcon,
  CombineIcon,
  FileSearch,
  FileText,
  FlaskConical,
  Gauge,
  GitCompare,
  Headphones,
  Kanban,
  Layers,
  LayoutGrid,
  Library,
  ListTodo,
  MessageSquare,
  Mic,
  Microscope,
  NotebookPen,
  Rss,
  Scissors,
  ShieldCheck,
  SquarePen,
  StickyNote,
  UserCircle2,
  Volume2,
  Table2,
  Workflow,
  Zap
} from "lucide-react"
import type { HeaderShortcutId } from "@/services/settings/ui-settings"
import { DOCUMENT_WORKSPACE_PATH, REPO2TXT_PATH } from "@/routes/route-paths"
import { isHostedTldwDeployment } from "@/services/tldw/deployment-mode"

export type HeaderShortcutItem = {
  id: HeaderShortcutId
  to: string
  icon: LucideIcon
  labelKey: string
  labelDefault: string
  /** Optional 1-9 index for ⌘+number shortcut when the launcher is open */
  shortcutIndex?: number
}

export type HeaderShortcutGroup = {
  id: string
  titleKey: string
  titleDefault: string
  items: HeaderShortcutItem[]
}

const BASE_HEADER_SHORTCUT_GROUPS: HeaderShortcutGroup[] = [
  {
    id: "chat-persona",
    titleKey: "option:header.groupChatPersona",
    titleDefault: "Chat & Persona",
    items: [
      {
        id: "chat",
        to: "/chat",
        icon: MessageSquare,
        labelKey: "option:header.modePlayground",
        labelDefault: "Chat",
        shortcutIndex: 1
      },
      {
        id: "prompts",
        to: "/prompts",
        icon: NotebookPen,
        labelKey: "option:header.modePromptsPlayground",
        labelDefault: "Prompts",
        shortcutIndex: 2
      },
      {
        id: "characters",
        to: "/characters",
        icon: UserCircle2,
        labelKey: "option:header.modeCharacters",
        labelDefault: "Characters",
        shortcutIndex: 4
      },
      {
        id: "chat-dictionaries",
        to: "/dictionaries",
        icon: BookMarked,
        labelKey: "option:header.modeDictionaries",
        labelDefault: "Chat Dictionaries",
        shortcutIndex: 5
      },
      {
        id: "world-books",
        to: "/world-books",
        icon: BookOpen,
        labelKey: "option:header.modeWorldBooks",
        labelDefault: "World Books",
        shortcutIndex: 6
      },
      {
        id: "model-playground",
        to: "/model-playground",
        icon: FlaskConical,
        labelKey: "settings:modelPlaygroundNav",
        labelDefault: "Model Playground"
      }
    ]
  },
  {
    id: "research",
    titleKey: "option:header.groupResearch",
    titleDefault: "Research",
    items: [
      {
        id: "prompt-studio",
        to: "/prompt-studio",
        icon: NotebookPen,
        labelKey: "option:header.modePromptStudio",
        labelDefault: "Prompt Studio",
        shortcutIndex: 3
      },
      {
        id: "deep-research",
        to: "/research",
        icon: BrainCircuit,
        labelKey: "option:header.deepResearch",
        labelDefault: "Deep Research"
      },
      {
        id: "workspace-playground",
        to: "/workspace-playground",
        icon: GitCompare,
        labelKey: "settings:researchStudioNav",
        labelDefault: "Research Studio",
        shortcutIndex: 7
      },
      {
        id: "knowledge-qa",
        to: "/knowledge",
        icon: CombineIcon,
        labelKey: "option:header.modeKnowledge",
        labelDefault: "Knowledge QA",
        shortcutIndex: 8
      },
      {
        id: "document-workspace",
        to: DOCUMENT_WORKSPACE_PATH,
        icon: FileSearch,
        labelKey: "option:header.documentWorkspace",
        labelDefault: "Document Workspace"
      },
      {
        id: "repo2txt",
        to: REPO2TXT_PATH,
        icon: FileText,
        labelKey: "option:repo2txt.nav",
        labelDefault: "Repo2Txt"
      },
      {
        id: "evaluations",
        to: "/evaluations",
        icon: Microscope,
        labelKey: "option:header.evaluations",
        labelDefault: "Evaluations"
      }
    ]
  },
  {
    id: "library",
    titleKey: "option:header.groupLibrary",
    titleDefault: "Library",
    items: [
      {
        id: "media",
        to: "/media",
        icon: BookText,
        labelKey: "option:header.media",
        labelDefault: "Media",
        shortcutIndex: 9
      },
      {
        id: "multi-item-review",
        to: "/media-multi",
        icon: LayoutGrid,
        labelKey: "option:header.libraryView",
        labelDefault: "Multi-Item Review"
      },
      {
        id: "collections",
        to: "/collections",
        icon: Library,
        labelKey: "option:header.modeCollections",
        labelDefault: "Collections"
      },
      {
        id: "watchlists",
        to: "/watchlists",
        icon: Rss,
        labelKey: "option:header.modeWatchlists",
        labelDefault: "Watchlists"
      },
      {
        id: "notes",
        to: "/notes",
        icon: StickyNote,
        labelKey: "option:header.notes",
        labelDefault: "Notes"
      }
    ]
  },
  {
    id: "creation",
    titleKey: "option:header.groupCreationWorkspace",
    titleDefault: "Creation",
    items: [
      {
        id: "writing-playground",
        to: "/writing-playground",
        icon: SquarePen,
        labelKey: "option:header.writingPlayground",
        labelDefault: "Writing Playground"
      },
      {
        id: "data-tables",
        to: "/data-tables",
        icon: Table2,
        labelKey: "option:header.dataTables",
        labelDefault: "Data Tables"
      },
      {
        id: "stt-playground",
        to: "/stt",
        icon: Mic,
        labelKey: "option:header.modeStt",
        labelDefault: "STT Playground"
      },
      {
        id: "tts-playground",
        to: "/tts",
        icon: Volume2,
        labelKey: "option:tts.playground",
        labelDefault: "TTS Playground"
      },
      {
        id: "audiobook-studio",
        to: "/audiobook-studio",
        icon: Headphones,
        labelKey: "option:header.audiobookStudio",
        labelDefault: "Audiobook Studio"
      },
      {
        id: "presentation-studio",
        to: "/presentation-studio",
        icon: FileText,
        labelKey: "option:header.presentationStudio",
        labelDefault: "Presentation Studio"
      }
    ]
  },
  {
    id: "planning-learning",
    titleKey: "option:header.groupPlanningLearning",
    titleDefault: "Planning & Learning",
    items: [
      {
        id: "kanban-playground",
        to: "/kanban",
        icon: Kanban,
        labelKey: "option:header.modeKanban",
        labelDefault: "Kanban Playground"
      },
      {
        id: "flashcards",
        to: "/flashcards",
        icon: Layers,
        labelKey: "option:header.flashcards",
        labelDefault: "Flashcards"
      },
      {
        id: "quizzes",
        to: "/quiz",
        icon: ClipboardList,
        labelKey: "option:header.quiz",
        labelDefault: "Quizzes"
      }
    ]
  },
  {
    id: "automation-agents",
    titleKey: "option:header.groupAutomationAgents",
    titleDefault: "Automation & Agents",
    items: [
      {
        id: "workflows",
        to: "/workflow-editor",
        icon: Workflow,
        labelKey: "option:header.workflows",
        labelDefault: "Workflows"
      },
      {
        id: "integrations",
        to: "/integrations",
        icon: Bot,
        labelKey: "option:header.integrations",
        labelDefault: "Integrations"
      },
      {
        id: "scheduled-tasks",
        to: "/scheduled-tasks",
        icon: ListTodo,
        labelKey: "option:header.scheduledTasks",
        labelDefault: "Scheduled Tasks"
      },
      {
        id: "acp-playground",
        to: "/acp-playground",
        icon: Bot,
        labelKey: "option:header.acpPlayground",
        labelDefault: "ACP Playground"
      },
      {
        id: "skills",
        to: "/skills",
        icon: Zap,
        labelKey: "settings:skillsNav",
        labelDefault: "Skills"
      }
    ]
  },
  {
    id: "tools",
    titleKey: "option:header.groupTools",
    titleDefault: "Tools",
    items: [
      {
        id: "chatbooks-playground",
        to: "/chatbooks",
        icon: BookOpen,
        labelKey: "option:header.chatbooksPlayground",
        labelDefault: "Chatbooks Playground"
      },
      {
        id: "chunking-playground",
        to: "/chunking-playground",
        icon: Scissors,
        labelKey: "settings:chunkingPlayground.nav",
        labelDefault: "Chunking Playground"
      },
      {
        id: "moderation-playground",
        to: "/moderation-playground",
        icon: ShieldCheck,
        labelKey: "option:moderationPlayground.nav",
        labelDefault: "Moderation Playground"
      }
    ]
  },
  {
    id: "admin",
    titleKey: "option:header.groupAdminHelp",
    titleDefault: "Admin & Help",
    items: [
      {
        id: "admin-server",
        to: "/admin/server",
        icon: CogIcon,
        labelKey: "option:header.adminServer",
        labelDefault: "Server Admin"
      },
      {
        id: "admin-integrations",
        to: "/admin/integrations",
        icon: CombineIcon,
        labelKey: "option:header.adminIntegrations",
        labelDefault: "Workspace Integrations"
      },
      {
        id: "admin-llamacpp",
        to: "/admin/llamacpp",
        icon: Microscope,
        labelKey: "option:header.adminLlamacpp",
        labelDefault: "Llama.cpp Admin"
      },
      {
        id: "admin-mlx",
        to: "/admin/mlx",
        icon: Gauge,
        labelKey: "option:header.adminMlx",
        labelDefault: "MLX LM Admin"
      },
      {
        id: "settings",
        to: "/settings",
        icon: CogIcon,
        labelKey: "settings",
        labelDefault: "Settings"
      },
      {
        id: "documentation",
        to: "/documentation",
        icon: FileText,
        labelKey: "option:header.modeDocumentation",
        labelDefault: "Documentation"
      }
    ]
  }
]

const HOSTED_VISIBLE_SHORTCUT_PATHS = new Set([
  "/chat",
  "/knowledge",
  "/media",
  "/collections"
])

const getHostedHeaderShortcutGroups = (): HeaderShortcutGroup[] => {
  const filteredGroups = BASE_HEADER_SHORTCUT_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => HOSTED_VISIBLE_SHORTCUT_PATHS.has(item.to))
  })).filter((group) => group.items.length > 0)

  filteredGroups.push({
    id: "account-help",
    titleKey: "option:header.groupAccountHelp",
    titleDefault: "Account & Billing",
    items: [
      {
        id: "account",
        to: "/account",
        icon: UserCircle2,
        labelKey: "option:header.account",
        labelDefault: "Account"
      },
      {
        id: "billing",
        to: "/billing",
        icon: ClipboardList,
        labelKey: "option:header.billing",
        labelDefault: "Billing"
      }
    ]
  })

  return filteredGroups
}

export const getHeaderShortcutGroups = (): HeaderShortcutGroup[] =>
  isHostedTldwDeployment()
    ? getHostedHeaderShortcutGroups()
    : BASE_HEADER_SHORTCUT_GROUPS

export const getHeaderShortcutItems = (): HeaderShortcutItem[] =>
  getHeaderShortcutGroups().flatMap((group) => group.items)

export const normalizeHeaderShortcutSelection = (
  selection: HeaderShortcutId[]
): HeaderShortcutItem[] => {
  const selected = new Set(selection)
  return getHeaderShortcutItems().filter((item) => selected.has(item.id))
}
