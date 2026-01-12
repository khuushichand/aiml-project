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

  async function previewInvite(code) {
    if (!code) return;
    try {
      const res = await fetch(`/api/v1/invites/preview?code=${encodeURIComponent(code)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      setOutput('preview_result', data, 'ok');
    } catch (e) {
      setOutput('preview_result', String(e), 'err');
    }
  }

  async function handlePreview(ev) {
    ev.preventDefault();
    const code = document.getElementById('invite_code')?.value.trim();
    await previewInvite(code);
  }

  async function handleRedeem(ev) {
    ev.preventDefault();
    const code = document.getElementById('invite_code')?.value.trim();
    if (!code) return;
    const token = getAccessToken();
    if (!token) {
      setOutput('redeem_result', 'Missing access token. Log in first.', 'err');
      return;
    }
    try {
      const res = await fetch('/api/v1/invites/redeem', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      setOutput('redeem_result', data, 'ok');
    } catch (e) {
      setOutput('redeem_result', String(e), 'err');
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const codeParam = params.get('code');
    if (codeParam) {
      const input = document.getElementById('invite_code');
      if (input) input.value = codeParam;
      previewInvite(codeParam);
    }
    document.getElementById('invite-preview-form')?.addEventListener('submit', handlePreview);
    document.getElementById('invite-redeem-form')?.addEventListener('submit', handleRedeem);
  });
})();
