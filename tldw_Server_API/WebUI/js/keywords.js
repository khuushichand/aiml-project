// Keywords Tab Logic (extracted to external file to avoid inline scripts)
(function () {
  'use strict';

  async function addKeyword() {
    const input = document.getElementById('keywordAdd_text');
    const keywordText = (input && input.value ? input.value : '').trim();
    if (!keywordText) { alert('Please enter a keyword'); return; }

    try {
      // Show cURL (auth-aware and masked by default)
      const curl = apiClient.generateCurlV2('POST', '/api/v1/prompts/keywords/', { body: { keyword_text: keywordText } });
      const curlEl = document.getElementById('keywordAdd_curl');
      if (curlEl) curlEl.textContent = curl;

      const response = await apiClient.post('/api/v1/prompts/keywords/', { keyword_text: keywordText });
      const respEl = document.getElementById('keywordAdd_response');
      if (respEl) respEl.textContent = JSON.stringify(response, null, 2);
      if (input) input.value = '';
      loadAllKeywords();
    } catch (error) {
      const respEl = document.getElementById('keywordAdd_response');
      if (respEl) respEl.textContent = `Error: ${error.message}`;
    }
  }

  async function listKeywords() {
    try {
      const curl = apiClient.generateCurlV2('GET', '/api/v1/prompts/keywords/');
      const curlEl = document.getElementById('keywordsList_curl');
      if (curlEl) curlEl.textContent = curl;

      const keywords = await apiClient.get('/api/v1/prompts/keywords/');
      const respEl = document.getElementById('keywordsList_response');
      if (respEl) respEl.textContent = JSON.stringify(keywords, null, 2);
    } catch (error) {
      const respEl = document.getElementById('keywordsList_response');
      if (respEl) respEl.textContent = `Error: ${error.message}`;
    }
  }

  async function deleteKeyword() {
    const input = document.getElementById('keywordDelete_text');
    const keywordText = (input && input.value ? input.value : '').trim();
    if (!keywordText) { alert('Please enter a keyword to delete'); return; }

    try {
      const path = `/api/v1/prompts/keywords/${encodeURIComponent(keywordText)}`;
      const curl = apiClient.generateCurlV2('DELETE', path);
      const curlEl = document.getElementById('keywordDelete_curl');
      if (curlEl) curlEl.textContent = curl;

      if (!confirm(`Delete keyword "${keywordText}"?`)) return;
      await apiClient.delete(path);
      const respEl = document.getElementById('keywordDelete_response');
      if (respEl) respEl.textContent = 'Keyword deleted successfully';
      if (input) input.value = '';
      loadAllKeywords();
    } catch (error) {
      const respEl = document.getElementById('keywordDelete_response');
      if (respEl) respEl.textContent = `Error: ${error.message}`;
    }
  }

  async function loadAllKeywords() {
    const container = document.getElementById('keywords-list');
    if (!container) return;
    try {
      const keywords = await apiClient.get('/api/v1/prompts/keywords/');
      container.innerHTML = '';
      if (!Array.isArray(keywords) || keywords.length === 0) {
        const p = document.createElement('p');
        p.textContent = 'No keywords found.';
        container.appendChild(p);
        return;
      }
      const table = document.createElement('table');
      table.className = 'data-table';
      const thead = document.createElement('thead');
      const thr = document.createElement('tr');
      ['Keyword', 'Actions'].forEach(h => { const th = document.createElement('th'); th.textContent = h; thr.appendChild(th); });
      thead.appendChild(thr);
      const tbody = document.createElement('tbody');
      for (const kw of keywords) {
        const tr = document.createElement('tr');
        const tdKw = document.createElement('td');
        tdKw.textContent = String(kw);
        const tdAct = document.createElement('td');
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-danger';
        btn.textContent = 'Delete';
        btn.addEventListener('click', () => deleteKeywordFromList(String(kw)));
        tdAct.appendChild(btn);
        tr.appendChild(tdKw); tr.appendChild(tdAct);
        tbody.appendChild(tr);
      }
      table.appendChild(thead); table.appendChild(tbody);
      container.appendChild(table);
    } catch (error) {
      container.innerHTML = '';
      const p = document.createElement('p');
      p.className = 'error';
      p.textContent = `Error loading keywords: ${error.message}`;
      container.appendChild(p);
    }
  }

  async function deleteKeywordFromList(keyword) {
    if (!confirm(`Delete keyword "${keyword}"?`)) return;
    await apiClient.delete(`/api/v1/prompts/keywords/${encodeURIComponent(keyword)}`);
    loadAllKeywords();
  }

  // Expose functions for onclick attributes
  if (typeof window !== 'undefined') {
    window.addKeyword = addKeyword;
    window.listKeywords = listKeywords;
    window.deleteKeyword = deleteKeyword;
    window.loadAllKeywords = loadAllKeywords;
    window.deleteKeywordFromList = deleteKeywordFromList;
  }

  // Auto-load keywords when overview tab becomes visible
  document.addEventListener('DOMContentLoaded', () => {
    const overviewTab = document.getElementById('tabKeywordsOverview');
    if (!overviewTab) return;
    try {
      const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
          if (m.type === 'attributes' && m.attributeName === 'style') {
            if (overviewTab && overviewTab.style.display !== 'none') {
              loadAllKeywords();
            }
          }
        }
      });
      observer.observe(overviewTab, { attributes: true });
    } catch (e) { /* ignore */ }
  });
})();
