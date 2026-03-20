import { beforeEach, describe, expect, it, vi } from 'vitest';

import { streamSSE, streamStructuredSSE, type StructuredSSEEvent } from '@web/lib/sse';

const encoder = new TextEncoder();

function createSSEStream(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

function createResponse(chunks: string[]): Response {
  return new Response(createSSEStream(chunks), {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
    },
  });
}

describe('streamStructuredSSE', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('surfaces event names, ids, and parsed payloads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        createResponse([
          'event: snapshot\n',
          'id: 4\n',
          'data: {"latest_event_id":4}\n',
          '\n',
          'event: terminal\n',
          'id: 5\n',
          'data: {"event_id":5}\n',
          '\n',
        ])
      )
    );

    const events: StructuredSSEEvent[] = [];

    await streamStructuredSSE('/events', {}, (event) => {
      events.push(event);
    });

    expect(events).toEqual([
      { event: 'snapshot', id: 4, payload: { latest_event_id: 4 } },
      { event: 'terminal', id: 5, payload: { event_id: 5 } },
    ]);
  });

  it('joins multiple data lines and preserves plain-text payloads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        createResponse([
          'event: message\n',
          'id: 9\n',
          'data: line one\n',
          'data: line two\n',
          '\n',
        ])
      )
    );

    const events: StructuredSSEEvent[] = [];

    await streamStructuredSSE('/events', {}, (event) => {
      events.push(event);
    });

    expect(events).toEqual([{ event: 'message', id: 9, payload: 'line one\nline two' }]);
  });

  it('calls onDone for a done frame without emitting an extra event', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        createResponse([
          'event: progress\n',
          'id: 3\n',
          'data: {"phase":"collecting"}\n',
          '\n',
          'data: [DONE]\n',
          '\n',
        ])
      )
    );

    const events: StructuredSSEEvent[] = [];
    const onDone = vi.fn();

    await streamStructuredSSE(
      '/events',
      {},
      (event) => {
        events.push(event);
      },
      onDone
    );

    expect(events).toEqual([{ event: 'progress', id: 3, payload: { phase: 'collecting' } }]);
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});

describe('streamSSE', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps the delta-oriented chat wrapper behavior compatible', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        createResponse([
          'event: message\n',
          'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
          '\n',
          'data: plain text follow-up\n',
          '\n',
          'data: [DONE]\n',
          '\n',
        ])
      )
    );

    const deltas: string[] = [];
    const jsonFrames: unknown[] = [];
    const onDone = vi.fn();

    await streamSSE(
      '/chat',
      {},
      (delta) => {
        deltas.push(delta);
      },
      (json) => {
        jsonFrames.push(json);
      },
      onDone
    );

    expect(jsonFrames).toEqual([{ choices: [{ delta: { content: 'Hello' } }] }]);
    expect(deltas).toEqual(['Hello', 'plain text follow-up']);
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
