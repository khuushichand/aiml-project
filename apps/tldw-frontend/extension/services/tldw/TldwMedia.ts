import { bgRequest } from '@/services/background-proxy'
import { db } from '@/db/dexie/schema'
import { generateID } from '@/db/dexie/helpers'

type UnknownRecord = Record<string, unknown>

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null

export interface ProcessOptions {
  storeLocal?: boolean
  metadata?: Record<string, unknown>
}

export const tldwMedia = {
  async addUrl(url: string, metadata?: Record<string, unknown>) {
    return await bgRequest<unknown>({
      path: '/api/v1/media/add',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { url, ...(metadata || {}) }
    })
  },

  async processUrl(url: string, opts?: ProcessOptions) {
    // Process without storing on server
    const res = await bgRequest<unknown>({
      path: '/api/v1/media/process-web-scraping',
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { url, ...(opts?.metadata || {}) }
    })
    if (opts?.storeLocal) {
      try {
        const record = isRecord(res) ? res : {}
        const recordMetadata = isRecord(record.metadata) ? record.metadata : {}
        const title =
          typeof record.title === "string"
            ? record.title
            : typeof recordMetadata.title === "string"
              ? recordMetadata.title
              : ""
        const content =
          typeof record.content === "string"
            ? record.content
            : typeof record.text === "string"
              ? record.text
              : ""
        await db.processedMedia.add({
          id: generateID(),
          url,
          title,
          content,
          metadata: recordMetadata,
          createdAt: Date.now()
        })
      } catch (e) {
        console.error('Failed to store processed media locally', e)
      }
    }
    return res
  }
}
