(() => {
  async function getConfig() {
    try {
      const r = await fetch('/webui/config.json', { cache: 'no-store' });
      return await r.json();
    } catch {
      return { mode: 'unknown' };
    }
  }

  function setOutput(elId, data, klass) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    el.className = klass || '';
  }

  async function handleRegister(ev) {
    ev.preventDefault();
    const username = document.getElementById('reg_username').value.trim();
    const email = document.getElementById('reg_email').value.trim();
    const password = document.getElementById('reg_password').value;
    const registration_code = document.getElementById('reg_code').value.trim() || null;
    try {
      const r = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password, registration_code })
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || r.statusText);
      setOutput('reg_result', data, 'ok');
      if (data && data.api_key) {
        alert('Registration successful. An API key was generated; copy it from the result and store it securely.');
      }
    } catch (e) {
      setOutput('reg_result', String(e), 'err');
    }
  }

  async function handleLogin(ev) {
    ev.preventDefault();
    const username = document.getElementById('login_username').value.trim();
    const password = document.getElementById('login_password').value;
    const form = new URLSearchParams();
    form.set('username', username);
    form.set('password', password);
    try {
      const r = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString()
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || r.statusText);
      if (data.access_token) {
        try { localStorage.setItem('tldw_access_token', data.access_token); } catch (_) {}
      }
      setOutput('login_result', data, 'ok');
    } catch (e) {
      setOutput('login_result', String(e), 'err');
    }
  }

  function handleCopyToken() {
    const pre = document.getElementById('login_result');
    try {
      const obj = JSON.parse(pre.textContent || '');
      if (obj && obj.access_token) {
        navigator.clipboard.writeText(obj.access_token);
        alert('Access token copied to clipboard');
      } else {
        alert('No token found');
      }
    } catch {
      alert('No token found');
    }
  }

  window.addEventListener('DOMContentLoaded', async () => {
    // Mode banner
    try {
      const cfg = await getConfig();
      const modeEl = document.getElementById('mode');
      if (modeEl) modeEl.textContent = (cfg && cfg.mode) ? cfg.mode : 'unknown';
      if (cfg && cfg.mode === 'single-user') {
        document.getElementById('mu_hint')?.classList.remove('hidden');
        document.getElementById('forms')?.classList.add('hidden');
      }
    } catch (_) {}

    // Bind forms
    document.getElementById('reg-form')?.addEventListener('submit', handleRegister);
    document.getElementById('login-form')?.addEventListener('submit', handleLogin);
    document.getElementById('copy-token-btn')?.addEventListener('click', handleCopyToken);

    const codeParam = new URLSearchParams(window.location.search).get('code');
    if (codeParam) {
      const regCode = document.getElementById('reg_code');
      if (regCode) regCode.value = codeParam;
    }
  });
})();
