import JSZip from "jszip"
import { BaseProvider } from "./BaseProvider"
import type { ParsedRepoInfo, RepoFileContent, RepoTreeNode } from "./types"

type LocalSource = "directory" | "zip"

export type LocalProviderInitializeOptions = {
  source: LocalSource
  files?: FileList
  zipFile?: File
  onProgress?: (progress: number, message: string) => void
}

export class LocalProvider extends BaseProvider {
  private source: LocalSource | null = null
  private fileMap = new Map<string, File>()
  private zipInstance: JSZip | null = null

  getType() {
    return "local" as const
  }

  getName() {
    return "Local"
  }

  requiresAuth() {
    return false
  }

  validateUrl(url: string): boolean {
    return url.startsWith("local://")
  }

  parseUrl(url: string): ParsedRepoInfo {
    if (!this.validateUrl(url)) {
      return {
        url,
        isValid: false,
        error: "Invalid local URL. Expected local://directory or local://zip"
      }
    }
    return {
      url,
      isValid: true
    }
  }

  async initialize(options: LocalProviderInitializeOptions): Promise<void> {
    this.source = options.source
    this.fileMap.clear()
    this.zipInstance = null

    if (options.source === "directory") {
      if (!options.files || options.files.length === 0) {
        throw new Error("Directory initialization requires files")
      }
      for (let i = 0; i < options.files.length; i++) {
        const file = options.files[i]
        const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath
        const path = relativePath || file.name
        if (!relativePath && this.fileMap.has(path)) {
          throw new Error(
            `Duplicate filename without directory context: ${path}. Use directory picker or zip source to preserve paths.`
          )
        }
        this.fileMap.set(path, file)
      }
      return
    }

    if (!options.zipFile) {
      throw new Error("Zip initialization requires a zipFile")
    }

    options.onProgress?.(0, "Loading zip file")
    this.zipInstance = await JSZip.loadAsync(options.zipFile)
    options.onProgress?.(100, "Zip file loaded")
  }

  async fetchTree(_url: string): Promise<RepoTreeNode[]> {
    if (!this.source) {
      throw new Error("LocalProvider must be initialized before fetchTree")
    }

    if (this.source === "directory") {
      return Array.from(this.fileMap.entries()).map(([path, file]) => ({
        path,
        type: "blob",
        url: path,
        urlType: "directory",
        size: file.size
      }))
    }

    if (!this.zipInstance) {
      return []
    }

    const tree: RepoTreeNode[] = []
    this.zipInstance.forEach((path, file) => {
      if (file.dir) return
      tree.push({
        path,
        type: "blob",
        url: path,
        urlType: "zip"
      })
    })
    return tree
  }

  async fetchFile(node: RepoTreeNode): Promise<RepoFileContent> {
    if (node.urlType === "directory") {
      const file = this.fileMap.get(node.path)
      if (!file) {
        throw new Error(`Local file not found: ${node.path}`)
      }
      const text = await file.text()
      return {
        path: node.path,
        text,
        lineCount: text.split("\n").length
      }
    }

    if (node.urlType === "zip") {
      const zipFile = this.zipInstance?.file(node.path)
      if (!zipFile) {
        throw new Error(`Zip file entry not found: ${node.path}`)
      }
      const text = await zipFile.async("text")
      return {
        path: node.path,
        text,
        lineCount: text.split("\n").length
      }
    }

    return super.fetchFile(node)
  }
}
