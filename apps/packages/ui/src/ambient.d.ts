// Ambient declarations for shared UI code when compiled outside the extension build.

declare const browser: any

declare function defineBackground<T>(definition: T): T
declare function defineContentScript<T>(definition: T): T

declare namespace chrome {
  namespace storage {
    type StorageArea = any
  }
  namespace runtime {
    type Port = any
    type MessageSender = any
  }
  namespace tabs {
    type Tab = any
  }
  const storage: any
  const runtime: any
  const tabs: any
  const alarms: any
  const action: any
  const i18n: any
  const scripting: any
  const permissions: any
  const notifications: any
  const tts: any
  const sidePanel: any
  namespace sidePanel {
    type OpenOptions = any
  }
}

declare var chrome: typeof chrome

interface ImportMetaEnv {
  DEV?: boolean
  MODE?: string
  PROD?: boolean
  VITE_TLDW_DOCS_URL?: string
  VITE_TLDW_API_KEY?: string
  BROWSER?: string
}

interface ImportMeta {
  readonly env?: ImportMetaEnv
  glob?: {
    <T = unknown>(
      pattern: string,
      options?: {
        query?: string
        import?: string
        eager?: false
      }
    ): Record<string, () => Promise<T>>
    <T = unknown>(
      pattern: string,
      options: {
        query?: string
        import?: string
        eager: true
      }
    ): Record<string, T>
  }
}

declare module "*.png" {
  const src: string
  export default src
}
