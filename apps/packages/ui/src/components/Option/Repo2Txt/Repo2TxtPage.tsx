import { useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useStore } from "zustand"
import { AdvancedFilters } from "./components/AdvancedFilters"
import { FileTree } from "./components/FileTree"
import { OutputPanel } from "./components/OutputPanel"
import { ProviderSelector } from "./components/ProviderSelector"
import type { IProvider, RepoTreeNode } from "./providers/types"
import { createRepo2TxtStore } from "./store"

type ProviderKind = "github" | "local" | null

const toDisplayTree = (nodes: RepoTreeNode[]) =>
  nodes.map((node) => ({
    name: node.path.split("/").pop() ?? node.path,
    path: node.path,
    type: node.type === "blob" ? "file" : "directory"
  }))

const loadGitHubProvider = () =>
  import("./providers/GitHubProvider").then((module) => module.GitHubProvider)

const loadLocalProvider = () =>
  import("./providers/LocalProvider").then((module) => module.LocalProvider)

const loadFetchFilesWithConcurrency = () =>
  import("./fetchFilesWithConcurrency").then(
    (module) => module.fetchFilesWithConcurrency
  )

const loadFormatter = () =>
  import("./formatter/Formatter").then((module) => module.Formatter)

export function Repo2TxtPage() {
  const { t } = useTranslation(["option"])
  const storeRef = useRef(createRepo2TxtStore())
  const store = storeRef.current
  const nodes = useStore(store, (state) => state.nodes)
  const selectedPaths = useStore(store, (state) => state.selectedPaths)

  const [providerKind, setProviderKind] = useState<ProviderKind>(null)
  const [provider, setProvider] = useState<IProvider | null>(null)
  const [githubUrl, setGithubUrl] = useState("")
  const [filterText, setFilterText] = useState("")
  const [output, setOutput] = useState("")
  const [busy, setBusy] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string>("")
  const [sourceLoaded, setSourceLoaded] = useState(false)

  const filteredNodes = useMemo(() => {
    const query = filterText.trim().toLowerCase()
    if (!query) return nodes
    return nodes.filter((node) => node.path.toLowerCase().includes(query))
  }, [nodes, filterText])

  const syncNodesIntoStore = (nextNodes: RepoTreeNode[]) => {
    store.getState().setNodes(nextNodes)
  }

  const handleSelectProvider = (nextProvider: Exclude<ProviderKind, null>) => {
    setProviderKind(nextProvider)
    setProvider(null)
    setSourceLoaded(false)
    setOutput("")
    setStatusMessage("")
    syncNodesIntoStore([])
  }

  const handleLoadGithub = async () => {
    setBusy(true)
    setStatusMessage("")
    try {
      const GitHubProvider = await loadGitHubProvider()
      const githubProvider = new GitHubProvider()
      if (!githubProvider.validateUrl(githubUrl)) {
        throw new Error(
          t("option:repo2txt.errors.invalidGithubUrl", {
            defaultValue: "Enter a valid GitHub repository URL."
          })
        )
      }

      const tree = await githubProvider.fetchTree(githubUrl)
      setProvider(githubProvider)
      syncNodesIntoStore(tree)
      setSourceLoaded(tree.length > 0)
      setStatusMessage(
        t("option:repo2txt.status.loadedTree", {
          defaultValue: "Loaded {{count}} file tree entries.",
          count: tree.length
        })
      )
    } catch (error) {
      console.error("Failed to load GitHub repository.", error)
      setSourceLoaded(false)
      setStatusMessage(
        error instanceof Error
          ? error.message
          : t("option:repo2txt.errors.loadGithub", {
              defaultValue: "Failed to load GitHub repository."
            })
      )
    } finally {
      setBusy(false)
    }
  }

  const handleLocalFilesSelected = async (files: FileList) => {
    setBusy(true)
    setStatusMessage("")
    try {
      const LocalProvider = await loadLocalProvider()
      const localProvider = new LocalProvider()
      const firstFile = files[0]
      const looksLikeZip = files.length === 1 && /\.zip$/i.test(firstFile?.name ?? "")

      if (looksLikeZip) {
        await localProvider.initialize({
          source: "zip",
          zipFile: firstFile
        })
      } else {
        await localProvider.initialize({
          source: "directory",
          files
        })
      }

      const tree = await localProvider.fetchTree("local://directory")
      setProvider(localProvider)
      syncNodesIntoStore(tree)
      setSourceLoaded(tree.length > 0)
      setStatusMessage(
        t("option:repo2txt.status.loadedLocal", {
          defaultValue: "Loaded {{count}} local files.",
          count: tree.length
        })
      )
    } catch (error) {
      console.error("Failed to load local files.", error)
      setSourceLoaded(false)
      setStatusMessage(
        error instanceof Error
          ? error.message
          : t("option:repo2txt.errors.loadLocal", {
              defaultValue: "Failed to load local files."
            })
      )
    } finally {
      setBusy(false)
    }
  }

  const handleTogglePath = (path: string) => {
    store.getState().togglePath(path)
  }

  const handleGenerate = async () => {
    if (!provider) return

    const selectedNodes = nodes.filter(
      (node) => node.type === "blob" && selectedPaths.has(node.path)
    )

    if (selectedNodes.length === 0) {
      setOutput("")
      setStatusMessage(
        t("option:repo2txt.status.selectAtLeastOne", {
          defaultValue: "Select at least one file to generate output."
        })
      )
      return
    }

    setBusy(true)
    setStatusMessage("")
    try {
      const fetchFilesWithConcurrency = await loadFetchFilesWithConcurrency()
      const fileContents = await fetchFilesWithConcurrency({
        nodes: selectedNodes,
        provider,
        limit: 5,
        onProgress: (completed, total) => {
          setStatusMessage(
            t("option:repo2txt.status.fetchingFiles", {
              defaultValue: "Fetching files ({{completed}}/{{total}})...",
              completed,
              total
            })
          )
        }
      })
      const Formatter = await loadFormatter()
      const formatted = await Formatter.formatAsync(
        toDisplayTree(selectedNodes),
        fileContents
      )
      setOutput(`${formatted.directoryTree}\n\n${formatted.fileContents}`)
      setStatusMessage(
        t("option:repo2txt.status.generated", {
          defaultValue:
            "Generated output for {{count}} files ({{tokenCount}} tokens).",
          count: selectedNodes.length,
          tokenCount: formatted.tokenCount
        })
      )
    } catch (error) {
      console.error("Failed to generate output.", error)
      setStatusMessage(
        error instanceof Error
          ? error.message
          : t("option:repo2txt.errors.generate", {
              defaultValue: "Failed to generate output."
            })
      )
    } finally {
      setBusy(false)
    }
  }

  const handleCopy = async () => {
    if (!output.trim()) return
    if (!navigator?.clipboard?.writeText) return
    await navigator.clipboard.writeText(output)
  }

  const handleDownload = () => {
    if (!output.trim()) return
    const blob = new Blob([output], { type: "text/plain;charset=utf-8" })
    const href = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = href
    anchor.download = "repo2txt-output.txt"
    anchor.click()
    URL.revokeObjectURL(href)
  }

  return (
    <section
      data-testid="repo2txt-route-root"
      className="space-y-4"
    >
      <div
        data-testid="repo2txt-provider-panel"
        className="space-y-3 rounded border p-3"
      >
        <ProviderSelector
          provider={providerKind}
          githubUrl={githubUrl}
          busy={busy}
          onSelectProvider={handleSelectProvider}
          onGithubUrlChange={setGithubUrl}
          onLoadGithub={handleLoadGithub}
          onLocalFilesSelected={handleLocalFilesSelected}
        />
        <AdvancedFilters
          filterText={filterText}
          onFilterTextChange={setFilterText}
          totalCount={nodes.filter((node) => node.type === "blob").length}
          selectedCount={selectedPaths.size}
        />
        <FileTree
          nodes={filteredNodes}
          selectedPaths={selectedPaths}
          onTogglePath={handleTogglePath}
        />
        {statusMessage && (
          <p
            role="status"
            className="text-xs text-text-subtle"
          >
            {statusMessage}
          </p>
        )}
      </div>

      <div
        data-testid="repo2txt-output-panel"
        className="rounded border p-3"
      >
        <OutputPanel
          output={output}
          busy={busy}
          canGenerate={sourceLoaded}
          onGenerate={handleGenerate}
          onCopy={handleCopy}
          onDownload={handleDownload}
        />
      </div>
    </section>
  )
}
