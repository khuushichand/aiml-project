import { lazy } from "react"
import type { ReactElement } from "react"
import type { LucideIcon } from "lucide-react"
import {
  ActivityIcon,
  BookIcon,
  BookMarked,
  BookOpen,
  BookText,
  Bot,
  BrainCircuitIcon,
  CombineIcon,
  CpuIcon,
  Gauge,
  GitBranch,
  InfoIcon,
  OrbitIcon,
  ServerIcon,
  ShareIcon,
  Layers,
  StickyNote,
  Microscope,
  FlaskConical,
  MessageSquare,
  ClipboardList,
  MicIcon,
  Trash2,
  Table2,
  Library,
  ShieldCheck,
  Headphones,
  SquarePen,
  ImageIcon,
  SlidersHorizontal,
  FileText,
  Zap,
  Sparkles
} from "lucide-react"
import { ALL_TARGETS, type PlatformTarget } from "@/config/platform"
import { createSettingsRoute } from "./settings-route"
import { Navigate } from "react-router-dom"
import { DOCUMENT_WORKSPACE_PATH, REPO2TXT_PATH } from "@/routes/route-paths"

// Eagerly loaded routes for instant navigation on frequently visited pages
import OptionIndex from "./option-index"
import OptionChat from "./option-chat"
import OptionMediaMulti from "./option-media-multi"
import OptionMedia from "./option-media"

export type RouteKind = "options" | "sidepanel"

export type NavGroupKey = "server" | "knowledge" | "workspace" | "about"

type RouteNav = {
  group: NavGroupKey
  labelToken: string
  icon: LucideIcon
  order: number
  beta?: boolean
}

export type RouteDefinition = {
  kind: RouteKind
  path: string
  element: ReactElement
  targets?: PlatformTarget[]
  nav?: RouteNav
}
const OptionSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/general-settings"),
  "GeneralSettings"
)
const OptionModal = createSettingsRoute(
  () => import("~/components/Option/Models"),
  "ModelsBody"
)
const OptionPrompt = createSettingsRoute(
  () => import("~/components/Option/Settings/WorkspaceLinks"),
  "PromptWorkspaceSettings"
)
const OptionShare = createSettingsRoute(
  () => import("~/components/Option/Share"),
  "OptionShareBody"
)
const OptionProcessed = lazy(() => import("./option-settings-processed"))
const OptionHealth = lazy(() => import("./option-settings-health"))
const OptionMediaTrash = lazy(() => import("./option-media-trash"))
const OptionKnowledgeBase = createSettingsRoute(
  () => import("~/components/Option/Knowledge"),
  "KnowledgeSettings"
)
const OptionAbout = createSettingsRoute(
  () => import("~/components/Option/Settings/about"),
  "AboutApp"
)
const OptionChatbooks = createSettingsRoute(
  () => import("~/components/Option/Settings/chatbooks"),
  "ChatbooksSettings"
)
const SidepanelChat = lazy(() => import("./sidepanel-chat"))
const SidepanelSettings = lazy(() => import("./sidepanel-settings"))
const SidepanelAgent = lazy(() => import("./sidepanel-agent"))
const SidepanelPersona = lazy(() => import("./sidepanel-persona"))
const SidepanelErrorBoundaryTest = lazy(() => import("./sidepanel-error-boundary-test"))
const OptionRagSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/rag"),
  "RagSettings"
)
const OptionTldwSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/tldw"),
  "TldwSettings"
)
// OptionMedia and OptionMediaMulti are eagerly imported above
const OptionNotes = lazy(() => import("./option-notes"))
const OptionWorldBooks = createSettingsRoute(
  () => import("~/components/Option/Settings/WorkspaceLinks"),
  "WorldBooksWorkspaceSettings"
)
const OptionDictionaries = createSettingsRoute(
  () => import("~/components/Option/Settings/WorkspaceLinks"),
  "DictionariesWorkspaceSettings"
)
const OptionCharacters = createSettingsRoute(
  () => import("~/components/Option/Settings/WorkspaceLinks"),
  "CharactersWorkspaceSettings"
)
const OptionWorldBooksWorkspace = lazy(() => import("./option-world-books"))
const OptionDictionariesWorkspace = lazy(() => import("./option-dictionaries"))
const OptionCharactersWorkspace = lazy(() => import("./option-characters"))
const OptionPromptsWorkspace = lazy(() => import("./option-prompts"))
const OptionKnowledgeWorkspace = lazy(() => import("./option-knowledge"))
const OptionFlashcards = lazy(() => import("./option-flashcards"))
const OptionTts = lazy(() => import("./option-tts"))
const OptionEvaluations = lazy(() => import("./option-evaluations"))
const OptionStt = lazy(() => import("./option-stt"))
const OptionSpeech = lazy(() => import("./option-speech"))
const OptionSettingsEvaluations = createSettingsRoute(
  () => import("~/components/Option/Settings/evaluations"),
  "EvaluationsSettings"
)
const OptionSpeechSettings = createSettingsRoute(
  () => import("@/components/Option/Settings/SpeechSettings"),
  "SpeechSettings"
)
const OptionImageGenerationSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/ImageGenerationSettings"),
  "ImageGenerationSettings"
)
// Note: OptionPromptStudio has been unified with OptionPromptsWorkspace (/prompts)
// The /prompt-studio route now redirects to /prompts?tab=studio
const OptionSettingsPromptStudio = createSettingsRoute(
  () => import("~/components/Option/Settings/prompt-studio"),
  "PromptStudioSettings"
)
const OptionAdminServer = lazy(() => import("./option-admin-server"))
const OptionAdminLlamacpp = lazy(() => import("./option-admin-llamacpp"))
const OptionAdminMlx = lazy(() => import("./option-admin-mlx"))
const OptionChatSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/ChatSettings"),
  "ChatSettings"
)
const OptionUiCustomization = createSettingsRoute(
  () => import("~/components/Option/Settings/ui-customization"),
  "UiCustomizationSettings"
)
const OptionSplashSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/splash"),
  "SplashSettings"
)
const OptionQuickIngestSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/QuickIngestSettings"),
  "QuickIngestSettings"
)
const OptionQuickChatPopout = lazy(() => import("./option-quick-chat-popout"))
const OptionContentReview = lazy(() => import("./option-content-review"))
const OptionChunkingPlayground = lazy(() => import("./option-chunking-playground"))
const OptionDocumentation = lazy(() => import("./option-documentation"))
const OptionQuiz = lazy(() => import("./option-quiz"))
const OptionWritingPlayground = lazy(() => import("./option-writing-playground"))
const OptionDocumentWorkspace = lazy(() => import("./option-document-workspace"))
const OptionModelPlayground = lazy(() => import("./option-model-playground"))
const OptionModerationPlayground = lazy(() => import("./option-moderation-playground"))
const OptionFamilyGuardrailsWizard = lazy(
  () => import("./option-family-guardrails-wizard")
)
const OptionGuardianSettings = createSettingsRoute(
  () => import("~/components/Option/Settings/GuardianSettings"),
  "GuardianSettings"
)
const OptionChatbooksPlayground = lazy(() => import("./option-chatbooks-playground"))
const OptionWatchlists = lazy(() => import("./option-watchlists"))
const OptionKanbanPlayground = lazy(() => import("./option-kanban-playground"))
const OptionDataTables = lazy(() => import("./option-data-tables"))
const OptionCollections = lazy(() => import("./option-collections"))
const OptionSources = lazy(() => import("./option-sources"))
const OptionSourcesNew = lazy(() => import("./option-sources-new"))
const OptionSourcesDetail = lazy(() => import("./option-sources-detail"))
const OptionAdminSources = lazy(() => import("./option-admin-sources"))
const OptionAudiobookStudio = lazy(() => import("./option-audiobook-studio"))
const OptionChatWorkflows = lazy(() => import("./option-chat-workflows"))
const OptionWorkflowEditor = lazy(() => import("./option-workflow-editor"))
const OptionACPPlayground = lazy(() => import("./option-acp-playground"))
const OptionMcpHub = lazy(() => import("./option-mcp-hub"))
const OptionSkills = lazy(() => import("./option-skills"))
const OptionRepo2Txt = lazy(() => import("./option-repo2txt"))
const OptionSetup = lazy(() => import("./option-setup"))
const OptionOnboardingTest = lazy(() => import("./option-onboarding-test"))
const OptionWorkspacePlayground = lazy(() => import("./option-workspace-playground"))
// OptionChat is eagerly imported above

export const ROUTE_DEFINITIONS: RouteDefinition[] = [
  { kind: "options", path: "/", element: <OptionIndex /> },
  { kind: "options", path: "/setup", element: <OptionSetup /> },
  { kind: "options", path: "/chat", element: <OptionChat /> },
  {
    kind: "options",
    path: "/onboarding-test",
    element: <OptionOnboardingTest />,
    targets: ALL_TARGETS
  },
  {
    kind: "options",
    path: "/settings",
    element: <OptionSettings />,
    nav: {
      group: "server",
      labelToken: "settings:generalSettings.title",
      icon: OrbitIcon,
      order: 2
    }
  },
  {
    kind: "options",
    path: "/settings/tldw",
    element: <OptionTldwSettings />,
    nav: {
      group: "server",
      labelToken: "settings:tldw.serverNav",
      icon: ServerIcon,
      order: 1
    }
  },
  {
    kind: "options",
    path: "/settings/model",
    element: <OptionModal />,
    nav: {
      group: "server",
      labelToken: "settings:manageModels.title",
      icon: BrainCircuitIcon,
      order: 6
    }
  },
  {
    kind: "options",
    path: "/settings/mcp-hub",
    element: <OptionMcpHub />,
    nav: {
      group: "server",
      labelToken: "settings:mcpHubNav",
      icon: ServerIcon,
      order: 7
    }
  },
  {
    kind: "options",
    path: "/settings/prompt",
    element: <OptionPrompt />,
    nav: {
      group: "workspace",
      labelToken: "settings:managePrompts.title",
      icon: BookIcon,
      order: 6
    }
  },
  {
    kind: "options",
    path: "/settings/evaluations",
    element: <OptionSettingsEvaluations />,
    nav: {
      group: "server",
      labelToken: "settings:evaluationsSettings.title",
      icon: FlaskConical,
      order: 9,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/settings/chat",
    element: <OptionChatSettings />,
    nav: {
      group: "server",
      labelToken: "settings:chatSettingsNav",
      icon: MessageSquare,
      order: 3
    }
  },
  {
    kind: "options",
    path: "/settings/ui",
    element: <OptionUiCustomization />,
    nav: {
      group: "server",
      labelToken: "settings:uiCustomizationNav",
      icon: SlidersHorizontal,
      order: 3.5
    }
  },
  {
    kind: "options",
    path: "/settings/splash",
    element: <OptionSplashSettings />,
    nav: {
      group: "server",
      labelToken: "settings:splashSettingsNav",
      icon: Sparkles,
      order: 3.6
    }
  },
  {
    kind: "options",
    path: "/settings/quick-ingest",
    element: <OptionQuickIngestSettings />,
    nav: {
      group: "server",
      labelToken: "settings:quickIngestSettingsNav",
      icon: ClipboardList,
      order: 4
    }
  },
  {
    kind: "options",
    path: "/settings/speech",
    element: <OptionSpeechSettings />,
    nav: {
      group: "server",
      labelToken: "settings:speechSettingsNav",
      icon: MicIcon,
      order: 5
    }
  },
  {
    kind: "options",
    path: "/settings/image-generation",
    element: <OptionImageGenerationSettings />,
    nav: {
      group: "server",
      labelToken: "settings:imageGenerationSettingsNav",
      icon: ImageIcon,
      order: 7
    }
  },
  {
    kind: "options",
    path: "/settings/image-gen",
    element: <Navigate to="/settings/image-generation" replace />
  },
  {
    kind: "options",
    path: "/settings/share",
    element: <OptionShare />,
    nav: {
      group: "workspace",
      labelToken: "settings:manageShare.title",
      icon: ShareIcon,
      order: 7
    }
  },
  { kind: "options", path: "/settings/processed", element: <OptionProcessed /> },
  {
    kind: "options",
    path: "/settings/health",
    element: <OptionHealth />,
    nav: {
      group: "server",
      labelToken: "settings:healthNav",
      icon: ActivityIcon,
      order: 11
    }
  },
  {
    kind: "options",
    path: "/settings/prompt-studio",
    element: <OptionSettingsPromptStudio />,
    nav: {
      group: "server",
      labelToken: "settings:promptStudio.nav",
      icon: Microscope,
      order: 10,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/settings/knowledge",
    element: <OptionKnowledgeBase />,
    nav: {
      group: "knowledge",
      labelToken: "settings:manageKnowledge.title",
      icon: BookText,
      order: 1
    }
  },
  {
    kind: "options",
    path: "/settings/chatbooks",
    element: <OptionChatbooks />,
    nav: {
      group: "knowledge",
      labelToken: "settings:chatbooksNav",
      icon: BookText,
      order: 4
    }
  },
  {
    kind: "options",
    path: "/settings/characters",
    element: <OptionCharacters />,
    nav: {
      group: "knowledge",
      labelToken: "settings:charactersNav",
      icon: BookIcon,
      order: 5
    }
  },
  {
    kind: "options",
    path: "/settings/world-books",
    element: <OptionWorldBooks />,
    nav: {
      group: "knowledge",
      labelToken: "settings:worldBooksNav",
      icon: BookOpen,
      order: 2
    }
  },
  {
    kind: "options",
    path: "/settings/chat-dictionaries",
    element: <OptionDictionaries />,
    nav: {
      group: "knowledge",
      labelToken: "settings:chatDictionariesNav",
      icon: BookMarked,
      order: 3
    }
  },
  {
    kind: "options",
    path: "/settings/rag",
    element: <OptionRagSettings />,
    nav: {
      group: "server",
      labelToken: "settings:rag.title",
      icon: CombineIcon,
      order: 4
    }
  },
  { kind: "options", path: "/chunking-playground", element: <OptionChunkingPlayground /> },
  { kind: "options", path: "/documentation", element: <OptionDocumentation /> },
  {
    kind: "options",
    path: "/settings/about",
    element: <OptionAbout />,
    nav: {
      group: "about",
      labelToken: "settings:about.title",
      icon: InfoIcon,
      order: 1
    }
  },
  {
    kind: "options",
    path: "/review",
    element: <Navigate to="/media-multi" replace />
  },
  {
    kind: "options",
    path: "/flashcards",
    element: <OptionFlashcards />,
    nav: {
      group: "workspace",
      labelToken: "option:header.flashcards",
      icon: Layers,
      order: 4
    }
  },
  {
    kind: "options",
    path: "/quiz",
    element: <OptionQuiz />,
    targets: ALL_TARGETS,
    nav: {
      group: "workspace",
      labelToken: "option:header.quiz",
      icon: ClipboardList,
      order: 5,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/writing-playground",
    element: <OptionWritingPlayground />,
    nav: {
      group: "workspace",
      labelToken: "option:header.writingPlayground",
      icon: SquarePen,
      order: 6,
      beta: true
    }
  },
  {
    kind: "options",
    path: REPO2TXT_PATH,
    element: <OptionRepo2Txt />,
    nav: {
      group: "workspace",
      labelToken: "option:repo2txt.nav",
      icon: FileText,
      order: 7
    }
  },
  {
    kind: "options",
    path: "/model-playground",
    element: <OptionModelPlayground />,
    nav: {
      group: "workspace",
      labelToken: "settings:modelPlaygroundNav",
      icon: FlaskConical,
      order: 5,
      beta: true
    }
  },
  { kind: "options", path: "/chatbooks", element: <OptionChatbooksPlayground /> },
  { kind: "options", path: "/watchlists", element: <OptionWatchlists /> },
  { kind: "options", path: "/kanban", element: <OptionKanbanPlayground /> },
  {
    kind: "options",
    path: "/data-tables",
    element: <OptionDataTables />,
    nav: {
      group: "workspace",
      labelToken: "option:header.dataTables",
      icon: Table2,
      order: 8,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/collections",
    element: <OptionCollections />,
    nav: {
      group: "workspace",
      labelToken: "option:header.collections",
      icon: Library,
      order: 9,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/sources",
    element: <OptionSources />,
    nav: {
      group: "workspace",
      labelToken: "option:header.sources",
      icon: Layers,
      order: 9.5,
      beta: true
    }
  },
  { kind: "options", path: "/sources/new", element: <OptionSourcesNew /> },
  { kind: "options", path: "/sources/:sourceId", element: <OptionSourcesDetail /> },
  { kind: "options", path: "/admin/sources", element: <OptionAdminSources /> },
  {
    kind: "options",
    path: "/media",
    element: <OptionMedia />,
    nav: {
      group: "knowledge",
      labelToken: "settings:mediaNav",
      icon: BookText,
      order: 6
    }
  },
  {
    kind: "options",
    path: "/media-trash",
    element: <OptionMediaTrash />,
    nav: {
      group: "knowledge",
      labelToken: "settings:mediaTrashNav",
      icon: Trash2,
      order: 7
    }
  },
  {
    kind: "options",
    path: "/media-multi",
    element: <OptionMediaMulti />,
    nav: {
      group: "workspace",
      labelToken: "option:header.libraryView",
      icon: Microscope,
      order: 1
    }
  },
  {
    kind: "options",
    path: "/content-review",
    element: <OptionContentReview />,
    nav: {
      group: "workspace",
      labelToken: "option:header.contentReview",
      icon: BookText,
      order: 2
    }
  },
  {
    kind: "options",
    path: "/notes",
    element: <OptionNotes />,
    nav: {
      group: "workspace",
      labelToken: "option:header.notes",
      icon: StickyNote,
      order: 3
    }
  },
  { kind: "options", path: "/knowledge", element: <OptionKnowledgeWorkspace /> },
  { kind: "options", path: "/knowledge/thread/:threadId", element: <OptionKnowledgeWorkspace /> },
  { kind: "options", path: "/knowledge/shared/:shareToken", element: <OptionKnowledgeWorkspace /> },
  { kind: "options", path: "/world-books", element: <OptionWorldBooksWorkspace /> },
  { kind: "options", path: "/dictionaries", element: <OptionDictionariesWorkspace /> },
  { kind: "options", path: "/characters", element: <OptionCharactersWorkspace /> },
  { kind: "options", path: "/prompts", element: <OptionPromptsWorkspace /> },
  // Legacy route - redirect to unified Prompts page
  { kind: "options", path: "/prompt-studio", element: <Navigate to="/prompts?tab=studio" replace /> },
  { kind: "options", path: "/tts", element: <OptionTts /> },
  { kind: "options", path: "/stt", element: <OptionStt /> },
  { kind: "options", path: "/speech", element: <OptionSpeech /> },
  { kind: "options", path: "/evaluations", element: <OptionEvaluations /> },
  {
    kind: "options",
    path: "/audiobook-studio",
    element: <OptionAudiobookStudio />,
    nav: {
      group: "workspace",
      labelToken: "option:header.audiobookStudio",
      icon: Headphones,
      order: 10,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/chat-workflows",
    element: <OptionChatWorkflows />,
    nav: {
      group: "workspace",
      labelToken: "option:header.chatWorkflows",
      icon: ClipboardList,
      order: 10.5,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/workflow-editor",
    element: <OptionWorkflowEditor />,
    nav: {
      group: "workspace",
      labelToken: "option:header.workflowEditor",
      icon: GitBranch,
      order: 11,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/acp-playground",
    element: <OptionACPPlayground />,
    nav: {
      group: "workspace",
      labelToken: "settings:acpPlaygroundNav",
      icon: Bot,
      order: 12,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/mcp-hub",
    element: <OptionMcpHub />,
    nav: {
      group: "workspace",
      labelToken: "settings:mcpHubNav",
      icon: Bot,
      order: 12.5,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/skills",
    element: <OptionSkills />,
    nav: {
      group: "workspace",
      labelToken: "settings:skillsNav",
      icon: Zap,
      order: 13,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/workspace-playground",
    element: <OptionWorkspacePlayground />,
    nav: {
      group: "workspace",
      labelToken: "settings:researchStudioNav",
      icon: FlaskConical,
      order: 0,
      beta: true
    }
  },
  {
    kind: "options",
    path: DOCUMENT_WORKSPACE_PATH,
    element: <OptionDocumentWorkspace />,
    nav: {
      group: "workspace",
      labelToken: "option:header.documentWorkspace",
      icon: FileText,
      order: 1,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/moderation-playground",
    element: <OptionModerationPlayground />,
    targets: ALL_TARGETS,
    nav: {
      group: "server",
      labelToken: "option:moderationPlayground.nav",
      icon: ShieldCheck,
      order: 10
    }
  },
  {
    kind: "options",
    path: "/settings/family-guardrails",
    element: <OptionFamilyGuardrailsWizard />,
    nav: {
      group: "server",
      labelToken: "settings:familyGuardrailsWizardNav",
      icon: ShieldCheck,
      order: 8,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/settings/guardian",
    element: <OptionGuardianSettings />,
    nav: {
      group: "server",
      labelToken: "settings:guardianNav",
      icon: ShieldCheck,
      order: 9,
      beta: true
    }
  },
  {
    kind: "options",
    path: "/admin/server",
    element: <OptionAdminServer />,
    targets: ALL_TARGETS
  },
  {
    kind: "options",
    path: "/admin/llamacpp",
    element: <OptionAdminLlamacpp />,
    targets: ALL_TARGETS,
    nav: {
      group: "server",
      labelToken: "option:header.adminLlamacpp",
      icon: CpuIcon,
      order: 7
    }
  },
  {
    kind: "options",
    path: "/admin/mlx",
    element: <OptionAdminMlx />,
    targets: ALL_TARGETS,
    nav: {
      group: "server",
      labelToken: "option:header.adminMlx",
      icon: Gauge,
      order: 8
    }
  },
  {
    kind: "options",
    path: "/quick-chat-popout",
    element: <OptionQuickChatPopout />,
    targets: ALL_TARGETS
  },
  { kind: "sidepanel", path: "/", element: <SidepanelChat /> },
  {
    kind: "sidepanel",
    path: "/agent",
    element: <SidepanelAgent />,
    targets: ALL_TARGETS
  },
  {
    kind: "sidepanel",
    path: "/persona",
    element: <SidepanelPersona />,
    targets: ALL_TARGETS
  },
  { kind: "sidepanel", path: "/settings", element: <SidepanelSettings /> },
  {
    kind: "sidepanel",
    path: "/error-boundary-test",
    element: <SidepanelErrorBoundaryTest />,
    targets: ALL_TARGETS
  }
]

export const optionRoutes = ROUTE_DEFINITIONS.filter(
  (route) => route.kind === "options"
)

export const sidepanelRoutes = ROUTE_DEFINITIONS.filter(
  (route) => route.kind === "sidepanel"
)
