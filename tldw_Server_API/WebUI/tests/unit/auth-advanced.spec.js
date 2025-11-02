import { describe, it, expect, beforeEach, vi } from 'vitest';

// jsdom is provided by vitest env via package.json type module

describe('auth-advanced module', async () => {
  let mod;
  beforeEach(async () => {
    // Reset DOM
    document.body.innerHTML = `
      <div>
        <input id="authMfa_token" />
        <pre id="authMfa_response"></pre>
        <div id="authMfa_setup"></div>
        <input id="authResend_email" />
        <pre id="authResend_response"></pre>
        <textarea id="authReset_token"></textarea>
        <input id="authReset_new" />
        <pre id="authReset_response"></pre>
        <input id="authForgot_email" />
        <pre id="authForgot_response"></pre>
        <pre id="authVirtualKey_response"></pre>
        <input id="vk_ttl" value="45" />
        <input id="vk_scope" value="workflows" />
        <input id="vk_schedule" />
        <input id="vk_endpoints" value="chat.completions,embeddings" />
        <input id="vk_methods" value="GET,POST" />
        <input id="vk_paths" value="/api/v1/chat/completions" />
        <input id="vk_calls" value="10" />
        <input id="vk_runs" value="1" />
        <input id="vk_nbf" value="2025-01-01T00:00:00Z" />
      </div>`;
    // Mock apiClient
    global.window.apiClient = {
      post: vi.fn(async (path, body) => {
        if (path === '/api/v1/auth/mfa/setup') return { secret: 'S', qr_code: 'AAA', backup_codes: ['x'] };
        if (path === '/api/v1/auth/mfa/verify') return { ok: true };
        if (path === '/api/v1/auth/forgot-password') return { message: 'ok' };
        if (path === '/api/v1/auth/reset-password') return { message: 'ok' };
        if (path === '/api/v1/auth/virtual-key') return { token: 'tok', scope: body.scope };
        return { ok: true };
      }),
      get: vi.fn(async (path) => ({ ok: true })),
      makeRequest: vi.fn(async () => ({ message: 'ok' })),
    };
    // Minimal Toast shim
    global.Toast = { success: vi.fn(), error: vi.fn() };
    // Utils shim (escapeHtml not needed here)
    global.Utils = { escapeHtml: (s) => String(s) };
    // Import module
    mod = await import('../../js/auth-advanced.js');
  });

  it('runs MFA setup and verify', async () => {
    await mod.authMfaSetup();
    expect(window.apiClient.post).toHaveBeenCalledWith('/api/v1/auth/mfa/setup', {});
    document.getElementById('authMfa_token').value = '123456';
    await mod.authMfaVerify();
    expect(window.apiClient.post).toHaveBeenCalledWith('/api/v1/auth/mfa/verify', { token: '123456' });
  });

  it('mints self virtual key with proper payload', async () => {
    await mod.authMintVirtualKey();
    const last = window.apiClient.post.mock.calls.find(c => c[0] === '/api/v1/auth/virtual-key');
    expect(last).toBeTruthy();
    const body = last[1];
    expect(body.ttl_minutes).toBe(45);
    expect(body.allowed_endpoints).toEqual(['chat.completions','embeddings']);
    expect(body.allowed_methods).toEqual(['GET','POST']);
    expect(body.allowed_paths).toEqual(['/api/v1/chat/completions']);
    expect(body.max_calls).toBe(10);
    expect(body.max_runs).toBe(1);
  });
});
