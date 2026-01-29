export {}

declare module "wxt/browser" {
  interface WxtRuntime {
    getURL(path: string): string
  }
  interface WxtI18n {
    getMessage(messageName: string, substitutions?: string | string[]): string
  }
}
