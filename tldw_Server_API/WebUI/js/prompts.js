// prompts.js - bind Prompts tab actions without inline handlers

function bindPrompts() {
  const mr = (id, method, path, bodyType) => {
    if (typeof window.makeRequest === 'function') window.makeRequest(id, method, path, bodyType);
  };
  const q = (sel) => document.querySelector(sel);
  // Core endpoints
  q('#btnPromptsList')?.addEventListener('click', () => mr('promptsList','GET','/api/v1/prompts','query'));
  q('#btnPromptsSearch')?.addEventListener('click', () => mr('promptsSearch','POST','/api/v1/prompts/search','query'));
  q('#btnPromptsGet')?.addEventListener('click', () => mr('promptsGet','GET','/api/v1/prompts/{prompt_identifier}','none'));
  q('#btnPromptsExport')?.addEventListener('click', () => mr('promptsExport','GET','/api/v1/prompts/export','query'));
  q('#btnPromptsCreate')?.addEventListener('click', () => mr('promptsCreate','POST','/api/v1/prompts','json'));
  q('#btnPromptsUpdate')?.addEventListener('click', () => mr('promptsUpdate','PUT','/api/v1/prompts/{prompt_identifier}','json'));
  q('#btnPromptsDelete')?.addEventListener('click', () => {
    if (confirm('Are you sure you want to delete this prompt?')) {
      mr('promptsDelete','DELETE','/api/v1/prompts/{prompt_identifier}','none');
    }
  });

  // Keywords
  q('#btnPromptKeywordAdd')?.addEventListener('click', async () => {
    const el = q('#promptsKeyword_text');
    const val = (el?.value || '').trim();
    if (!val) { alert('Please enter a keyword'); return; }
    try {
      const res = await window.apiClient.post('/api/v1/prompts/keywords/', { keyword_text: val });
      q('#promptsKeywords_response').textContent = JSON.stringify(res, null, 2);
      if (el) el.value='';
    } catch (e) { q('#promptsKeywords_response').textContent = `Error: ${e.message}`; }
  });

  q('#btnPromptKeywordList')?.addEventListener('click', async () => {
    try { const res = await window.apiClient.get('/api/v1/prompts/keywords/');
      q('#promptsKeywords_response').textContent = JSON.stringify(res, null, 2);
    } catch (e) { q('#promptsKeywords_response').textContent = `Error: ${e.message}`; }
  });

  q('#btnPromptKeywordDelete')?.addEventListener('click', async () => {
    const el = q('#promptsKeyword_delete');
    const val = (el?.value || '').trim();
    if (!val) { alert('Please enter a keyword to delete'); return; }
    if (!confirm(`Delete keyword "${val}"?`)) return;
    try { await window.apiClient.delete(`/api/v1/prompts/keywords/${encodeURIComponent(val)}`);
      q('#promptsKeywords_response').textContent = 'Keyword deleted successfully';
      if (el) el.value='';
    } catch (e) { q('#promptsKeywords_response').textContent = `Error: ${e.message}`; }
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindPrompts);
else bindPrompts();

export default { bindPrompts };
