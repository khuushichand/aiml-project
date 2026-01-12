(() => {
  function setOutput(elId, data, klass) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    el.className = klass || '';
  }

  function getAccessToken() {
    try {
      return localStorage.getItem('tldw_access_token');
    } catch {
      return null;
    }
  }

  async function handleAccept(ev) {
    ev.preventDefault();
    const code = document.getElementById('invite_code')?.value.trim();
    if (!code) return;
    const token = getAccessToken();
    if (!token) {
      setOutput('accept_result', 'Missing access token. Log in first.', 'err');
      return;
    }
    try {
      const r = await fetch('/api/v1/orgs/invites/accept', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ code }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || r.statusText);
      setOutput('accept_result', data, 'ok');
    } catch (e) {
      setOutput('accept_result', String(e), 'err');
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    const codeParam = new URLSearchParams(window.location.search).get('code');
    if (codeParam) {
      const input = document.getElementById('invite_code');
      if (input) input.value = codeParam;
    }
    document.getElementById('accept-form')?.addEventListener('submit', handleAccept);
  });
})();
