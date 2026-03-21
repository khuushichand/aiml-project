import fetcher from "@/libs/fetcher"
import { tldwAuth } from "@/services/tldw/TldwAuth"

const toHeaderRecord = (headers?: HeadersInit): Record<string, string> => {
  if (!headers) return {}
  return Object.fromEntries(new Headers(headers).entries())
}

export const fetchWithTldwAuth = async (
  input: string | URL | globalThis.Request,
  init?: RequestInit
): Promise<Response> => {
  const authHeaders = await tldwAuth.getAuthHeaders()
  const headerRecord = toHeaderRecord(init?.headers)
  return fetcher(input, {
    ...init,
    headers: {
      ...headerRecord,
      ...toHeaderRecord(authHeaders)
    }
  })
}
