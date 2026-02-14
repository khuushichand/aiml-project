#!/usr/bin/env node
/*
  Simple smoke-test for tldw_server API via the frontend config.
  Usage:
    NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 \
    NEXT_PUBLIC_API_VERSION=v1 \
    NEXT_PUBLIC_X_API_KEY=... \
    node scripts/smoke.mjs
*/

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const BASE = `${API_URL}/api/${API_VERSION}`;
const X_API_KEY = process.env.NEXT_PUBLIC_X_API_KEY || '';
const API_BEARER = process.env.NEXT_PUBLIC_API_BEARER || '';

function authHeaders() {
  const h = { 'Accept': 'application/json' };
  if (API_BEARER) h['Authorization'] = `Bearer ${API_BEARER}`;
  if (X_API_KEY) h['X-API-KEY'] = X_API_KEY;
  return h;
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders(), redirect: 'manual' });
  const text = await res.text();
  let body; try { body = JSON.parse(text); } catch { body = text; }
  return { ok: res.ok, status: res.status, statusText: res.statusText, body };
}

async function post(path, json) {
  const headers = { ...authHeaders(), 'Content-Type': 'application/json' };
  const res = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: JSON.stringify(json), redirect: 'manual' });
  const text = await res.text();
  let body; try { body = JSON.parse(text); } catch { body = text; }
  return { ok: res.ok, status: res.status, statusText: res.statusText, body };
}

function logStep(name, result) {
  const ok = result.ok ? 'OK' : 'FAIL';
  console.log(`- ${name}: ${ok} (${result.status} ${result.statusText})`);
}

(async () => {
  console.log('TLDW Frontend Smoke Test');
  console.log(`Base: ${BASE}`);
  console.log(`Auth: ${API_BEARER ? 'Bearer' : X_API_KEY ? 'X-API-KEY' : 'none'}`);

  let failures = 0;

  // 1) LLM providers (critical)
  const providers = await get('/llm/providers');
  logStep('GET /llm/providers', providers);
  if (!providers.ok) failures++;

  // 2) Chat completion (basic)
  const chat = await post('/chat/completions', {
    model: 'auto',
    stream: false,
    messages: [
      { role: 'system', content: 'You are a helpful assistant.' },
      { role: 'user', content: 'Say hello.' },
    ],
  });
  logStep('POST /chat/completions', chat);

  // 3) RAG search (basic)
  const rag = await post('/rag/search', { query: 'test', top_k: 3 });
  logStep('POST /rag/search', rag);

  // 4) Audio voices (non-critical)
  let voices = await get('/audio/voices');
  if (!voices.ok) voices = await get('/audio/voices/catalog');
  logStep('GET /audio/voices(*/catalog)', voices);

  // 5) Connectors (optional)
  const connectors = await get('/connectors/providers');
  logStep('GET /connectors/providers', connectors);

  console.log('---');
  if (failures > 0) {
    console.log(`Smoke test completed with ${failures} critical failure(s).`);
    process.exit(1);
  } else {
    console.log('Smoke test completed. Core endpoints reachable.');
    process.exit(0);
  }
})();

