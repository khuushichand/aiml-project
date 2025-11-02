/**
 * Main JavaScript file for API WebUI
 */

class WebUI {
    constructor() {
        this.loadedContentGroups = new Set();
        this.activeTopTabButton = null;
        this.activeSubTabButton = null;
        this.apiOnline = false;
        this.searchPreloaded = false;
        this.theme = 'light';
        this.apiStatusCheckInterval = null;
        this.init();
    }

    async init() {
        // Load saved theme
        this.loadTheme();

        // Initialize tabs
        this.initTabs();

        // Initialize global settings
        this.initGlobalSettings();

        // Start API status check
        this.startApiStatusCheck();

        // Initialize keyboard shortcuts
        this.initKeyboardShortcuts();

        // Load default tab
        this.loadDefaultTab();

        // Initialize search functionality
        this.initSearch();

        // Start DLQ badge updates
        this.startDlqBadgeUpdates();
        this.startHydeStatusUpdates();

        // Apply capability-based visibility (hide experimental tabs dynamically)
        this.applyFeatureVisibilityFromServer();

        // If opened via file://, show guidance banner
        if (window.location.protocol === 'file:') {
            try {
                const banner = document.createElement('div');
                banner.style.cssText = 'padding:10px; background:#fff3cd; border:1px solid #ffeeba; color:#856404; text-align:center;';
                banner.innerText = 'Opened from file:// - start the server and use http://127.0.0.1:8000/webui/ for full functionality.';
                const container = document.querySelector('.app-container');
                if (container) container.insertBefore(banner, container.firstChild);
            } catch (e) { /* ignore */ }
        }

        console.log('WebUI initialized successfully');
    }

    async applyFeatureVisibilityFromServer() {
        try {
            const base = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
            const res = await fetch(`${base}/api/v1/config/docs-info`);
            if (!res.ok) return;
            const data = await res.json();
            const caps = (data && (data.capabilities || data.supported_features)) || {};

            // Map capabilities to DOM selectors to hide when disabled
            const capabilityToSelectors = {
                persona: [
                    '.top-tab-button[data-toptab="persona"]',
                    '#persona-subtabs'
                ],
                personalization: [
                    '.top-tab-button[data-toptab="personalization"]',
                    '#personalization-subtabs'
                ],
            };

            const hide = (selector) => { const el = document.querySelector(selector); if (el) el.style.display = 'none'; };
            Object.entries(capabilityToSelectors).forEach(([cap, selectors]) => {
                const enabled = !!caps[cap];
                if (!enabled) selectors.forEach(hide);
            });
        } catch (e) {
            // Non-fatal
            console.debug('Capability visibility fetch failed:', e);
        }
    }

    loadTheme() {
        const savedTheme = Utils.getFromStorage('theme') || 'light';
        this.setTheme(savedTheme);
    }

    setTheme(theme) {
        this.theme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        Utils.saveToStorage('theme', theme);

        // Update theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.innerHTML = theme === 'dark' ? '☀️' : '🌙';
            themeToggle.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
        }
    }

    toggleTheme() {
        this.setTheme(this.theme === 'dark' ? 'light' : 'dark');
    }

    initTabs() {
        // Top level tabs
        const topTabButtons = document.querySelectorAll('.top-tab-button');
        topTabButtons.forEach(btn => {
            btn.addEventListener('click', () => this.activateTopTab(btn));
        });

        // Sub-level tabs
        const subTabButtons = document.querySelectorAll('.sub-tab-button');
        subTabButtons.forEach(btn => {
            btn.addEventListener('click', () => this.activateSubTab(btn));
        });
    }

    async activateTopTab(tabButton) {
        try {
            // Remove active class from previous tab
            if (this.activeTopTabButton) {
                this.activeTopTabButton.classList.remove('active');
                this.activeTopTabButton.setAttribute('aria-selected', 'false');
            }

            // Set new active tab
            this.activeTopTabButton = tabButton;
            this.activeTopTabButton.classList.add('active');
            this.activeTopTabButton.setAttribute('aria-selected', 'true');

            // Get tab name
            const topTabName = tabButton.dataset.toptab;

            // Hide all sub-tab rows
            document.querySelectorAll('.sub-tab-row').forEach(row => {
                row.classList.remove('active');
            });

            // Show corresponding sub-tab row
            const subTabRow = document.getElementById(`${topTabName}-subtabs`);
            if (subTabRow) {
                subTabRow.classList.add('active');
                try { this.activeTopTabButton.setAttribute('aria-controls', `${topTabName}-subtabs`); } catch (e) { /* ignore */ }

                // Activate first sub-tab
                const firstSubTab = subTabRow.querySelector('.sub-tab-button');
                if (firstSubTab) {
                    await this.activateSubTab(firstSubTab);
                }
            } else {
                // Handle tabs without sub-tabs (like Global Settings)
                this.showContent(topTabName);
            }

            // Save active tab to storage
            Utils.saveToStorage('active-top-tab', topTabName);
        } catch (error) {
            console.error('Error activating top tab:', error);
            // Try to show Global Settings as fallback
            const globalSettings = document.getElementById('tabGlobalSettings');
            if (globalSettings) {
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                globalSettings.classList.add('active');
            }
        }
    }

    async activateSubTab(tabButton) {
        const parentRow = tabButton.closest('.sub-tab-row');
        if (!parentRow) return;

        // Remove active class from all sub-tabs in this row
        parentRow.querySelectorAll('.sub-tab-button').forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        });

        // Set new active sub-tab
        this.activeSubTabButton = tabButton;
        this.activeSubTabButton.classList.add('active');
        this.activeSubTabButton.setAttribute('aria-selected', 'true');

        // Get content ID and load group
        const contentId = tabButton.dataset.contentId;
        const loadGroup = tabButton.dataset.loadGroup;
        try { if (contentId) this.activeSubTabButton.setAttribute('aria-controls', contentId); } catch (e) { /* ignore */ }

        // Load content if not already loaded
        if (loadGroup && !this.loadedContentGroups.has(loadGroup)) {
            try {
                if (typeof Loading !== 'undefined' && Loading) {
                    Loading.show(document.querySelector('.content-container'), 'Loading content...');
                }
                await this.loadContentGroup(loadGroup, contentId);
                this.loadedContentGroups.add(loadGroup);
            } catch (error) {
                console.error(`Failed to load content group ${loadGroup}:`, error);
                if (typeof Toast !== 'undefined' && Toast) {
                    Toast.error(`Failed to load content: ${error.message}`);
                } else {
                    // Fallback alert if Toast not available
                    alert(`Failed to load content: ${error.message}`);
                }
            } finally {
                if (typeof Loading !== 'undefined' && Loading) {
                    Loading.hide(document.querySelector('.content-container'));
                }
            }
        }

        // Show the content
        this.showContent(contentId);

        // Save active sub-tab to storage
        Utils.saveToStorage('active-sub-tab', contentId);

        // Initialize specific tab functionality if needed
        if (contentId && contentId.startsWith('tabWatchlists') && typeof initializeWatchlistsTab === 'function') {
            initializeWatchlistsTab(contentId);
        }

        if (contentId === 'tabChatCompletions' && typeof initializeChatCompletionsTab === 'function') {
            initializeChatCompletionsTab();
        }
        if (contentId === 'tabWebScrapingIngest' && typeof initializeWebScrapingIngestTab === 'function') {
            initializeWebScrapingIngestTab();
        }
        if (contentId === 'tabMultiItemAnalysis' && typeof initializeMultiItemAnalysisTab === 'function') {
            initializeMultiItemAnalysisTab();
        }

        if (contentId === 'tabEvalsOpenAI' || contentId === 'tabEvalsGEval') {
            if (typeof initializeEvaluationsTab === 'function') {
                initializeEvaluationsTab();
            }
        }

        if (contentId === 'tabDictionaries' && typeof initializeDictionariesTab === 'function') {
            initializeDictionariesTab();
        }

        // Initialize model dropdowns for tabs that have LLM selection
        // This includes chat, media processing, and evaluation tabs
        const tabsWithModelSelection = [
            'tabChatCompletions', 'tabCharacterChat', 'tabConversations',
            'tabMediaIngestion', 'tabMediaProcessingNoDB',
            'tabEvalsOpenAI', 'tabEvalsGEval',
            'tabWebScrapingIngest', 'tabMultiItemAnalysis'
        ];

        if (tabsWithModelSelection.includes(contentId)) {
            // Small delay to ensure DOM is ready
            setTimeout(() => {
                if (typeof populateModelDropdowns === 'function') {
                    populateModelDropdowns();
                }
            }, 100);
        }

        // Populate Embeddings Create model dropdown dynamically
        if (contentId === 'tabEmbeddingsCreate') {
            setTimeout(() => {
                if (typeof window.populateEmbeddingsCreateModelDropdown === 'function') {
                    window.populateEmbeddingsCreateModelDropdown();
                }
            }, 100);
        }
    }

    async loadContentGroup(groupName, targetContentId) {
        const response = await fetch(`tabs/${groupName}_content.html`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status} for tabs/${groupName}_content.html`);
        }

        const html = await response.text();
        const mainContentArea = document.getElementById('main-content-area');
        // Ensure inline scripts inside tab HTML are executed
        const temp = document.createElement('div');
        temp.innerHTML = html;
        const scripts = Array.from(temp.querySelectorAll('script'));
        scripts.forEach(s => s.parentNode && s.parentNode.removeChild(s));
        mainContentArea.insertAdjacentHTML('beforeend', temp.innerHTML);
        // For migrated groups, skip executing inline scripts (no eval) and only load external src scripts.
        const MIGRATED_GROUPS = new Set(['keywords', 'jobs', 'rag', 'evaluations', 'admin']);
        for (const s of scripts) {
            try {
                if (s.src) {
                    const newScript = document.createElement('script');
                    if (s.type) newScript.type = s.type;
                    newScript.src = s.src;
                    document.body.appendChild(newScript);
                    document.body.removeChild(newScript);
                } else {
                    // Inline script: only execute for non-migrated groups
                    if (!MIGRATED_GROUPS.has(groupName)) {
                        const code = s.textContent || '';
                        (0, eval)(code);
                    } else {
                        console.debug(`Skipped inline script eval for migrated group: ${groupName}`);
                    }
                }
            } catch (e) {
                console.error('Failed to execute inline script for group', groupName, e);
            }
        }
        try {
            window.__groupScriptEval = window.__groupScriptEval || {};
            window.__groupScriptEval[groupName] = (window.__groupScriptEval[groupName] || 0) + scripts.length;
        } catch (e) { /* ignore */ }

        // Re-initialize form handlers for newly loaded content
        this.initFormHandlers();

        // After loading content, ensure all newly loaded tabs are hidden initially
        // This is important when loading multiple tabs from a single HTML file
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });

        // Initialize model dropdowns for groups that contain LLM-using tabs
        const groupsWithModelSelection = ['chat', 'media', 'evaluations'];
        if (groupsWithModelSelection.includes(groupName)) {
            // Populate dropdowns after DOM is updated
            setTimeout(() => {
                if (typeof populateModelDropdowns === 'function') {
                    populateModelDropdowns();
                }
            }, 100);
        }
    }

    // --------------------------
    // DLQ Badge
    // --------------------------
    startDlqBadgeUpdates() {
        const update = async () => {
            try {
                const badge = document.getElementById('dlq-badge');
                if (!badge) return;
                const client = window.apiClient;
                if (!client || !client.token) {
                    return;
                }
                const res = await client.get('/api/v1/embeddings/dlq/stats');
                const total = (res && typeof res.total_dlq === 'number') ? res.total_dlq : 0;
                badge.textContent = `DLQ: ${total}`;
                badge.classList.remove('badge-warn', 'badge-crit');
                if (total >= 100) {
                    badge.classList.add('badge-crit');
                } else if (total >= 10) {
                    badge.classList.add('badge-warn');
                }
            } catch (e) {
                // ignore
            }
        };
        update();
        setInterval(update, 30000);
    }

    startHydeStatusUpdates() {
        const update = async () => {
            try {
                if (typeof embeddingsRefreshHydeStatus === 'function') {
                    await embeddingsRefreshHydeStatus();
                }
            } catch (e) {
                // ignore
            }
        };
        update();
        setInterval(update, 60000);
    }

    showContent(contentId) {
        // Determine previously active tabs for cleanup hooks
        const previouslyActive = Array.from(document.querySelectorAll('.tab-content.active')).map(el => el.id);

        // Hide all tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });

        // Show selected content
        const content = document.getElementById(contentId);
        if (content) {
            content.classList.add('active');
            console.log(`Showing tab: ${contentId}`);
        } else {
            console.warn(`Tab content not found: ${contentId}`);
        }

        // Cleanup timers when leaving certain tabs
        try {
            if (previouslyActive.includes('tabLLMDiagnostics') && contentId !== 'tabLLMDiagnostics') {
                if (typeof window.cleanupLLMDiagnosticsTimers === 'function') {
                    window.cleanupLLMDiagnosticsTimers();
                }
            }
        } catch (e) { /* ignore */ }
    }

    loadDefaultTab() {
        // Try to restore previously active tab
        const savedTopTab = Utils.getFromStorage('active-top-tab');
        const savedSubTab = Utils.getFromStorage('active-sub-tab');

        if (savedTopTab) {
            const tabButton = document.querySelector(`.top-tab-button[data-toptab="${savedTopTab}"]`);
            if (tabButton) {
                this.activateTopTab(tabButton);
                return;
            }
        }

        // Default to General tab (which has Global Settings)
        const defaultTab = document.querySelector('.top-tab-button[data-toptab="general"]');
        if (defaultTab) {
            this.activateTopTab(defaultTab);
        } else {
            // Fallback to first available tab
            const firstTab = document.querySelector('.top-tab-button');
            if (firstTab) {
                this.activateTopTab(firstTab);
            }
        }

        // Ensure at least one content tab is visible
        setTimeout(() => {
            const activeTabs = document.querySelectorAll('.tab-content.active');
            if (activeTabs.length === 0) {
                // Force show Global Settings as fallback
                const globalSettings = document.getElementById('tabGlobalSettings');
                if (globalSettings) {
                    globalSettings.classList.add('active');
                    console.log('Forced Global Settings tab to be visible');
                }
            }
        }, 100);
    }

    async initGlobalSettings() {
        // Wait for API client to load configuration
        if (apiClient.init) {
            await apiClient.init();
        }

        // Load saved API configuration
        const baseUrlInput = document.getElementById('baseUrl');
        const apiKeyInput = document.getElementById('apiKeyInput');

        if (baseUrlInput) {
            baseUrlInput.value = apiClient.baseUrl;
            baseUrlInput.addEventListener('change', (e) => {
                apiClient.setBaseUrl(e.target.value);
                if (typeof Toast !== 'undefined' && Toast) {
                    Toast.success('API base URL updated');
                }
                this.checkApiStatus();
            });
            // Copy base URL button
            const copyBtn = document.getElementById('copyBaseUrlBtn');
            if (copyBtn) {
                copyBtn.addEventListener('click', async () => {
                    const success = await Utils.copyToClipboard(baseUrlInput.value || '');
                    if (typeof Toast !== 'undefined' && Toast) {
                        success ? Toast.success('Copied base URL') : Toast.error('Failed to copy');
                    }
                });
            }
        }

        if (apiKeyInput) {
            apiKeyInput.value = apiClient.token;

            // Show indicator if config was auto-loaded
            if (apiClient.configLoaded && apiClient.token) {
                apiKeyInput.placeholder = 'Auto-configured from server';
                // Add visual indicator
                const label = apiKeyInput.previousElementSibling;
                if (label && label.tagName === 'LABEL') {
                    label.innerHTML = 'API Token: <span style="color: green;">✓ Auto-configured</span>';
                }
            }

            apiKeyInput.addEventListener('change', (e) => {
                apiClient.setToken(e.target.value);
                if (typeof Toast !== 'undefined' && Toast) {
                    Toast.success('API token updated');
                }
            });

            // Toggle visibility button
            const toggleBtn = document.getElementById('toggleApiKeyVisibility');
            if (toggleBtn) {
                toggleBtn.addEventListener('click', () => {
                    if (apiKeyInput.type === 'password') {
                        apiKeyInput.type = 'text';
                        toggleBtn.textContent = 'Hide';
                    } else {
                        apiKeyInput.type = 'password';
                        toggleBtn.textContent = 'Show';
                    }
                });
            }

            // Copy API key button
            const copyApiBtn = document.getElementById('copyApiKeyBtn');
            if (copyApiBtn) {
                copyApiBtn.addEventListener('click', async () => {
                    const success = await Utils.copyToClipboard(apiKeyInput.value || '');
                    if (typeof Toast !== 'undefined' && Toast) {
                        success ? Toast.success('Copied API token') : Toast.error('Failed to copy');
                    }
                });
            }
        }

        // Multi-user API key preference toggle
        const preferToggle = document.getElementById('preferApiKeyInMultiUser');
        if (preferToggle) {
            try {
                preferToggle.checked = !!apiClient.preferApiKeyInMultiUser;
                preferToggle.addEventListener('change', (e) => {
                    apiClient.setPreferApiKeyInMultiUser(e.target.checked);
                    if (typeof Toast !== 'undefined' && Toast) {
                        Toast.success('Auth preference updated');
                    }
                });
            } catch (e) { /* ignore */ }
        }

        // cURL token masking toggle
        const curlToggle = document.getElementById('includeTokenInCurl');
        if (curlToggle) {
            try {
                // Reflect current preference
                curlToggle.checked = !!apiClient.includeTokenInCurl;
                curlToggle.addEventListener('change', (e) => {
                    apiClient.setIncludeTokenInCurl(e.target.checked);
                    if (typeof Toast !== 'undefined' && Toast) {
                        Toast.success(e.target.checked ? 'cURL will include token' : 'cURL will mask token');
                    }
                });
            } catch (e) { /* ignore */ }
        }

        // Quick Actions buttons (no inline handlers due to CSP)
        const btnTestConnection = document.getElementById('btnTestConnection');
        if (btnTestConnection) {
            btnTestConnection.addEventListener('click', () => this.checkApiStatus());
        }
        const btnViewHistory = document.getElementById('btnViewHistory');
        if (btnViewHistory) {
            btnViewHistory.addEventListener('click', () => this.showRequestHistory());
        }
        const btnRefreshPage = document.getElementById('btnRefreshPage');
        if (btnRefreshPage) {
            btnRefreshPage.addEventListener('click', () => window.location.reload());
        }

        // Add theme toggle handler
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
    }

    async checkApiStatus() {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.api-status-text');

        try {
            const startTime = Date.now();
            const health = await apiClient.checkHealth();
            const responseTime = Date.now() - startTime;

            if (health.online) {
                if (statusDot) {
                    statusDot.classList.remove('offline');
                    statusDot.classList.remove('slow');
                    // Add slow indicator if response is slow
                    if (responseTime > 1000) {
                        statusDot.classList.add('slow');
                    }
                }
                if (statusText) {
                    if (responseTime > 1000) {
                        statusText.textContent = `Connected (${responseTime}ms)`;
                    } else {
                        statusText.textContent = 'Connected';
                    }
                    statusText.title = `API: ${apiClient.baseUrl}\nResponse time: ${responseTime}ms`;
                }
                this.apiOnline = true;
                this.updateApiDependentControls(true);
            } else {
                if (statusDot) {
                    statusDot.classList.add('offline');
                    statusDot.classList.remove('slow');
                }
                if (statusText) {
                    statusText.textContent = 'API Offline';
                    statusText.title = `Cannot reach API at ${apiClient.baseUrl}`;
                }
                this.apiOnline = false;
                this.updateApiDependentControls(false);
            }
        } catch (error) {
            if (statusDot) {
                statusDot.classList.add('offline');
                statusDot.classList.remove('slow');
            }
            if (statusText) {
                // More descriptive error messages
                if (error.message.includes('Failed to fetch')) {
                    statusText.textContent = 'API Unreachable';
                    statusText.title = `Cannot connect to ${apiClient.baseUrl}\nCheck if the API server is running`;
                } else if (error.status === 401) {
                    statusText.textContent = 'Auth Failed';
                    statusText.title = 'Authentication failed - check your API token';
                } else {
                    statusText.textContent = `Error (${error.status || 'Network'})`;
                    statusText.title = error.message;
                }
            }
            this.apiOnline = false;
            this.updateApiDependentControls(false);
        }
    }

    startApiStatusCheck() {
        // Initial check
        this.checkApiStatus();

        // Set up periodic check every 30 seconds
        this.apiStatusCheckInterval = setInterval(() => {
            this.checkApiStatus();
        }, 30000);
    }

    stopApiStatusCheck() {
        if (this.apiStatusCheckInterval) {
            clearInterval(this.apiStatusCheckInterval);
            this.apiStatusCheckInterval = null;
        }
    }

    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K: Focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.getElementById('endpoint-search');
                if (searchInput) {
                    const sc = document.querySelector('.search-container');
                    if (sc) sc.classList.add('visible');
                    searchInput.focus();
                }
            }

            // Ctrl/Cmd + Shift + D: Toggle theme
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                this.toggleTheme();
            }

            // Ctrl/Cmd + Shift + H: Show history
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'H') {
                e.preventDefault();
                this.showRequestHistory();
            }

            // Escape: close modals and hide search UI
            if (e.key === 'Escape') {
                const sc = document.querySelector('.search-container');
                if (sc) sc.classList.remove('visible');
                // Modal handling is implemented in Modal
            }
        });
    }

    initSearch() {
        const searchInput = document.getElementById('endpoint-search');
        if (!searchInput) return;

        // Preload all lazy tabs on first focus so search spans all endpoints
        searchInput.addEventListener('focus', async () => {
            if (this.searchPreloaded) return;
            try { await this.preloadAllEndpointsForSearch(); } catch (e) { /* ignore */ }
            this.searchPreloaded = true;
        });

        // Hide search container after blur
        searchInput.addEventListener('blur', () => {
            setTimeout(() => {
                const sc = document.querySelector('.search-container');
                if (sc) sc.classList.remove('visible');
            }, 150);
        });

        const searchHandler = Utils.debounce((e) => {
            const query = e.target.value.toLowerCase();
            this.filterEndpoints(query);
        }, 300);

        searchInput.addEventListener('input', searchHandler);

        // Manual preload button for users who prefer not to auto-preload
        const preloadBtn = document.getElementById('preload-endpoints-btn');
        if (preloadBtn) {
            preloadBtn.addEventListener('click', async () => {
                try {
                    if (!this.searchPreloaded) {
                        await this.preloadAllEndpointsForSearch();
                        this.searchPreloaded = true;
                        if (typeof Toast !== 'undefined' && Toast) {
                            Toast.success('All endpoints loaded for search');
                        }
                    }
                } catch (e) {
                    if (typeof Toast !== 'undefined' && Toast) {
                        Toast.error('Failed to load endpoints');
                    }
                }
            });
        }
    }

    async preloadAllEndpointsForSearch() {
        const groups = new Set(Array.from(document.querySelectorAll('.sub-tab-button'))
            .map(b => b.dataset.loadGroup)
            .filter(Boolean));
        for (const g of groups) {
            if (!this.loadedContentGroups.has(g)) {
                await this.loadContentGroup(g);
                this.loadedContentGroups.add(g);
            }
        }
    }

    filterEndpoints(query) {
        const endpoints = document.querySelectorAll('.endpoint-section');
        let visibleCount = 0;

        endpoints.forEach(endpoint => {
            const title = endpoint.querySelector('h2')?.textContent.toLowerCase() || '';
            const path = endpoint.querySelector('.endpoint-path')?.textContent.toLowerCase() || '';

            if (title.includes(query) || path.includes(query)) {
                endpoint.style.display = 'block';
                visibleCount++;
            } else {
                endpoint.style.display = 'none';
            }
        });

        // Show message if no results
        const noResultsMsg = document.getElementById('no-search-results');
        if (noResultsMsg) {
            noResultsMsg.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    }

    updateApiDependentControls(online) {
        try {
            document.querySelectorAll('.api-button').forEach(btn => {
                btn.setAttribute('data-requires-api', 'true');
                btn.disabled = !online;
                if (!online) btn.title = 'Disabled: API offline'; else btn.removeAttribute('title');
            });
        } catch (e) { /* ignore */ }
    }

    showRequestHistory() {
        const history = apiClient.getHistory();

        if (history.length === 0) {
            if (typeof Toast !== 'undefined' && Toast) {
                Toast.info('No request history available');
            } else {
                alert('No request history available');
            }
            return;
        }

        let historyHtml = `
            <div class="history-list">
                <div class="history-controls mb-3">
                    <button class="btn btn-sm btn-danger" onclick="webUI.clearHistory()">Clear History</button>
                </div>
                <div class="history-items">
        `;

        history.forEach((item, index) => {
            const statusClass = item.success ? 'success' : 'error';
            const timestamp = Utils.formatDate(item.timestamp);
            const duration = Utils.formatDuration(item.duration);
            const safeMethod = Utils.escapeHtml(String(item.method || ''));
            const safePath = Utils.escapeHtml(String(item.path || ''));
            const safeStatus = Utils.escapeHtml(String(item.status || 'Error'));
            const safeError = item.error ? Utils.escapeHtml(String(item.error)) : '';

            historyHtml += `
                <div class="history-item ${statusClass}">
                    <div class="history-item-header">
                        <span class="endpoint-method ${safeMethod.toLowerCase()}">${safeMethod}</span>
                        <span class="history-path">${safePath}</span>
                        <span class="history-status">${safeStatus}</span>
                    </div>
                    <div class="history-item-details">
                        <span class="history-timestamp">${timestamp}</span>
                        <span class="history-duration">${duration}</span>
                    </div>
                    ${safeError ? `<div class="history-error">${safeError}</div>` : ''}
                </div>
            `;
        });

        historyHtml += `
                </div>
            </div>
        `;

        const modal = new Modal({
            title: 'Request History',
            content: historyHtml,
            size: 'large'
        });
        modal.show();
    }

    clearHistory() {
        apiClient.clearHistory();
        if (typeof Toast !== 'undefined' && Toast) {
            Toast.success('Request history cleared');
        }
        // Close any open modals
        document.querySelectorAll('.modal').forEach(modal => {
            modal.remove();
        });
        document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
            backdrop.remove();
        });
    }

    initFormHandlers() {
        // Initialize copy buttons for all pre elements
        document.querySelectorAll('pre').forEach(pre => {
            if (!pre.querySelector('.copy-button')) {
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-button';
                copyBtn.textContent = 'Copy';
                copyBtn.onclick = async () => {
                    const text = pre.textContent.replace('Copy', '').trim();
                    const success = await Utils.copyToClipboard(text);
                    if (success) {
                        copyBtn.textContent = 'Copied!';
                        setTimeout(() => {
                            copyBtn.textContent = 'Copy';
                        }, 2000);
                    }
                };
                pre.appendChild(copyBtn);
            }
        });

        // Initialize file inputs with better UI
        document.querySelectorAll('input[type="file"]').forEach(input => {
            if (!input.parentElement.classList.contains('file-input-wrapper')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'file-input-wrapper';

                const label = document.createElement('label');
                label.className = 'file-input-label';
                label.innerHTML = `
                    <span class="file-input-icon">📁</span>
                    <span class="file-input-text">Choose file or drag here</span>
                `;

                input.parentNode.insertBefore(wrapper, input);
                wrapper.appendChild(input);
                wrapper.appendChild(label);

                // Handle file selection
                input.addEventListener('change', (e) => {
                    if (e.target.files.length > 0) {
                        const file = e.target.files[0];
                        wrapper.classList.add('has-file');
                        label.querySelector('.file-input-text').textContent = file.name;
                        label.querySelector('.file-input-icon').textContent = '📄';
                    } else {
                        wrapper.classList.remove('has-file');
                        label.querySelector('.file-input-text').textContent = 'Choose file or drag here';
                        label.querySelector('.file-input-icon').textContent = '📁';
                    }
                });

                // Handle drag and drop
                wrapper.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    wrapper.classList.add('drag-over');
                });

                wrapper.addEventListener('dragleave', () => {
                    wrapper.classList.remove('drag-over');
                });

                wrapper.addEventListener('drop', (e) => {
                    e.preventDefault();
                    wrapper.classList.remove('drag-over');
                    if (e.dataTransfer.files.length > 0) {
                        input.files = e.dataTransfer.files;
                        input.dispatchEvent(new Event('change'));
                    }
                });
            }
        });
    }
}

// Initialize WebUI when DOM is ready
let webUI;
document.addEventListener('DOMContentLoaded', () => {
    webUI = new WebUI();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebUI;
}
