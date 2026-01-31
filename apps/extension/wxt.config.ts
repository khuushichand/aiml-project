import path from "node:path"
import { fileURLToPath } from "node:url"
import { defineConfig } from "wxt"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sharedRoot = path.resolve(__dirname, "../packages/ui/src")

export default defineConfig({
  srcDir: sharedRoot,
  entrypointsDir: path.join(__dirname, "entrypoints"),
  publicDir: path.join(__dirname, "public"),
  manifest: {
    default_locale: "en",
    options_ui: {
      page: "options.html",
      open_in_tab: true
    },
    permissions: [
      "storage",
      "contextMenus",
      "activeTab",
      "notifications",
      "sidePanel",
      "tabs",
      "scripting"
    ],
    optional_host_permissions: ["<all_urls>"],
    action: {
      default_title: "tldw Assistant",
      default_icon: {
        16: "icon/16.png",
        32: "icon/32.png",
        48: "icon/48.png",
        64: "icon/64.png",
        128: "icon/128.png"
      }
    }
  },
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
