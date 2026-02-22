#!/usr/bin/env node

/**
 * Verifies that WebUI build CSS color token values match
 * ../packages/ui/src/assets/tailwind-shared.css.
 *
 * Usage:
 *   node scripts/verify-shared-token-sync.mjs
 *   node scripts/verify-shared-token-sync.mjs --dir .next
 */

import fs from "node:fs"
import path from "node:path"
import url from "node:url"

const __dirname = path.dirname(url.fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, "..")

const SHARED_TOKEN_FILE = path.resolve(
  projectRoot,
  "../packages/ui/src/assets/tailwind-shared.css"
)

const DEFAULT_TARGET_DIR = path.resolve(projectRoot, ".next")

const args = process.argv.slice(2)

function readArgValue(name) {
  const index = args.indexOf(name)
  if (index === -1) return null
  return args[index + 1] ?? null
}

function normalizeTokenValue(value) {
  return String(value || "").trim().replace(/\s+/g, " ")
}

function extractTokensFromBlock(block) {
  const map = new Map()
  if (!block) return map

  const regex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/gi
  let match
  while ((match = regex.exec(block)) !== null) {
    const tokenName = match[1]
    if (!tokenName.startsWith("--color-")) continue
    map.set(tokenName, normalizeTokenValue(match[2]))
  }
  return map
}

function extractDirectSelectorTokenBlock(text, selector) {
  let cursor = 0

  while (cursor < text.length) {
    const selectorIndex = text.indexOf(selector, cursor)
    if (selectorIndex === -1) return null

    const afterSelector = text.slice(selectorIndex + selector.length)
    const match = afterSelector.match(/^\s*\{/)
    if (!match) {
      cursor = selectorIndex + selector.length
      continue
    }

    const openBrace = selectorIndex + selector.length + match[0].length - 1
    let depth = 0
    let closeBrace = -1

    for (let i = openBrace; i < text.length; i += 1) {
      const ch = text[i]
      if (ch === "{") depth += 1
      if (ch === "}") depth -= 1
      if (depth === 0) {
        closeBrace = i
        break
      }
    }

    if (closeBrace === -1) {
      cursor = selectorIndex + selector.length
      continue
    }

    const block = text.slice(openBrace + 1, closeBrace)
    const tokens = extractTokensFromBlock(block)
    if (tokens.size > 0) {
      return tokens
    }

    cursor = closeBrace + 1
  }

  return null
}

function extractTokenSets(cssText) {
  return {
    root: extractDirectSelectorTokenBlock(cssText, ":root") ?? new Map(),
    dark: extractDirectSelectorTokenBlock(cssText, ".dark") ?? new Map()
  }
}

function collectCssFiles(rootDir) {
  const results = []
  const walk = (dir) => {
    const entries = fs.readdirSync(dir, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        walk(fullPath)
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".css")) {
        results.push(fullPath)
      }
    }
  }
  walk(rootDir)
  return results
}

function resolveCssSearchRoots(targetDir) {
  const roots = []

  if (path.basename(targetDir) === ".next") {
    const nextBuildRoots = [
      path.join(targetDir, "static"),
      path.join(targetDir, "server"),
      path.join(targetDir, "build")
    ]
    for (const candidate of nextBuildRoots) {
      if (fs.existsSync(candidate)) {
        roots.push(candidate)
      }
    }
  }

  if (roots.length === 0) {
    roots.push(targetDir)
  }

  return roots
}

function findBuiltCssCandidates(targetDir) {
  const roots = resolveCssSearchRoots(targetDir)
  const cssFiles = roots.flatMap((root) => collectCssFiles(root))
  const candidates = []

  for (const filePath of cssFiles) {
    const cssText = fs.readFileSync(filePath, "utf8")
    const tokens = extractTokenSets(cssText)
    const rootCount = tokens.root.size
    const darkCount = tokens.dark.size
    if (rootCount === 0 || darkCount === 0) continue

    candidates.push({
      filePath,
      tokens,
      rootCount,
      darkCount,
      mtimeMs: fs.statSync(filePath).mtimeMs
    })
  }

  return candidates
}

function compareTokenSets(source, built, mode) {
  const mismatches = []

  for (const [token, sourceValue] of source.entries()) {
    const builtValue = built.get(token)
    if (!builtValue) {
      mismatches.push({
        mode,
        token,
        sourceValue,
        builtValue: null,
        reason: "missing-in-build"
      })
      continue
    }

    if (sourceValue !== builtValue) {
      mismatches.push({
        mode,
        token,
        sourceValue,
        builtValue,
        reason: "value-mismatch"
      })
    }
  }

  return mismatches
}

function resolveTargetDir() {
  const explicitDir = readArgValue("--dir")
  if (!explicitDir) return DEFAULT_TARGET_DIR
  if (path.isAbsolute(explicitDir)) return explicitDir
  return path.resolve(projectRoot, explicitDir)
}

function main() {
  if (!fs.existsSync(SHARED_TOKEN_FILE)) {
    console.error(
      `[token-sync] Shared token file not found: ${SHARED_TOKEN_FILE}`
    )
    process.exit(1)
  }

  const targetDir = resolveTargetDir()
  if (!fs.existsSync(targetDir)) {
    console.error(`[token-sync] Target build directory not found: ${targetDir}`)
    process.exit(1)
  }

  const sourceCss = fs.readFileSync(SHARED_TOKEN_FILE, "utf8")
  const sourceTokens = extractTokenSets(sourceCss)

  const candidates = findBuiltCssCandidates(targetDir)
  if (candidates.length === 0) {
    console.error(
      `[token-sync] Could not find built CSS with :root + .dark color tokens in ${targetDir}`
    )
    process.exit(1)
  }

  const evaluated = candidates.map((candidate) => {
    const mismatches = [
      ...compareTokenSets(sourceTokens.root, candidate.tokens.root, "root"),
      ...compareTokenSets(sourceTokens.dark, candidate.tokens.dark, "dark")
    ]
    return {
      ...candidate,
      mismatches
    }
  })

  const exactMatches = evaluated
    .filter((candidate) => candidate.mismatches.length === 0)
    .sort((a, b) => b.mtimeMs - a.mtimeMs)

  if (exactMatches.length > 0) {
    const matched = exactMatches[0]
    console.log(
      `[token-sync] OK: ${path.relative(projectRoot, matched.filePath)} matches shared tokens`
    )
    return
  }

  evaluated.sort((a, b) => {
    if (a.mismatches.length !== b.mismatches.length) {
      return a.mismatches.length - b.mismatches.length
    }
    const aScore = a.rootCount + a.darkCount
    const bScore = b.rootCount + b.darkCount
    if (aScore !== bScore) return bScore - aScore
    return b.mtimeMs - a.mtimeMs
  })

  const closest = evaluated[0]
  if (closest.mismatches.length > 0) {
    console.error(
      `[token-sync] Shared color-token mismatch detected in ${closest.filePath}`
    )
    for (const item of closest.mismatches) {
      console.error(
        `  - [${item.mode}] ${item.token}: source="${item.sourceValue}" built="${item.builtValue ?? "<missing>"}"`
      )
    }
    console.error("[token-sync] Rebuild WebUI artifacts and retry.")
    process.exit(1)
  }
}

main()
