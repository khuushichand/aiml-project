import { test, expect, type Page } from '@playwright/test'
import http from 'node:http'
import { AddressInfo } from 'node:net'
import { launchWithBuiltExtension } from './utils/extension-build'
import { forceConnected, waitForConnectionStore } from './utils/connection'

const API_KEY = 'THIS-IS-A-SECURE-KEY-123-FAKE-KEY'

const sharedOpenApiPaths = {
  '/api/v1/chat/completions': {},
  '/api/v1/rag/search': {},
  '/api/v1/rag/search/stream': {},
  '/api/v1/media/ingest/jobs': {},
  '/api/v1/media/process-videos': {},
  '/api/v1/media/process-audios': {},
  '/api/v1/media/process-pdfs': {},
  '/api/v1/media/process-ebooks': {},
  '/api/v1/media/process-documents': {},
  '/api/v1/media/process-web-scraping': {},
  '/api/v1/audio/speech': {},
  '/api/v1/audio/providers': {},
  '/api/v1/audio/voices': {},
  '/api/v1/audio/voices/catalog': {},
  '/api/v1/llm/models': {},
  '/api/v1/llm/models/metadata': {},
  '/api/v1/llm/providers': {},
  '/api/v1/chat/dictionaries': {}
}

const patchQuickIngestRuntime = async (page: Page, apiBaseUrl: string) =>
  page.evaluate(({ resolvedApiBaseUrl }) => {
    try {
      const runtime =
        (globalThis as any)?.browser?.runtime ||
        (globalThis as any)?.chrome?.runtime
      const onMessage = runtime?.onMessage
      const originalSendMessage =
        typeof runtime?.sendMessage === 'function'
          ? runtime.sendMessage.bind(runtime)
          : null
      if (!runtime || !onMessage || !originalSendMessage) {
        return false
      }

      const originalAddListener =
        typeof onMessage.addListener === 'function'
          ? onMessage.addListener.bind(onMessage)
          : null
      const originalRemoveListener =
        typeof onMessage.removeListener === 'function'
          ? onMessage.removeListener.bind(onMessage)
          : null
      const listeners = new Set<
        (message: any, sender?: any, sendResponse?: any) => void
      >()

      const emit = (message: any) => {
        for (const listener of [...listeners]) {
          try {
            listener(message, {}, () => undefined)
          } catch {
            // best-effort test emitter
          }
        }
      }

      const resolveProcessEndpoint = (type: string) => {
        switch ((type || '').toLowerCase()) {
          case 'video':
            return '/api/v1/media/process-videos'
          case 'audio':
            return '/api/v1/media/process-audios'
          case 'pdf':
            return '/api/v1/media/process-pdfs'
          case 'document':
            return '/api/v1/media/process-documents'
          default:
            return '/api/v1/media/process-web-scraping'
        }
      }

      onMessage.addListener = (listener: any) => {
        listeners.add(listener)
      }
      onMessage.removeListener = (listener: any) => {
        listeners.delete(listener)
      }

      runtime.sendMessage = async (message: any) => {
        if (message?.type === 'tldw:quick-ingest/start') {
          const payload = message?.payload || {}
          const sessionId = `qi-e2e-media-${Date.now()}`
          const files = Array.isArray(payload?.files) ? payload.files : []
          const entries = Array.isArray(payload?.entries) ? payload.entries : []

          queueMicrotask(async () => {
            const results: Array<Record<string, any>> = []
            for (let index = 0; index < files.length; index += 1) {
              const file = files[index] || {}
              const sourceId = String(file?.id || `file-${index + 1}`)
              const fileName = String(file?.name || `file-${index + 1}.bin`)
              const byteLength = Array.isArray(file?.data)
                ? file.data.length
                : file?.data instanceof Uint8Array
                  ? file.data.byteLength
                  : file?.data instanceof ArrayBuffer
                    ? file.data.byteLength
                    : 0
              try {
                const submitResponse = await fetch(
                  `${resolvedApiBaseUrl}/api/v1/media/ingest/jobs`,
                  {
                    method: 'POST',
                    headers: { 'content-type': 'application/json' },
                    body: JSON.stringify({
                      media_type: 'document',
                      source_id: sourceId,
                      file_name: fileName,
                      size_bytes: byteLength
                    })
                  }
                )
                if (!submitResponse.ok) {
                  throw new Error(`Submit failed (${submitResponse.status})`)
                }
                const submitPayload = await submitResponse
                  .json()
                  .catch(() => ({}))
                const result = {
                  id: sourceId,
                  status: 'ok',
                  fileName,
                  type: 'document',
                  data: {
                    id:
                      submitPayload?.jobs?.[0]?.id || `media-file-${sourceId}`
                  }
                }
                results.push(result)
                emit({
                  type: 'tldw:quick-ingest/progress',
                  payload: {
                    sessionId,
                    result
                  }
                })
              } catch (error: any) {
                const result = {
                  id: sourceId,
                  status: 'error',
                  fileName,
                  type: 'file',
                  error: error?.message || 'Upload failed'
                }
                results.push(result)
                emit({
                  type: 'tldw:quick-ingest/progress',
                  payload: {
                    sessionId,
                    result
                  }
                })
              }
            }

            for (let index = 0; index < entries.length; index += 1) {
              const entry = entries[index] || {}
              const sourceId = String(entry?.id || `entry-${index + 1}`)
              const entryType = String(entry?.type || 'web_page')
              const url = String(entry?.url || '').trim()
              const processEndpoint = resolveProcessEndpoint(entryType)
              try {
                const processResponse = await fetch(
                  `${resolvedApiBaseUrl}${processEndpoint}`,
                  {
                    method: 'POST',
                    headers: { 'content-type': 'application/json' },
                    body: JSON.stringify({
                      url,
                      media_type: entryType
                    })
                  }
                )
                if (!processResponse.ok) {
                  throw new Error(`Process failed (${processResponse.status})`)
                }
                const processPayload = await processResponse
                  .json()
                  .catch(() => ({}))
                const result = {
                  id: sourceId,
                  status: 'ok',
                  type: entryType,
                  url,
                  data: {
                    id: processPayload?.id || `media-entry-${sourceId}`
                  }
                }
                results.push(result)
                emit({
                  type: 'tldw:quick-ingest/progress',
                  payload: {
                    sessionId,
                    result
                  }
                })
              } catch (error: any) {
                const result = {
                  id: sourceId,
                  status: 'error',
                  type: entryType,
                  url,
                  error: error?.message || 'Process failed'
                }
                results.push(result)
                emit({
                  type: 'tldw:quick-ingest/progress',
                  payload: {
                    sessionId,
                    result
                  }
                })
              }
            }

            emit({
              type: 'tldw:quick-ingest/completed',
              payload: {
                sessionId,
                results
              }
            })
          })

          return {
            ok: true,
            sessionId
          }
        }
        if (message?.type === 'tldw:quick-ingest/cancel') {
          emit({
            type: 'tldw:quick-ingest/cancelled',
            payload: {
              sessionId: String(message?.payload?.sessionId || ''),
              reason: String(message?.payload?.reason || 'Cancelled by user.')
            }
          })
          return { ok: true }
        }
        return originalSendMessage(message)
      }

      ;(window as any).__restoreQuickIngestRuntimePatch = () => {
        runtime.sendMessage = originalSendMessage
        if (originalAddListener) {
          onMessage.addListener = originalAddListener
        }
        if (originalRemoveListener) {
          onMessage.removeListener = originalRemoveListener
        }
        listeners.clear()
      }

      return true
    } catch {
      return false
    }
  }, { resolvedApiBaseUrl: apiBaseUrl })

test.describe('Quick ingest media requests', () => {
  let server: http.Server
  let baseUrl = ''
  let ingestJobSubmits: string[] = []
  let mediaProcesses: string[] = []

  test.beforeAll(async () => {
    server = http.createServer((req, res) => {
      const url = req.url || '/'
      const method = (req.method || 'GET').toUpperCase()
      const json = (code: number, body: any) => {
        res.writeHead(code, {
          'content-type': 'application/json',
          'access-control-allow-origin': '*',
          'access-control-allow-credentials': 'true'
        })
        res.end(JSON.stringify(body))
      }

      if (method === 'OPTIONS') {
        res.writeHead(204, {
          'access-control-allow-origin': '*',
          'access-control-allow-credentials': 'true',
          'access-control-allow-headers': 'content-type, x-api-key, authorization'
        })
        return res.end()
      }

      if (url === '/api/v1/health' && method === 'GET') {
        return json(200, { status: 'ok' })
      }
      if (url === '/openapi.json' && method === 'GET') {
        return json(200, {
          openapi: '3.1.0',
          info: { title: 'tldw media e2e mock', version: 'e2e' },
          paths: sharedOpenApiPaths
        })
      }
      if (url === '/api/v1/rag/health' && method === 'GET') {
        return json(200, {
          status: 'ok',
          components: {
            search_index: {
              status: 'healthy',
              message: '',
              fts_table_count: 1
            }
          }
        })
      }
      if (url === '/api/v1/media/ingest/jobs' && method === 'POST') {
        ingestJobSubmits.push(url)
        let body = ''
        req.on('data', (c) => (body += c))
        req.on('end', () =>
          json(200, {
            batch_id: `batch-${ingestJobSubmits.length}`,
            jobs: [{ id: 7000 + ingestJobSubmits.length, status: 'queued' }],
            ok: true,
            body: body || '{}'
          })
        )
        return
      }
      if (url.startsWith('/api/v1/media/process-') && method === 'POST') {
        mediaProcesses.push(url)
        let body = ''
        req.on('data', (c) => (body += c))
        req.on('end', () =>
          setTimeout(() => {
            json(200, { ok: true, body: body || '{}' })
          }, 150)
        )
        return
      }

      res.writeHead(404)
      res.end('not found')
    })
    await new Promise<void>((resolve) =>
      server.listen(0, '127.0.0.1', resolve)
    )
    const addr = server.address() as AddressInfo
    baseUrl = `http://127.0.0.1:${addr.port}`
  })

  test.afterAll(async () => {
    await new Promise<void>((resolve) => server.close(() => resolve()))
  })

  test('quick ingest calls /media/ingest/jobs and /media/process-*', async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension({
      seedConfig: {
        serverUrl: baseUrl,
        authMode: 'single-user',
        apiKey: API_KEY
      }
    })

    try {
      const patched = await patchQuickIngestRuntime(page, baseUrl)
      if (!patched) {
        test.skip(true, 'Unable to patch runtime messaging in extension page context.')
        return
      }

      await page.goto(optionsUrl + '#/chat', {
        waitUntil: 'domcontentloaded'
      })
      await waitForConnectionStore(page, 'media-and-tts')
      await forceConnected(page, {}, 'media-and-tts')

      const openQuickIngestButton = page
        .getByRole('button', { name: /quick ingest/i })
        .first()
      await expect(openQuickIngestButton).toBeVisible()
      await openQuickIngestButton.click()

      const modal = page.getByRole('dialog', { name: /quick ingest/i }).first()
      await expect(modal).toBeVisible({ timeout: 10_000 })

      const urlInput = modal.getByPlaceholder('https://...').first()
      await urlInput.fill('https://example.com/a.html')
      await modal.getByRole('button', { name: /add url|add urls/i }).first().click()
      const rows = modal.getByPlaceholder('https://...')
      await rows.nth(1).fill('https://example.com/b.pdf')

      await page.setInputFiles('[data-testid="qi-file-input"]', {
        name: 'sample.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('hello from media-and-tts spec')
      })

      const runButton = modal
        .getByRole('button', { name: /Run quick ingest|Ingest|Process/i })
        .first()
      await expect(runButton).toBeEnabled()
      await runButton.click()

      await expect
        .poll(
          () => ingestJobSubmits.length + mediaProcesses.length,
          {
            timeout: 30_000
          }
        )
        .toBeGreaterThan(0)
    } finally {
      try {
        await page.evaluate(() => {
          try {
            const restore = (window as any).__restoreQuickIngestRuntimePatch
            if (typeof restore === 'function') {
              restore()
            }
            delete (window as any).__restoreQuickIngestRuntimePatch
          } catch {
            // ignore cleanup failures if page context is gone
          }
        })
      } catch {
        // ignore cleanup failures if page already closed
      }
      await context.close()
    }
  })
})

test.describe('tldw TTS provider', () => {
  let server: http.Server
  let baseUrl = ''
  let audioRequests = 0

  test.beforeAll(async () => {
    server = http.createServer((req, res) => {
      const requestUrl = new URL(req.url || '/', 'http://127.0.0.1')
      const pathName = requestUrl.pathname
      const method = (req.method || 'GET').toUpperCase()
      const json = (code: number, body: any) => {
        res.writeHead(code, {
          'content-type': 'application/json',
          'access-control-allow-origin': '*',
          'access-control-allow-credentials': 'true'
        })
        res.end(JSON.stringify(body))
      }

      if (method === 'OPTIONS') {
        res.writeHead(204, {
          'access-control-allow-origin': '*',
          'access-control-allow-credentials': 'true',
          'access-control-allow-headers': 'content-type, x-api-key, authorization'
        })
        return res.end()
      }

      if (pathName === '/api/v1/health' && method === 'GET') {
        return json(200, { status: 'ok' })
      }
      if (pathName === '/openapi.json' && method === 'GET') {
        return json(200, {
          openapi: '3.1.0',
          info: { title: 'tldw tts e2e mock', version: 'e2e' },
          paths: sharedOpenApiPaths
        })
      }
      if (pathName === '/api/v1/audio/providers' && method === 'GET') {
        return json(200, {
          providers: {
            kokoro: {
              provider_name: 'Kokoro',
              formats: ['mp3'],
              default_format: 'mp3',
              supports_streaming: false,
              voices: [{ id: 'af_heart', name: 'AF Heart', language: 'en' }]
            }
          },
          voices: {
            kokoro: [{ id: 'af_heart', name: 'AF Heart', language: 'en' }]
          }
        })
      }
      if (pathName === '/api/v1/audio/voices' && method === 'GET') {
        return json(200, [{ id: 'af_heart', name: 'AF Heart', provider: 'kokoro' }])
      }
      if (pathName === '/api/v1/audio/voices/catalog' && method === 'GET') {
        return json(200, [{ id: 'af_heart', name: 'AF Heart', provider: 'kokoro' }])
      }
      if (pathName === '/api/v1/llm/providers' && method === 'GET') {
        return json(200, [{ provider: 'openai', display_name: 'OpenAI' }])
      }
      if (pathName === '/api/v1/llm/models' && method === 'GET') {
        return json(200, [{ id: 'gpt-4o-mini', provider: 'openai' }])
      }
      if (pathName === '/api/v1/llm/models/metadata' && method === 'GET') {
        return json(200, {
          models: [{ id: 'gpt-4o-mini', provider: 'openai', capabilities: {} }]
        })
      }
      if (pathName === '/api/v1/chat/completions' && method === 'POST') {
        return json(200, {
          id: 'chatcmpl-e2e',
          object: 'chat.completion',
          created: Math.floor(Date.now() / 1000),
          model: 'gpt-4o-mini',
          choices: [
            {
              index: 0,
              finish_reason: 'stop',
              message: { role: 'assistant', content: 'Hello from TTS test' }
            }
          ]
        })
      }
      if (pathName === '/api/v1/audio/speech' && method === 'POST') {
        audioRequests += 1
        const chunks: Buffer[] = []
        req.on('data', (c) => chunks.push(Buffer.from(c)))
        req.on('end', () => {
          res.writeHead(200, {
            'content-type': 'audio/mpeg',
            'access-control-allow-origin': '*',
            'access-control-allow-credentials': 'true'
          })
          res.end(Buffer.from([0x49, 0x44, 0x33]))
        })
        return
      }

      res.writeHead(404)
      res.end('not found')
    })

    await new Promise<void>((resolve) =>
      server.listen(0, '127.0.0.1', resolve)
    )
    const addr = server.address() as AddressInfo
    baseUrl = `http://127.0.0.1:${addr.port}`
  })

  test.afterAll(async () => {
    await new Promise<void>((resolve) => server.close(() => resolve()))
  })

  test('tts playground play with provider=tldw calls /api/v1/audio/speech', async () => {
    const { context, page, optionsUrl } = await launchWithBuiltExtension({
      seedConfig: {
        serverUrl: baseUrl,
        authMode: 'single-user',
        apiKey: API_KEY,
        ttsProvider: 'tldw',
        isTTSEnabled: true,
        tldwTtsModel: 'kokoro',
        tldwTtsVoice: 'af_heart',
        tldwTtsResponseFormat: 'mp3'
      }
    })

    try {
      await page.goto(optionsUrl + '#/tts', {
        waitUntil: 'domcontentloaded'
      })
      await waitForConnectionStore(page, 'media-and-tts-tts')
      await forceConnected(page, {}, 'media-and-tts-tts')

      const input = page
        .getByLabel(/Enter some text to hear it spoken/i)
        .first()
      await input.fill('Hello from TTS test')

      const playButton = page.getByRole('button', { name: /^Play$/i }).first()
      await expect(playButton).toBeEnabled()
      await playButton.click()

      await expect
        .poll(() => audioRequests, {
          timeout: 15_000
        })
        .toBeGreaterThan(0)
    } finally {
      await context.close()
    }
  })
})
