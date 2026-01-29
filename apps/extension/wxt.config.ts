import path from "node:path"
import { fileURLToPath } from "node:url"
import { defineConfig } from "wxt"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sharedRoot = path.resolve(__dirname, "../packages/ui/src")

export default defineConfig({
  srcDir: sharedRoot,
  entrypointsDir: path.join(__dirname, "entrypoints"),
  publicDir: path.join(__dirname, "public"),
  vite: () => ({
    resolve: {
      alias: {
        "@": sharedRoot,
        "~": sharedRoot,
        "@tldw/ui": sharedRoot,
        "pa-tesseract.js": path.join(__dirname, "node_modules/pa-tesseract.js")
      }
    }
  })
})
