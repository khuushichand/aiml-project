// auth-advanced.js
// Binds advanced AuthNZ panel buttons (forgot/reset, verify/resend, MFA, virtual key) without inline handlers.

export async function authForgotPassword() {
  const email = (document.getElementById('authForgot_email')?.value || '').trim();
  if (!email) { Toast.error('Email is required'); return; }
  try {
    const res = await window.apiClient.post('/api/v1/auth/forgot-password', { email });
    const pre = document.getElementById('authForgot_response');
    if (pre) pre.textContent = JSON.stringify(res, null, 2);
    Toast.success('If the email exists, a reset link was sent');
  } catch (e) {
    const pre = document.getElementById('authForgot_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Request failed');
  }
}

export async function authResetPassword() {
  const token = (document.getElementById('authReset_token')?.value || '').trim();
  const newpw = (document.getElementById('authReset_new')?.value || '');
  if (!token || !newpw) { Toast.error('Token and new password required'); return; }
  try {
    const res = await window.apiClient.post('/api/v1/auth/reset-password', { token, new_password: newpw });
    const pre = document.getElementById('authReset_response');
    if (pre) pre.textContent = JSON.stringify(res, null, 2);
    Toast.success('Password updated');
  } catch (e) {
    const pre = document.getElementById('authReset_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Reset failed');
  }
}

export async function authVerifyEmail() {
  const token = (document.getElementById('authVerify_token')?.value || '').trim();
  if (!token) { Toast.error('Token required'); return; }
  try {
    const qs = new URLSearchParams({ token });
    const res = await window.apiClient.get(`/api/v1/auth/verify-email?${qs.toString()}`);
    const pre = document.getElementById('authVerify_response');
    if (pre) pre.textContent = JSON.stringify(res, null, 2);
    Toast.success('Email verified');
  } catch (e) {
    const pre = document.getElementById('authVerify_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Verify failed');
  }
}

export async function authResendVerification() {
  const email = (document.getElementById('authResend_email')?.value || '').trim();
  if (!email) { Toast.error('Email is required'); return; }
  try {
    const res = await window.apiClient.post('/api/v1/auth/resend-verification', { email });
    const pre = document.getElementById('authResend_response');
    if (pre) pre.textContent = JSON.stringify(res, null, 2);
    Toast.success('Verification email sent (if account exists)');
  } catch (e) {
    const pre = document.getElementById('authResend_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Resend failed');
  }
}

export async function authMfaSetup() {
  try {
    const res = await window.apiClient.post('/api/v1/auth/mfa/setup', {});
    const box = document.getElementById('authMfa_setup');
    if (box) {
      box.innerHTML = '';
      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify({ secret: res.secret, backup_codes: res.backup_codes }, null, 2);
      box.appendChild(pre);
      if (res.qr_code) {
        const img = document.createElement('img');
        img.alt = 'MFA QR code';
        img.src = 'data:image/png;base64,' + String(res.qr_code);
        img.style.maxWidth = '160px';
        img.style.border = '1px solid #ddd';
        img.style.marginTop = '8px';
        box.appendChild(img);
      }
    }
    const preOut = document.getElementById('authMfa_response');
    if (preOut) preOut.textContent = JSON.stringify(res, null, 2);
    Toast.success('MFA setup initiated');
  } catch (e) {
    const pre = document.getElementById('authMfa_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('MFA setup failed');
  }
}

export async function authMfaVerify() {
  const token = (document.getElementById('authMfa_token')?.value || '').trim();
  if (!token) { Toast.error('Enter MFA token'); return; }
  try {
    const res = await window.apiClient.post('/api/v1/auth/mfa/verify', { token });
    const pre = document.getElementById('authMfa_response');
    if (pre) pre.textContent = JSON.stringify(res, null, 2);
    Toast.success('MFA enabled');
  } catch (e) {
    const pre = document.getElementById('authMfa_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('MFA verify failed');
  }
}

export async function authMfaDisable() {
  const pw = (document.getElementById('authMfa_disable_password')?.value || '');
  if (!pw) { Toast.error('Password required to disable'); return; }
  try {
    const body = new URLSearchParams();
    body.set('password', pw);
    const res = await window.apiClient.makeRequest('POST', '/api/v1/auth/mfa/disable', {
      body: body.toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    const pre = document.getElementById('authMfa_response');
    if (pre) pre.textContent = JSON.stringify(res, null, 2);
    Toast.success('MFA disabled');
  } catch (e) {
    const pre = document.getElementById('authMfa_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Disable failed');
  }
}

export async function authMintVirtualKey() {
  const ttl_minutes = parseInt(document.getElementById('vk_ttl')?.value || '60', 10);
  const scope = (document.getElementById('vk_scope')?.value || 'workflows').trim();
  const schedule_id = (document.getElementById('vk_schedule')?.value || '').trim() || null;
  const toList = (val) => (val || '').split(',').map(s => s.trim()).filter(Boolean);
  const allowed_endpoints = toList(document.getElementById('vk_endpoints')?.value);
  const allowed_methods = toList(document.getElementById('vk_methods')?.value);
  const allowed_paths = toList(document.getElementById('vk_paths')?.value);
  const max_calls = document.getElementById('vk_calls')?.value ? parseInt(document.getElementById('vk_calls').value, 10) : null;
  const max_runs = document.getElementById('vk_runs')?.value ? parseInt(document.getElementById('vk_runs').value, 10) : null;
  const not_before = (document.getElementById('vk_nbf')?.value || '').trim() || null;
  const payload = { ttl_minutes, scope, schedule_id, allowed_endpoints, allowed_methods, allowed_paths, max_calls, max_runs, not_before };
  try {
    const res = await window.apiClient.post('/api/v1/auth/virtual-key', payload);
    const pre = document.getElementById('authVirtualKey_response');
    if (pre) pre.textContent = JSON.stringify(res, null, 2);
    Toast.success('Virtual key minted');
  } catch (e) {
    const pre = document.getElementById('authVirtualKey_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Mint failed');
  }
}

// Event bindings
function bindAuthAdvanced() {
  const btnForgot = document.getElementById('btnAuthForgot');
  if (btnForgot) btnForgot.addEventListener('click', authForgotPassword);
  const btnReset = document.getElementById('btnAuthReset');
  if (btnReset) btnReset.addEventListener('click', authResetPassword);
  const btnVerifyEmail = document.getElementById('btnAuthVerifyEmail');
  if (btnVerifyEmail) btnVerifyEmail.addEventListener('click', authVerifyEmail);
  const btnResend = document.getElementById('btnAuthResend');
  if (btnResend) btnResend.addEventListener('click', authResendVerification);
  const btnMfaSetup = document.getElementById('btnMfaSetup');
  if (btnMfaSetup) btnMfaSetup.addEventListener('click', authMfaSetup);
  const btnMfaVerify = document.getElementById('btnMfaVerify');
  if (btnMfaVerify) btnMfaVerify.addEventListener('click', authMfaVerify);
  const btnMfaDisable = document.getElementById('btnMfaDisable');
  if (btnMfaDisable) btnMfaDisable.addEventListener('click', authMfaDisable);
  const btnMint = document.getElementById('btnMintVirtualKey');
  if (btnMint) btnMint.addEventListener('click', authMintVirtualKey);
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAuthAdvanced);
  } else {
    bindAuthAdvanced();
  }
}

export default {
  authForgotPassword,
  authResetPassword,
  authVerifyEmail,
  authResendVerification,
  authMfaSetup,
  authMfaVerify,
  authMfaDisable,
  authMintVirtualKey,
  bindAuthAdvanced,
};
