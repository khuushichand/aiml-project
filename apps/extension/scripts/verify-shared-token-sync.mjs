#!/usr/bin/env node

/**
 * Verifies that extension build CSS token values match
 * ../packages/ui/src/assets/tailwind-shared.css.
 *
 * Usage:
 *   node scripts/verify-shared-token-sync.mjs
 *   node scripts/verify-shared-token-sync.mjs --target chrome-mv3
 *   node scripts/verify-shared-token-sync.mjs --dir .output/chrome-mv3
 */

import fs from 'node:fs'
import path from 'node:path'
import url from 'node:url'

const __dirname = path.dirname(url.fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, '..')

const SHARED_TOKEN_FILE = path.resolve(
  projectRoot,
  '../packages/ui/src/assets/tailwind-shared.css'
)

const OUTPUT_ROOT = path.resolve(projectRoot, '.output')
const FALLBACK_BUILD_ROOT = path.resolve(projectRoot, 'build')

const args = process.argv.slice(2)

function readArgValue(name) {
  const index = args.indexOf(name)
  if (index === -1) return null
  return args[index + 1] ?? null
}

function normalizeTokenValue(value) {
  return String(value || '').trim().replace(/\s+/g, ' ')
}

function extractBlock(text, selector) {
  const selectorIndex = text.indexOf(selector)
  if (selectorIndex === -1) return null

  const openBrace = text.indexOf('{', selectorIndex)
  if (openBrace === -1) return null

  let depth = 0
  for (let i = openBrace; i < text.length; i += 1) {
    const ch = text[i]
    if (ch === '{') depth += 1
    if (ch === '}') depth -= 1
    if (depth === 0) {
      return text.slice(openBrace + 1, i)
    }
  }

  return null
}

function extractTokensFromBlock(block) {
  const map = new Map()
  if (!block) return map

  const regex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/gi
  let match
  while ((match = regex.exec(block)) !== null) {
    const tokenName = match[1]
    if (!tokenName.startsWith('--color-')) continue
    map.set(tokenName, normalizeTokenValue(match[2]))
  }
  return map
}

function extractSourceTokens(sourceCss) {
  const rootBlock = extractBlock(sourceCss, ':root')
  const darkBlock = extractBlock(sourceCss, '.dark')
  return {
    root: extractTokensFromBlock(rootBlock),
    dark: extractTokensFromBlock(darkBlock)
  }
}

function extractBuiltTokens(builtCss) {
  const rootBlock = extractBlock(builtCss, ':root')
  const darkBlock = extractBlock(builtCss, '.dark')
  return {
    root: extractTokensFromBlock(rootBlock),
    dark: extractTokensFromBlock(darkBlock)
  }
}

function findBuiltCssFile(targetDir) {
  const assetsDir = path.join(targetDir, 'assets')
  if (!fs.existsSync(assetsDir)) return null

  const files = fs.readdirSync(assetsDir)
  const candidates = files
    .filter((file) => /^react-instance-check-.*\.css$/i.test(file))
    .map((file) => path.join(assetsDir, file))

  if (candidates.length === 0) return null

  candidates.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)
  return candidates[0]
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
        reason: 'missing-in-build'
      })
      continue
    }

    if (sourceValue !== builtValue) {
      mismatches.push({
        mode,
        token,
        sourceValue,
        builtValue,
        reason: 'value-mismatch'
      })
    }
  }

  return mismatches
}

function resolveTargetDir() {
  const explicitDir = readArgValue('--dir')
  if (explicitDir) {
    return path.resolve(projectRoot, explicitDir)
  }

  const target = readArgValue('--target')
  if (target) {
    const outCandidate = path.join(OUTPUT_ROOT, target)
    if (fs.existsSync(outCandidate)) return outCandidate
    const buildCandidate = path.join(FALLBACK_BUILD_ROOT, target)
    if (fs.existsSync(buildCandidate)) return buildCandidate
    return outCandidate
  }

  const defaultTargets = ['chrome-mv3', 'edge-mv3', 'firefox-mv2']
  for (const name of defaultTargets) {
    const outCandidate = path.join(OUTPUT_ROOT, name)
    if (fs.existsSync(outCandidate)) return outCandidate
    const buildCandidate = path.join(FALLBACK_BUILD_ROOT, name)
    if (fs.existsSync(buildCandidate)) return buildCandidate
  }

  return path.join(OUTPUT_ROOT, 'chrome-mv3')
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

  const builtCssFile = findBuiltCssFile(targetDir)
  if (!builtCssFile) {
    console.error(
      `[token-sync] Could not find built CSS (react-instance-check-*.css) in ${targetDir}`
    )
    process.exit(1)
  }

  const sourceCss = fs.readFileSync(SHARED_TOKEN_FILE, 'utf8')
  const builtCss = fs.readFileSync(builtCssFile, 'utf8')

  const sourceTokens = extractSourceTokens(sourceCss)
  const builtTokens = extractBuiltTokens(builtCss)

  const mismatches = [
    ...compareTokenSets(sourceTokens.root, builtTokens.root, 'root'),
    ...compareTokenSets(sourceTokens.dark, builtTokens.dark, 'dark')
  ]

  if (mismatches.length > 0) {
    console.error(
      `[token-sync] Shared color-token mismatch detected in ${builtCssFile}`
    )
    for (const item of mismatches) {
      console.error(
        `  - [${item.mode}] ${item.token}: source="${item.sourceValue}" built="${item.builtValue ?? '<missing>'}"`
      )
    }
    console.error(
      '[token-sync] Rebuild extension artifacts (e.g. `bun run build:chrome`) and retry.'
    )
    process.exit(1)
  }

  console.log(
    `[token-sync] OK: ${path.relative(projectRoot, builtCssFile)} matches shared tokens`
  )
}

main()
