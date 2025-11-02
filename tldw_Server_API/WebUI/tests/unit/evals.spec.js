/* @vitest-environment jsdom */
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('Evals module bindings', () => {
  beforeEach(async () => {
    document.body.innerHTML = `
      <select id="evalsCreate_model"><option value="prov/modelA">modelA</option></select>
      <textarea id="evalsCreate_payload">{"config":{}}</textarea>
      <select id="geval_model"><option value="prov/modelB">modelB</option></select>
      <textarea id="geval_payload">{"model":"x"}</textarea>
      <button id="btnRagEvalRefreshPresets"></button>
      <button data-req-section="evalsCreate" data-req-method="POST" data-req-path="/api/v1/evaluations" data-req-body-type="json"></button>
    `;
    // mock makeRequest for data-req
    global.makeRequest = vi.fn();
    await import('../../js/evals.js');
  });

  it('updates JSON payloads on model select change', () => {
    const sel1 = document.getElementById('evalsCreate_model');
    const ta1 = document.getElementById('evalsCreate_payload');
    sel1.value = 'prov/modelA';
    sel1.dispatchEvent(new Event('change'));
    expect(JSON.parse(ta1.value).config.model).toBe('modelA');

    const sel2 = document.getElementById('geval_model');
    const ta2 = document.getElementById('geval_payload');
    sel2.value = 'prov/modelB';
    sel2.dispatchEvent(new Event('change'));
    expect(JSON.parse(ta2.value).model).toBe('modelB');
  });

  it('delegates data-req buttons to makeRequest', () => {
    const btn = document.querySelector('button[data-req-section]');
    btn.click();
    expect(global.makeRequest).toHaveBeenCalledWith('evalsCreate', 'POST', '/api/v1/evaluations', 'json');
  });
});
