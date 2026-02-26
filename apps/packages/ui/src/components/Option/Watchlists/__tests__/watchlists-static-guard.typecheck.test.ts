import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const WATCHLISTS_ROOT = path.resolve(__dirname, "..")
type SymbolNamespace = "type" | "value"

interface SymbolIdentifier {
  name: string
  namespace: SymbolNamespace
}

const isSourceFile = (entryPath: string): boolean =>
  (entryPath.endsWith(".ts") || entryPath.endsWith(".tsx")) &&
  !entryPath.endsWith(".test.ts") &&
  !entryPath.endsWith(".test.tsx") &&
  !entryPath.includes(`${path.sep}__tests__${path.sep}`)

const readWatchlistsSourceFiles = (): string[] => {
  const stack = [WATCHLISTS_ROOT]
  const files: string[] = []

  while (stack.length > 0) {
    const current = stack.pop()
    if (!current) continue
    const entries = fs.readdirSync(current, { withFileTypes: true })
    for (const entry of entries) {
      const entryPath = path.join(current, entry.name)
      if (entry.isDirectory()) {
        if (entry.name === "__tests__") continue
        stack.push(entryPath)
        continue
      }
      if (isSourceFile(entryPath)) {
        files.push(entryPath)
      }
    }
  }

  return files.sort()
}

const findDuplicateSelectors = (source: string): string[] => {
  const selectorRegex = /useWatchlistsStore\s*\(\s*\(\w+\)\s*=>\s*\w+\.([A-Za-z0-9_]+)\s*\)/g
  const counts = new Map<string, number>()
  for (const match of source.matchAll(selectorRegex)) {
    const key = match[1]
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  return [...counts.entries()]
    .filter(([, count]) => count > 1)
    .map(([key]) => key)
    .sort()
}

const extractNamedImportIdentifiers = (
  namedClause: string,
  defaultNamespace: SymbolNamespace
): SymbolIdentifier[] => {
  return namedClause
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const isTypeOnly = part.startsWith("type ")
      const normalizedPart = isTypeOnly ? part.replace(/^type\s+/, "") : part
      const aliasMatch = /\bas\s+([A-Za-z_$][\w$]*)$/.exec(normalizedPart)
      return {
        name: aliasMatch ? aliasMatch[1] : normalizedPart,
        namespace: isTypeOnly ? "type" : defaultNamespace
      } satisfies SymbolIdentifier
    })
}

const extractImportIdentifiers = (source: string): SymbolIdentifier[] => {
  const identifiers: SymbolIdentifier[] = []
  const importRegex = /^import\s+(?:type\s+)?(.+?)\s+from\s+["'][^"']+["']/gm

  for (const match of source.matchAll(importRegex)) {
    const fullImportStatement = match[0] || ""
    const importIsTypeOnly = /^import\s+type\b/.test(fullImportStatement)
    const clause = match[1].trim()
    if (!clause) continue

    if (clause.startsWith("{") && clause.endsWith("}")) {
      const named = clause.slice(1, -1)
      identifiers.push(
        ...extractNamedImportIdentifiers(named, importIsTypeOnly ? "type" : "value")
      )
      continue
    }

    if (clause.startsWith("* as ")) {
      identifiers.push({
        name: clause.replace("* as ", "").trim(),
        namespace: importIsTypeOnly ? "type" : "value"
      })
      continue
    }

    const parts = clause.split(",").map((part) => part.trim()).filter(Boolean)
    if (parts.length > 0 && !parts[0].startsWith("{") && !parts[0].startsWith("*")) {
      identifiers.push({
        name: parts[0],
        namespace: importIsTypeOnly ? "type" : "value"
      })
    }
    const namedPart = parts.find((part) => part.startsWith("{") && part.endsWith("}"))
    if (namedPart) {
      const named = namedPart.slice(1, -1)
      identifiers.push(
        ...extractNamedImportIdentifiers(named, importIsTypeOnly ? "type" : "value")
      )
    }
  }

  return identifiers.filter((identifier) => Boolean(identifier.name))
}

const extractTopLevelDeclarationIdentifiers = (source: string): SymbolIdentifier[] => {
  const identifiers: SymbolIdentifier[] = []
  const declarationRegex =
    /^(?:export\s+)?(const|let|var|function|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/gm

  for (const match of source.matchAll(declarationRegex)) {
    const declarationType = match[1]
    const declarationName = match[2]
    identifiers.push({
      name: declarationName,
      namespace:
        declarationType === "interface" || declarationType === "type"
          ? "type"
          : "value"
    })
  }
  return identifiers
}

const findMatchingBrace = (source: string, startIndex: number): number => {
  let depth = 0
  for (let index = startIndex; index < source.length; index += 1) {
    const char = source[index]
    if (char === "{") depth += 1
    if (char === "}") {
      depth -= 1
      if (depth === 0) return index
    }
  }
  return -1
}

const extractTopLevelInterfacePropertyNames = (body: string): string[] => {
  const names: string[] = []
  const lines = body.split(/\r?\n/)
  let braceDepth = 0

  for (const line of lines) {
    if (braceDepth === 0) {
      const propertyMatch = /^\s*(?:readonly\s+)?([A-Za-z_$][\w$]*)\??\s*:/.exec(line)
      if (propertyMatch) {
        names.push(propertyMatch[1])
      }
    }

    for (const char of line) {
      if (char === "{") braceDepth += 1
      if (char === "}") braceDepth = Math.max(0, braceDepth - 1)
    }
  }

  return names
}

const findDuplicateInterfaceProperties = (source: string): Array<{ name: string; duplicates: string[] }> => {
  const issues: Array<{ name: string; duplicates: string[] }> = []
  const interfaceRegex = /^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)\b/gm

  for (const match of source.matchAll(interfaceRegex)) {
    const interfaceName = match[1]
    const interfaceIndex = match.index ?? -1
    if (interfaceIndex < 0) continue
    const bodyStart = source.indexOf("{", interfaceIndex)
    if (bodyStart < 0) continue
    const bodyEnd = findMatchingBrace(source, bodyStart)
    if (bodyEnd < 0) continue
    const body = source.slice(bodyStart + 1, bodyEnd)

    const propertyCounts = new Map<string, number>()
    for (const propertyName of extractTopLevelInterfacePropertyNames(body)) {
      propertyCounts.set(propertyName, (propertyCounts.get(propertyName) || 0) + 1)
    }

    const duplicates = [...propertyCounts.entries()]
      .filter(([, count]) => count > 1)
      .map(([propertyName]) => propertyName)
      .sort()
    if (duplicates.length > 0) {
      issues.push({ name: interfaceName, duplicates })
    }
  }

  return issues
}

describe("Watchlists static type guard", () => {
  it("prevents duplicate watchlists-store selectors within a single source file", () => {
    const issues = readWatchlistsSourceFiles()
      .map((filePath) => {
        const source = fs.readFileSync(filePath, "utf8")
        const duplicates = findDuplicateSelectors(source)
        return duplicates.length > 0
          ? `${path.relative(WATCHLISTS_ROOT, filePath)} -> ${duplicates.join(", ")}`
          : null
      })
      .filter(Boolean)

    expect(issues).toEqual([])
  })

  it("prevents duplicate top-level identifiers in watchlists source files", () => {
    const issues = readWatchlistsSourceFiles()
      .map((filePath) => {
        const source = fs.readFileSync(filePath, "utf8")
        const symbolCounts = new Map<string, number>()
        const symbols = [
          ...extractImportIdentifiers(source),
          ...extractTopLevelDeclarationIdentifiers(source)
        ]
        symbols.forEach((symbol) => {
          const key = `${symbol.namespace}:${symbol.name}`
          symbolCounts.set(key, (symbolCounts.get(key) || 0) + 1)
        })
        const duplicates = [...symbolCounts.entries()]
          .filter(([, count]) => count > 1)
          .map(([name]) => name)
          .sort()
        return duplicates.length > 0
          ? `${path.relative(WATCHLISTS_ROOT, filePath)} -> ${duplicates.join(", ")}`
          : null
      })
      .filter(Boolean)

    expect(issues).toEqual([])
  })

  it("prevents duplicate interface property keys in watchlists source files", () => {
    const issues = readWatchlistsSourceFiles()
      .map((filePath) => {
        const source = fs.readFileSync(filePath, "utf8")
        const duplicates = findDuplicateInterfaceProperties(source)
        if (duplicates.length === 0) return null
        const detail = duplicates
          .map((item) => `${item.name}: ${item.duplicates.join(", ")}`)
          .join("; ")
        return `${path.relative(WATCHLISTS_ROOT, filePath)} -> ${detail}`
      })
      .filter(Boolean)

    expect(issues).toEqual([])
  })
})
