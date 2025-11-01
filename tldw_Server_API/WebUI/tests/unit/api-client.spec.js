/* @vitest-environment jsdom */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import pkg from '../../js/api-client.js';

const { APIClient } = pkg;

describe('APIClient', () => {
  let client;
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    client = new APIClient();
    client.baseUrl = 'http://localhost:8000';
    client.token = 'sk-test';
    client.authMode = 'single-user';
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('generateCurlV2 includes headers/body', () => {
    const curl = client.generateCurlV2('POST', '/x', { body: { a: 1 }, query: { q: 'y' } });
    expect(curl).toContain('curl -X POST');
    expect(curl).toContain('Content-Type: application/json');
    // Auth-aware header now mirrors request behavior (single-user => X-API-KEY)
    expect(curl).toContain('X-API-KEY: [REDACTED]');
    expect(curl).toContain('q=y');
  });

  it('getTimeoutForEndpoint uses extended timeouts', () => {
    expect(client.getTimeoutForEndpoint('/api/v1/media/process-videos')).toBe(600000);
    expect(client.getTimeoutForEndpoint('/health')).toBe(30000);
  });

  it('makeRequest sets header and saves history', async () => {
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' }}));
    const res = await client.get('/health');
    expect(res).toEqual({ ok: true });
    expect(client.getHistory().length).toBe(1);
  });

  it('makeRequest throws on JSON error', async () => {
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'bad' }), { status: 400, headers: { 'Content-Type': 'application/json' }}));
    await expect(client.get('/bad')).rejects.toThrow();
  });

  it('masks token in cURL by default and reveals when toggled', () => {
    client.token = 'sk-test';
    client.includeTokenInCurl = false;
    let curl = client.generateCurlV2('GET', '/path');
    expect(curl).toContain('X-API-KEY: [REDACTED]');
    client.setIncludeTokenInCurl(true);
    curl = client.generateCurlV2('GET', '/path');
    expect(curl).toContain('X-API-KEY: sk-test');
  });

  it('handleStreamingResponse parses multi-line SSE events', async () => {
    const encoder = new TextEncoder();
    // Build a stream with two SSE events; one event has JSON split across two data: lines
    const chunks = [
      'data: {"a": 1}\n\n',
      'data: {"b":\n',
      'data: 2}\n\n',
      'data: [DONE]\n\n'
    ].map(s => encoder.encode(s));
    const stream = new ReadableStream({
      start(controller) {
        chunks.forEach(c => controller.enqueue(c));
        controller.close();
      }
    });
    const resp = new Response(stream);
    const out = await client.handleStreamingResponse(resp);
    expect(out.length).toBe(2);
    expect(out[0]).toEqual({ a: 1 });
    expect(out[1]).toEqual({ b: 2 });
  });
});
