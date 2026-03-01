import { BaseProvider } from "./BaseProvider"
import type { FetchTreeOptions, ParsedRepoInfo, RepoFileContent, RepoTreeNode } from "./types"

type GitHubContentResponse = {
  content?: string
  encoding?: string
}

type GitHubTreeEntry = {
  path: string
  type: "blob" | "tree" | string
  url?: string
  size?: number
  sha?: string
}

type GitHubTreeResponse = {
  tree?: GitHubTreeEntry[]
}

const decodeBase64 = (value: string): string => {
  if (typeof atob === "function") {
    return atob(value)
  }
  throw new Error("Base64 decoding is not available in this runtime")
}

export class GitHubProvider extends BaseProvider {
  private static readonly API_BASE = "https://api.github.com"
  private static readonly URL_PATTERN =
    /^https:\/\/github\.com\/([^/]+)\/([^/]+)(?:\/tree\/(.+))?$/

  getType() {
    return "github" as const
  }

  getName() {
    return "GitHub"
  }

  requiresAuth() {
    return false
  }

  validateUrl(url: string): boolean {
    const normalized = url.trim().replace(/\/$/, "")
    return GitHubProvider.URL_PATTERN.test(normalized)
  }

  parseUrl(url: string): ParsedRepoInfo {
    const normalized = url.trim().replace(/\/$/, "")
    const match = normalized.match(GitHubProvider.URL_PATTERN)

    if (!match) {
      return {
        url,
        isValid: false,
        error: "Invalid GitHub URL format. Expected https://github.com/owner/repo"
      }
    }

    const [, owner, repo, branch] = match
    return {
      owner,
      repo,
      branch,
      url,
      isValid: true
    }
  }

  async fetchTree(url: string, options: FetchTreeOptions = {}): Promise<RepoTreeNode[]> {
    const parsed = this.parseUrl(url)
    if (!parsed.isValid || !parsed.owner || !parsed.repo) {
      throw new Error(parsed.error ?? "Invalid GitHub URL")
    }

    const ref = options.branch ?? parsed.branch ?? "HEAD"
    const treeUrl =
      `${GitHubProvider.API_BASE}/repos/${parsed.owner}/${parsed.repo}/git/trees/` +
      `${encodeURIComponent(ref)}?recursive=1`
    const response = await fetch(treeUrl, { headers: this.buildHeaders() })

    if (!response.ok) {
      throw new Error(`Failed to fetch GitHub tree: HTTP ${response.status}`)
    }

    const payload = (await response.json()) as GitHubTreeResponse
    const tree = payload.tree ?? []
    return tree.map((entry) => ({
      path: entry.path,
      type: entry.type === "blob" ? "blob" : "tree",
      url: entry.url,
      size: entry.size,
      sha: entry.sha
    }))
  }

  async fetchFile(node: RepoTreeNode): Promise<RepoFileContent> {
    if (!node.url) {
      throw new Error(`Cannot fetch file content for ${node.path}: missing URL`)
    }

    const response = await fetch(node.url, { headers: this.buildHeaders() })
    if (!response.ok) {
      throw new Error(`Failed to fetch file ${node.path}: HTTP ${response.status}`)
    }

    const data = (await response.json()) as GitHubContentResponse
    let text = data.content ?? ""
    if (data.encoding === "base64") {
      text = decodeBase64(text.replace(/\s/g, ""))
    }

    return {
      path: node.path,
      text,
      url: node.url,
      lineCount: text.split("\n").length
    }
  }

  private buildHeaders(): HeadersInit {
    const headers: Record<string, string> = {
      Accept: "application/vnd.github+json"
    }

    if (this.credentials?.token) {
      headers.Authorization = `token ${this.credentials.token}`
    }

    return headers
  }
}
