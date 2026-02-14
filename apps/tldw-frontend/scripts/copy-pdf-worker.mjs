#!/usr/bin/env node
/**
 * Copy PDF.js worker to public folder
 *
 * This script copies the PDF.js worker file from node_modules to the public
 * directory so it can be served locally instead of from a CDN.
 *
 * This improves:
 * - Security: No external CDN dependencies
 * - Reliability: Works offline / in air-gapped environments
 * - Performance: Same-origin requests are faster
 */

import { copyFileSync, existsSync, mkdirSync } from "fs"
import { dirname, join } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(__dirname, "..")

// Source: node_modules/pdfjs-dist/build/pdf.worker.min.mjs
const workerSource = join(
  projectRoot,
  "node_modules",
  "pdfjs-dist",
  "build",
  "pdf.worker.min.mjs"
)

// Destination: public/pdf.worker.min.mjs
const workerDest = join(projectRoot, "public", "pdf.worker.min.mjs")

function copyPdfWorker() {
  // Ensure source exists
  if (!existsSync(workerSource)) {
    console.error(`PDF.js worker not found at: ${workerSource}`)
    console.error("Make sure pdfjs-dist is installed: bun install")
    process.exit(1)
  }

  // Ensure public directory exists
  const publicDir = dirname(workerDest)
  if (!existsSync(publicDir)) {
    mkdirSync(publicDir, { recursive: true })
  }

  // Copy the worker file
  try {
    copyFileSync(workerSource, workerDest)
    console.log(`Copied PDF.js worker to: ${workerDest}`)
  } catch (error) {
    console.error(`Failed to copy PDF.js worker: ${error.message}`)
    process.exit(1)
  }
}

copyPdfWorker()
