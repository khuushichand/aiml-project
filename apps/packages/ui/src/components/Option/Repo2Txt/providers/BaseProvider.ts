import type {
  FetchTreeOptions,
  IProvider,
  ParsedRepoInfo,
  ProviderCredentials,
  ProviderType,
  RepoFileContent,
  RepoTreeNode
} from "./types"

export abstract class BaseProvider implements IProvider {
  protected credentials: ProviderCredentials | null = null

  abstract getType(): ProviderType
  abstract getName(): string
  abstract validateUrl(url: string): boolean
  abstract parseUrl(url: string): ParsedRepoInfo
  abstract fetchTree(url: string, options?: FetchTreeOptions): Promise<RepoTreeNode[]>

  requiresAuth(): boolean {
    return true
  }

  setCredentials(credentials: ProviderCredentials): void {
    this.credentials = credentials
  }

  async fetchFile(node: RepoTreeNode): Promise<RepoFileContent> {
    if (!node.url) {
      throw new Error("Cannot fetch file content: missing file URL")
    }

    const response = await fetch(node.url)
    if (!response.ok) {
      throw new Error(`Failed to fetch file ${node.path}: HTTP ${response.status}`)
    }

    const text = await response.text()
    return {
      path: node.path,
      text,
      url: node.url,
      lineCount: text.split("\n").length
    }
  }
}
