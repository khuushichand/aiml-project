import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('admin-advanced module', async () => {
  let mod;
  beforeEach(async () => {
    document.body.innerHTML = `
      <div>
        <input id="org_name" /><input id="org_slug" /><input id="org_owner" />
        <div id="adminOrgsTeams_result"></div>
        <div id="adminOrgs_list"></div>

        <input id="rl_kind" value="ip" />
        <input id="rl_identifier" value="203.0.113.7" />
        <input id="rl_endpoint" value="/api/v1/media/process" />
        <select id="rl_dry"><option value="true" selected>true</option></select>
        <pre id="adminRateLimits_result"></pre>

        <input id="admVK_userId" value="42" />
        <div id="adminVirtualKeys_list"></div>
        <pre id="adminVirtualKeys_result"></pre>

        <input id="m_team" value="10" />
        <input id="m_user" value="11" />
        <input id="m_role" value="member" />
        <pre id="adminOrgsTeams_result"></pre>
      </div>`;
    global.window.apiClient = {
      post: vi.fn(async (path, body) => ({ path, body })),
      get: vi.fn(async (path) => ({ path })),
      delete: vi.fn(async (path) => ({ path })),
    };
    // basic HTML escape for safety-sensitive render tests
    global.Utils = { escapeHtml: (s) => String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;') };
    global.Toast = { success: vi.fn(), error: vi.fn() };
    mod = await import('../../js/admin-advanced.js');
  });

  it('creates org with provided fields', async () => {
    document.getElementById('org_name').value = 'Acme';
    document.getElementById('org_slug').value = 'acme';
    document.getElementById('org_owner').value = '7';
    await mod.default.admCreateOrg();
    const call = window.apiClient.post.mock.calls.find(c => c[0] === '/api/v1/admin/orgs');
    expect(call).toBeTruthy();
    expect(call[1]).toEqual({ name: 'Acme', slug: 'acme', owner_user_id: 7 });
  });

  it('resets rate limit with ip + endpoint', async () => {
    await mod.default.rlReset();
    const call = window.apiClient.post.mock.calls.find(c => c[0] === '/api/v1/admin/rate-limits/reset');
    expect(call).toBeTruthy();
    expect(call[1]).toEqual({ kind: 'ip', dry_run: true, ip: '203.0.113.7', endpoint: '/api/v1/media/process' });
  });

  it('adds team member with correct payload', async () => {
    await mod.default.admAddTeamMember();
    const call = window.apiClient.post.mock.calls.find(c => c[0] === '/api/v1/admin/teams/10/members');
    expect(call).toBeTruthy();
    expect(call[1]).toEqual({ user_id: 11, role: 'member' });
  });

  it('LLM usage query builds correct URL and renders text', async () => {
    document.body.insertAdjacentHTML('beforeend', `
      <input id="adminLLM_user_id" value="7" />
      <input id="adminLLM_provider" value="openai" />
      <input id="adminLLM_model" value="gpt-4o" />
      <select id="adminLLM_operation"><option value="chat" selected>chat</option></select>
      <input id="adminLLM_status" value="200" />
      <input id="adminLLM_limit" value="50" />
      <input id="adminLLM_start" value="2025-01-01" />
      <input id="adminLLM_end" value="2025-01-31" />
      <pre id="adminLLMUsage_result"></pre>
    `);
    window.apiClient.get = vi.fn(async (url) => ({ items: [] , url}));
    await mod.default.adminQueryLLMUsage();
    const call = window.apiClient.get.mock.calls[0][0];
    expect(call).toContain('/api/v1/admin/llm-usage?');
    expect(call).toContain('user_id=7');
    expect(call).toContain('provider=openai');
    expect(document.getElementById('adminLLMUsage_result').textContent).toContain('No data');
  });

  it('LLM usage CSV opens new window with expected URL', async () => {
    document.body.insertAdjacentHTML('beforeend', `
      <input id="adminLLM_user_id" value="" />
      <input id="adminLLM_provider" value="mistral" />
      <input id="adminLLM_model" value="" />
      <select id="adminLLM_operation"><option value="" selected>All</option></select>
      <input id="adminLLM_status" value="" />
      <input id="adminLLM_limit" value="" />
      <input id="adminLLM_start" value="" />
      <input id="adminLLM_end" value="" />
    `);
    const spy = vi.spyOn(window, 'open').mockImplementation(() => {});
    mod.default.adminDownloadLLMUsageCSV();
    expect(spy).toHaveBeenCalled();
    const url = spy.mock.calls[0][0];
    expect(url.startsWith('/api/v1/admin/llm-usage/export.csv')).toBe(true);
    spy.mockRestore();
  });

  it('Audit export download uses Utils.downloadData and builds query', async () => {
    document.body.insertAdjacentHTML('beforeend', `
      <select id="audit_format"><option value="json" selected>json</option></select>
      <input id="audit_min_risk" value="70" />
      <input id="audit_user_id" value="" />
      <input id="audit_event_type" value="API_REQUEST" />
      <input id="audit_category" value="API_CALL" />
      <input id="audit_filename" value="audit.json" />
      <input id="audit_start" value="2025-01-01T00:00:00+00:00" />
      <input id="audit_end" value="2025-01-02T00:00:00+00:00" />
    `);
    window.apiClient.baseUrl = '';
    global.fetch = vi.fn(async () => ({ ok: true, text: async () => '[]' }));
    const dl = vi.spyOn(Utils, 'downloadData').mockImplementation(() => {});
    await mod.default.adminAuditDownload();
    expect(dl).toHaveBeenCalled();
    const url = fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/audit/export?');
    expect(url).toContain('min_risk_score=70');
    dl.mockRestore();
  });

  it('Audit preview renders text into pre element', async () => {
    document.body.insertAdjacentHTML('beforeend', `
      <select id="audit_format"><option value="csv">csv</option></select>
      <pre id="adminAuditPreview"></pre>
    `);
    window.apiClient.baseUrl = '';
    global.fetch = vi.fn(async () => ({ ok: true, text: async () => '[{"x":1}]' }));
    await mod.default.adminAuditPreviewJSON();
    expect(document.getElementById('adminAuditPreview').textContent).toContain('x');
  });

  it('Charts render with escaped labels and legend toggle hides bars', async () => {
    document.body.insertAdjacentHTML('beforeend', `
      <input id="adminLLMCharts_start" value="" />
      <input id="adminLLMCharts_end" value="" />
      <input id="llmCharts_topN" value="5" />
      <select id="llmCharts_model_metric"><option value="tokens" selected>tokens</option></select>
      <select id="llmCharts_model_palette"><option value="distinct" selected>distinct</option></select>
      <select id="llmCharts_provider_metric"><option value="cost" selected>cost</option></select>
      <div id="llmChartTopSpenders"></div><div id="llmLegendTopSpenders"></div>
      <div id="llmChartModelMix"></div><div id="llmLegendModelMix"></div>
      <div id="llmChartProviderMix"></div><div id="llmLegendProviderMix"></div>
    `);
    // Malicious-like labels
    const calls = [];
    window.apiClient.get = vi.fn(async (url) => {
      calls.push(url);
      if (url.includes('top-spenders')) return { items: [{ user_id: '<img src=x>', total_cost_usd: 1 }] };
      if (url.includes('group_by=model')) return { items: [{ group_value: '<b>bold</b>', total_tokens: 2 }] };
      if (url.includes('group_by=provider')) return { items: [{ group_value: '<svg>', total_cost_usd: 3 }] };
      return { items: [] };
    });
    await mod.default.adminLoadLLMCharts();
    // Ensure tags not injected
    expect(document.getElementById('llmChartTopSpenders').innerHTML).not.toContain('<img');
    expect(document.getElementById('llmChartModelMix').innerHTML).not.toContain('<b>');
    // Legend toggle hides bars
    const firstLegend = document.querySelector('#llmLegendTopSpenders .legend-item');
    expect(firstLegend).toBeTruthy();
    firstLegend.click();
    const label = firstLegend.textContent.trim();
    const bar = document.querySelector(`#llmChartTopSpenders .chart-bar[data-label="${label}"]`);
    expect(bar.classList.contains('hidden')).toBe(true);
  });
});
