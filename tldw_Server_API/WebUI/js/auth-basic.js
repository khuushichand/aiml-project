// auth-basic.js
// Externalized bindings for Auth basic flows: login, register, logout, refresh, current user

async function performLogin() {
  const username = document.getElementById('authLogin_username')?.value;
  const password = document.getElementById('authLogin_password')?.value;
  const remember = document.getElementById('authLogin_remember')?.checked;
  if (!username || !password) { Toast.error('Username and password are required'); return; }
  try {
    const response = await window.apiClient.post('/api/v1/auth/login', { username, password, remember_me: !!remember });
    const pre = document.getElementById('authLogin_response'); if (pre) pre.textContent = JSON.stringify(response, null, 2);
    if (response && response.access_token) {
      window.apiClient.setToken(response.access_token);
      Toast.success('Login successful!');
      if (response.refresh_token) { try { Utils.saveToStorage('refresh_token', response.refresh_token); } catch (e) {} }
    }
  } catch (error) {
    const pre = document.getElementById('authLogin_response'); if (pre) pre.textContent = JSON.stringify(error.response || error, null, 2);
    Toast.error('Login failed: ' + (error.message || 'Unknown error'));
  }
}

async function performRegistration() {
  const username = document.getElementById('authRegister_username')?.value;
  const email = document.getElementById('authRegister_email')?.value;
  const password = document.getElementById('authRegister_password')?.value;
  const confirmPassword = document.getElementById('authRegister_confirmPassword')?.value;
  const full_name = document.getElementById('authRegister_fullName')?.value;
  if (!username || !email || !password) { Toast.error('Username, email, and password are required'); return; }
  if (password !== confirmPassword) { Toast.error('Passwords do not match'); return; }
  try {
    const response = await window.apiClient.post('/api/v1/auth/register', { username, email, password, full_name });
    const pre = document.getElementById('authRegister_response'); if (pre) pre.textContent = JSON.stringify(response, null, 2);
    if (response && response.api_key) Toast.success('Registration successful. API key created and shown below. Copy it now.');
    else Toast.success('Registration successful! Please login.');
  } catch (error) {
    const pre = document.getElementById('authRegister_response'); if (pre) pre.textContent = JSON.stringify(error.response || error, null, 2);
    Toast.error('Registration failed: ' + (error.message || 'Unknown error'));
  }
}

async function performLogout() {
  try {
    const all_devices = (document.getElementById('authLogout_all')?.value === 'true');
    const response = await window.apiClient.post('/api/v1/auth/logout', { all_devices });
    const pre = document.getElementById('authLogout_response'); if (pre) pre.textContent = JSON.stringify(response, null, 2);
    window.apiClient.setToken('');
    try { Utils.removeFromStorage('refresh_token'); } catch (e) {}
    Toast.success(all_devices ? 'Logged out from all devices' : 'Logged out successfully');
  } catch (error) {
    const pre = document.getElementById('authLogout_response'); if (pre) pre.textContent = JSON.stringify(error.response || error, null, 2);
    Toast.error('Logout failed: ' + (error.message || 'Unknown error'));
  }
}

async function performTokenRefresh() {
  const refresh_token = document.getElementById('authRefresh_token')?.value;
  if (!refresh_token) { Toast.error('Refresh token is required'); return; }
  try {
    const response = await window.apiClient.post('/api/v1/auth/refresh', { refresh_token });
    const pre = document.getElementById('authRefresh_response'); if (pre) pre.textContent = JSON.stringify(response, null, 2);
    if (response && response.access_token) {
      window.apiClient.setToken(response.access_token);
      Toast.success('Token refreshed successfully');
    }
    if (response && response.refresh_token) { try { Utils.saveToStorage('refresh_token', response.refresh_token); } catch (e) {} }
  } catch (error) {
    const pre = document.getElementById('authRefresh_response'); if (pre) pre.textContent = JSON.stringify(error.response || error, null, 2);
    Toast.error('Token refresh failed: ' + (error.message || 'Unknown error'));
  }
}

async function getCurrentUser() {
  try {
    const response = await window.apiClient.get('/api/v1/auth/me');
    const pre = document.getElementById('authCurrentUser_response'); if (pre) pre.textContent = JSON.stringify(response, null, 2);
  } catch (error) {
    const pre = document.getElementById('authCurrentUser_response'); if (pre) pre.textContent = JSON.stringify(error.response || error, null, 2);
    Toast.error('Failed to get user info: ' + (error.message || 'Unknown error'));
  }
}

function initializeAuthTab() {
  const rt = (typeof Utils !== 'undefined') ? Utils.getFromStorage('refresh_token') : null;
  if (rt && document.getElementById('authRefresh_token')) document.getElementById('authRefresh_token').value = rt;
  try {
    fetch('/api/v1/setup/status', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data && data.needs_setup) { const el = document.getElementById('authSetupBanner'); if (el) el.style.display = ''; } })
      .catch(() => {});
  } catch (e) {}
}

function bindAuthBasic() {
  document.getElementById('btnAuthLogin')?.addEventListener('click', performLogin);
  document.getElementById('btnAuthRegister')?.addEventListener('click', performRegistration);
  document.getElementById('btnAuthLogout')?.addEventListener('click', performLogout);
  document.getElementById('btnAuthRefresh')?.addEventListener('click', performTokenRefresh);
  document.getElementById('btnAuthCurrent')?.addEventListener('click', getCurrentUser);
  // Initialize on auth tab present
  if (document.querySelector('#tabAuth')) initializeAuthTab();
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindAuthBasic);
  else bindAuthBasic();
}

export default {
  performLogin, performRegistration, performLogout, performTokenRefresh, getCurrentUser, initializeAuthTab, bindAuthBasic,
};
