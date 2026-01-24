import { browser } from "./wxt-browser"

if (typeof globalThis !== "undefined") {
  const globalScope = globalThis as typeof globalThis & {
    browser?: typeof browser
    chrome?: typeof browser
  }
  if (!globalScope.browser) {
    globalScope.browser = browser
  }
  if (!globalScope.chrome) {
    globalScope.chrome = browser
  }
}
