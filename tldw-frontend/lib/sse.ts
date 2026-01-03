export type SSEMessageHandler = (delta: string) => void;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type SSEJSONHandler = (json: any) => void;

export interface SSEOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  signal?: AbortSignal;
}

// Minimal SSE reader using fetch + ReadableStream decoding
export async function streamSSE(
  url: string,
  options: SSEOptions,
  onDelta: SSEMessageHandler,
  onJSON?: SSEJSONHandler,
  onDone?: () => void
): Promise<void> {
  const res = await fetch(url, {
    method: options.method || 'GET',
    headers: options.headers,
    body: options.body,
    credentials: 'include',
    signal: options.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Stream error: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let doneSent = false;

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Process complete lines only
      const lines = buffer.split('\n');
      // Keep last partial line in buffer
      buffer = lines.pop() || '';

      for (const raw of lines) {
        const line = raw.trim();
        if (!line || line.startsWith(':') || line.startsWith('event:')) continue; // heartbeat or event header

        if (line.startsWith('data:')) {
          const payload = line.slice('data:'.length).trim();
          if (!payload) continue;
          if (payload === '[DONE]') {
            if (onDone && !doneSent) { onDone(); doneSent = true; }
            continue;
          }
          try {
            const json = JSON.parse(payload);
            // Handle error frames
            if (json && json.error && json.error.message) {
              throw new Error(json.error.message);
            }
            if (onJSON) onJSON(json);
            const choices = json?.choices;
            const delta = choices && choices[0]?.delta?.content;
            if (typeof delta === 'string' && delta.length > 0) {
              onDelta(delta);
            } else if (choices && choices[0]?.message?.content) {
              // Non-stream-like message content
              onDelta(String(choices[0].message.content));
            }
          } catch (parseError: unknown) {
            // If it's not JSON, treat as plain text
            if (payload && typeof payload === 'string') {
              onDelta(payload);
            } else {
              throw parseError;
            }
          }
        }
      }
    }
  } finally {
    if (onDone && !doneSent) { onDone(); doneSent = true; }
  }
}
