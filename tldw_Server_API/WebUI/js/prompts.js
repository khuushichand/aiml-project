// prompts.js - bind Prompts tab actions without inline handlers

function bindPrompts() {
  const mr = (id, method, path, bodyType) => {
    if (typeof window.makeRequest === 'function') window.makeRequest(id, method, path, bodyType);
  };
  const q = (sel) => document.querySelector(sel);

  // Resolve endpoints via config.json (with fallbacks)
  const pList = (apiClient.endpoint('prompts','list') || '/api/v1/prompts');
  const pSearch = (apiClient.endpoint('prompts','search') || '/api/v1/prompts/search');
  const pGet = (apiClient.endpoint('prompts','get') || '/api/v1/prompts/{prompt_identifier}');
  const pExport = (apiClient.endpoint('prompts','export') || '/api/v1/prompts/export');
  const pCreate = (apiClient.endpoint('prompts','create') || '/api/v1/prompts');
  const pUpdate = (apiClient.endpoint('prompts','update') || '/api/v1/prompts/{prompt_identifier}');
  const pDelete = (apiClient.endpoint('prompts','delete') || '/api/v1/prompts/{prompt_identifier}');
  const pKeywords = (apiClient.endpoint('prompts','keywords') || '/api/v1/prompts/keywords/');

  // Core endpoints
  q('#btnPromptsList')?.addEventListener('click', () => mr('promptsList','GET',pList,'query'));
  q('#btnPromptsSearch')?.addEventListener('click', () => mr('promptsSearch','POST',pSearch,'query'));
  q('#btnPromptsGet')?.addEventListener('click', () => mr('promptsGet','GET',pGet,'none'));
  q('#btnPromptsExport')?.addEventListener('click', () => mr('promptsExport','GET',pExport,'query'));
  q('#btnPromptsCreate')?.addEventListener('click', () => mr('promptsCreate','POST',pCreate,'json'));
  q('#btnPromptsUpdate')?.addEventListener('click', () => mr('promptsUpdate','PUT',pUpdate,'json'));
  q('#btnPromptsDelete')?.addEventListener('click', () => {
    if (confirm('Are you sure you want to delete this prompt?')) {
      mr('promptsDelete','DELETE',pDelete,'none');
    }
  });

  // Keywords
  q('#btnPromptKeywordAdd')?.addEventListener('click', async () => {
    const el = q('#promptsKeyword_text');
    const val = (el?.value || '').trim();
    if (!val) { alert('Please enter a keyword'); return; }
    try {
      const res = await window.apiClient.post(pKeywords, { keyword_text: val });
      q('#promptsKeywords_response').textContent = JSON.stringify(res, null, 2);
      if (el) el.value='';
    } catch (e) { q('#promptsKeywords_response').textContent = `Error: ${e.message}`; }
  });

  q('#btnPromptKeywordList')?.addEventListener('click', async () => {
    try {
      const res = await window.apiClient.get(pKeywords);
      q('#promptsKeywords_response').textContent = JSON.stringify(res, null, 2);
    } catch (e) { q('#promptsKeywords_response').textContent = `Error: ${e.message}`; }
  });

  q('#btnPromptKeywordDelete')?.addEventListener('click', async () => {
    const el = q('#promptsKeyword_delete');
    const val = (el?.value || '').trim();
    if (!val) { alert('Please enter a keyword to delete'); return; }
    if (!confirm(`Delete keyword "${val}"?`)) return;
    try {
      const delPath = (apiClient.endpoint('prompts','keyword_delete', { keyword: val }) || `${pKeywords}${encodeURIComponent(val)}`);
      await window.apiClient.delete(delPath);
      q('#promptsKeywords_response').textContent = 'Keyword deleted successfully';
      if (el) el.value='';
    } catch (e) { q('#promptsKeywords_response').textContent = `Error: ${e.message}`; }
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindPrompts);
else bindPrompts();

export default { bindPrompts };
