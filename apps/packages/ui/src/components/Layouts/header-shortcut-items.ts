import type { LucideIcon } from "lucide-react"
import {
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
  Workflow
} from "lucide-react"
import type { HeaderShortcutId } from "@/services/settings/ui-settings"
import { DOCUMENT_WORKSPACE_PATH } from "@/routes/route-paths"

export type HeaderShortcutItem = {
  id: HeaderShortcutId
  to: string
  icon: LucideIcon
  labelKey: string
  labelDefault: string
}

export type HeaderShortcutGroup = {
  id: string
  titleKey: string
  titleDefault: string
  items: HeaderShortcutItem[]
}

export const HEADER_SHORTCUT_GROUPS: HeaderShortcutGroup[] = [
  {
    id: "chat",
    titleKey: "option:header.groupChat",
    titleDefault: "Chat & Characters",
    items: [
      {
        id: "chat",
        to: "/",
        icon: MessageSquare,
        labelKey: "option:header.modePlayground",
        labelDefault: "Chat"
      },
      {
        id: "prompts",
        to: "/prompts",
        icon: NotebookPen,
        labelKey: "option:header.modePromptsPlayground",
        labelDefault: "Prompts"
      },
      {
        id: "characters",
        to: "/characters",
        icon: UserCircle2,
        labelKey: "option:header.modeCharacters",
        labelDefault: "Characters"
      },
      {
        id: "chat-dictionaries",
        to: "/dictionaries",
        icon: BookMarked,
        labelKey: "option:header.modeDictionaries",
        labelDefault: "Chat dictionaries"
      },
      {
        id: "world-books",
        to: "/world-books",
        icon: BookOpen,
        labelKey: "option:header.modeWorldBooks",
        labelDefault: "World Books"
      },
      {
        id: "workspace-playground",
        to: "/workspace-playground",
        icon: GitCompare,
        labelKey: "option:header.modelPlayground",
        labelDefault: "Research Studio"
      }
    ]
  },
  {
    id: "library",
    titleKey: "option:header.groupLibrary",
    titleDefault: "Library & Research",
    items: [
      {
        id: "knowledge-qa",
        to: "/knowledge",
        icon: CombineIcon,
        labelKey: "option:header.modeKnowledge",
        labelDefault: "Knowledge QA"
      },
      {
        id: "media",
        to: "/media",
        icon: BookText,
        labelKey: "option:header.media",
        labelDefault: "Media"
      },
      {
        id: "document-workspace",
        to: DOCUMENT_WORKSPACE_PATH,
        icon: FileSearch,
        labelKey: "option:header.documentWorkspace",
        labelDefault: "Document Workspace"
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
      },
      {
        id: "chatbooks-playground",
        to: "/chatbooks",
        icon: BookOpen,
        labelKey: "option:header.chatbooksPlayground",
        labelDefault: "Chatbooks Playground"
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
      },
      {
        id: "evaluations",
        to: "/evaluations",
        icon: Microscope,
        labelKey: "option:header.evaluations",
        labelDefault: "Evaluations"
      },
      {
        id: "chunking-playground",
        to: "/chunking-playground",
        icon: Scissors,
        labelKey: "settings:chunkingPlayground.nav",
        labelDefault: "Chunking Playground"
      }
    ]
  },
  {
    id: "audio",
    titleKey: "option:header.groupAudio",
    titleDefault: "Audio & Speech",
    items: [
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
      }
    ]
  },
  {
    id: "creation",
    titleKey: "option:header.groupCreation",
    titleDefault: "Creation & Automation",
    items: [
      {
        id: "workflows",
        to: "/workflow-editor",
        icon: Workflow,
        labelKey: "option:header.workflows",
        labelDefault: "Workflows"
      },
      {
        id: "writing-playground",
        to: "/writing-playground",
        icon: SquarePen,
        labelKey: "option:header.writingPlayground",
        labelDefault: "Writing Playground"
      },
      {
        id: "acp-playground",
        to: "/acp-playground",
        icon: Bot,
        labelKey: "option:header.acpPlayground",
        labelDefault: "ACP Playground"
      },
      {
        id: "kanban-playground",
        to: "/kanban",
        icon: Kanban,
        labelKey: "option:header.modeKanban",
        labelDefault: "Kanban Playground"
      }
    ]
  },
  {
    id: "tools",
    titleKey: "option:header.groupTools",
    titleDefault: "Tools & Playgrounds",
    items: [
      {
        id: "model-playground",
        to: "/model-playground",
        icon: FlaskConical,
        labelKey: "option:header.workspacePlayground",
        labelDefault: "Model Playground"
      },
      {
        id: "data-tables",
        to: "/data-tables",
        icon: Table2,
        labelKey: "option:header.dataTables",
        labelDefault: "Data Tables"
      }
    ]
  },
  {
    id: "admin",
    titleKey: "option:header.groupAdmin",
    titleDefault: "Admin & Settings",
    items: [
      {
        id: "admin-server",
        to: "/admin/server",
        icon: CogIcon,
        labelKey: "option:header.adminServer",
        labelDefault: "Server Admin"
      },
      {
        id: "documentation",
        to: "/documentation",
        icon: FileText,
        labelKey: "option:header.modeDocumentation",
        labelDefault: "Documentation"
      },
      {
        id: "moderation-playground",
        to: "/moderation-playground",
        icon: ShieldCheck,
        labelKey: "option:moderationPlayground.nav",
        labelDefault: "Moderation Playground"
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
      }
    ]
  }
]

export const HEADER_SHORTCUT_ITEMS: HeaderShortcutItem[] =
  HEADER_SHORTCUT_GROUPS.flatMap((group) => group.items)

export const normalizeHeaderShortcutSelection = (
  selection: HeaderShortcutId[]
): HeaderShortcutItem[] => {
  const selected = new Set(selection)
  return HEADER_SHORTCUT_ITEMS.filter((item) => selected.has(item.id))
}
