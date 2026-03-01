import { useMemo, useRef, useState } from "react"
import { Formatter } from "./formatter/Formatter"
import { GitHubProvider } from "./providers/GitHubProvider"
import { LocalProvider } from "./providers/LocalProvider"
import type { IProvider, RepoTreeNode } from "./providers/types"
import { createRepo2TxtStore } from "./store"
import { AdvancedFilters } from "./components/AdvancedFilters"
import { FileTree } from "./components/FileTree"
import { OutputPanel } from "./components/OutputPanel"
import { ProviderSelector } from "./components/ProviderSelector"

type ProviderKind = "github" | "local" | null

const toDisplayTree = (nodes: RepoTreeNode[]) =>
  nodes.map((node) => ({
    name: node.path.split("/").pop() ?? node.path,
    path: node.path,
    type: node.type === "blob" ? "file" : "directory"
  }))

export function Repo2TxtPage() {
  const storeRef = useRef(createRepo2TxtStore())
  const [providerKind, setProviderKind] = useState<ProviderKind>(null)
  const [provider, setProvider] = useState<IProvider | null>(null)
  const [githubUrl, setGithubUrl] = useState("")
  const [nodes, setNodes] = useState<RepoTreeNode[]>([])
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set())
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

  const syncNodesIntoState = (nextNodes: RepoTreeNode[]) => {
    storeRef.current.getState().setNodes(nextNodes)
    const storeState = storeRef.current.getState()
    setNodes(storeState.nodes)
    setSelectedPaths(new Set(storeState.selectedPaths))
  }

  const handleSelectProvider = (nextProvider: Exclude<ProviderKind, null>) => {
    setProviderKind(nextProvider)
    setProvider(null)
    setSourceLoaded(false)
    setOutput("")
    setStatusMessage("")
    syncNodesIntoState([])
  }

  const handleLoadGithub = async () => {
    setBusy(true)
    setStatusMessage("")
    try {
      const githubProvider = new GitHubProvider()
      if (!githubProvider.validateUrl(githubUrl)) {
        throw new Error("Enter a valid GitHub repository URL.")
      }

      const tree = await githubProvider.fetchTree(githubUrl)
      setProvider(githubProvider)
      syncNodesIntoState(tree)
      setSourceLoaded(tree.length > 0)
      setStatusMessage(`Loaded ${tree.length} file tree entries.`)
    } catch (error) {
      setSourceLoaded(false)
      setStatusMessage(
        error instanceof Error ? error.message : "Failed to load GitHub repository."
      )
    } finally {
      setBusy(false)
    }
  }

  const handleLocalFilesSelected = async (files: FileList) => {
    setBusy(true)
    setStatusMessage("")
    try {
      const localProvider = new LocalProvider()
      const firstFile = files[0]
      const looksLikeZip =
        files.length === 1 && /\.zip$/i.test(firstFile?.name ?? "")

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
      syncNodesIntoState(tree)
      setSourceLoaded(tree.length > 0)
      setStatusMessage(`Loaded ${tree.length} local files.`)
    } catch (error) {
      setSourceLoaded(false)
      setStatusMessage(
        error instanceof Error ? error.message : "Failed to load local files."
      )
    } finally {
      setBusy(false)
    }
  }

  const handleTogglePath = (path: string) => {
    setSelectedPaths((previous) => {
      const next = new Set(previous)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  const handleGenerate = async () => {
    if (!provider) return

    const selectedNodes = nodes.filter(
      (node) => node.type === "blob" && selectedPaths.has(node.path)
    )

    if (selectedNodes.length === 0) {
      setOutput("")
      setStatusMessage("Select at least one file to generate output.")
      return
    }

    setBusy(true)
    setStatusMessage("")
    try {
      const fileContents = await Promise.all(
        selectedNodes.map((node) => provider.fetchFile(node))
      )
      const formatted = await Formatter.formatAsync(
        toDisplayTree(selectedNodes),
        fileContents
      )
      setOutput(`${formatted.directoryTree}\n\n${formatted.fileContents}`)
      setStatusMessage(
        `Generated output for ${selectedNodes.length} files (${formatted.tokenCount} tokens).`
      )
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Failed to generate output."
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
