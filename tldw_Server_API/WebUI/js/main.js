/**
 * Main JavaScript file for API WebUI
 * NOTE: Sanitization and inline-handler migration are delegated to WebUISanitizer (js/sanitizer.js)
 * to keep a single source of truth. Avoid duplicating sanitizer logic here.
 */

// Ensure sanitizer.js is present (loaded before this file in index.html). Calls are guarded at runtime.

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

        // Initialize Simple/Advanced mode toggle and default visibility
        this.initSimpleAdvancedToggle();

        // Force-hide correlation badges unless user has explicitly enabled them
        try {
            if (String(localStorage.getItem('WEBUI_SHOW_CORRELATION')||'') !== '1') {
                const ridEl0 = document.getElementById('reqid-badge');
                const trEl0 = document.getElementById('trace-badge');
                if (ridEl0) ridEl0.style.display = 'none';
                if (trEl0) trEl0.style.display = 'none';
            }
        } catch(_){}

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

        // Proactively migrate any inline handlers present in base HTML
        try { this.migrateInlineHandlers(document.body || document); } catch (_) {}
        // Install CSP guard to sanitize/migrate inline handlers for any dynamic insertions
        try { this.installCSPGuard(); } catch (_) {}

        // Bind generic endpoint exec buttons across the app (no inline handlers)
        try {
            document.addEventListener('click', async (e) => {
                const btn = e.target && e.target.closest('button[data-action="exec-endpoint"]');
                if (!btn) return;
                e.preventDefault();
                const id = btn.getAttribute('data-id');
                const method = btn.getAttribute('data-method') || 'GET';
                const path = btn.getAttribute('data-path') || '';
                const bodyType = btn.getAttribute('data-body') || 'none';
                const confirmMsg = btn.getAttribute('data-confirm') || '';
                if (confirmMsg && !confirm(confirmMsg)) return;
                const responseEl = document.getElementById(`${id}_response`);
                try {
                    if (responseEl) responseEl.textContent = '';
                    // Try global endpointHelper instance if available
                    if (window.endpointHelper && typeof window.endpointHelper.executeRequest === 'function') {
                        await window.endpointHelper.executeRequest(id, method, path, bodyType);
                        return;
                    }
                    const body = (bodyType === 'json') ? (function(){ const ta = document.getElementById(`${id}_payload`); try { return ta && ta.value ? JSON.parse(ta.value) : {}; } catch(_) { return {}; } })() : null;
                    const res = await apiClient.makeRequest(method, path, { body });
                    if (responseEl) responseEl.textContent = (typeof res === 'string') ? res : JSON.stringify(res, null, 2);
                } catch(err) {
                    if (responseEl) responseEl.textContent = `Error: ${err.message}`;
                }
            }, true);
        } catch(_) {}

        console.log('WebUI initialized successfully');
    }

    updateCorrelationBadge(meta) {
        try {
            // Respect user pref to show/hide correlation badges; default: hidden
            let show = false;
            try { show = String(localStorage.getItem('WEBUI_SHOW_CORRELATION')||'') === '1'; } catch(_) {}
            if (!show) return;
            const rid = (meta && meta.requestId) ? String(meta.requestId) : '';
            const trace = (meta && (meta.traceparent || meta.traceId)) ? String(meta.traceparent || meta.traceId) : '';
            const ridEl = document.getElementById('reqid-badge');
            const trEl = document.getElementById('trace-badge');
            if (ridEl) {
                if (rid) {
                    const short = rid.length > 8 ? rid.slice(0, 8) : rid;
                    ridEl.textContent = `RID: ${short}`;
                    ridEl.title = `Last X-Request-ID: ${rid}`;
                    ridEl.style.display = '';
                } else {
                    ridEl.style.display = 'none';
                }
            }
            if (trEl) {
                if (trace) {
                    const shortT = trace.length > 12 ? trace.slice(0, 12) + '…' : trace;
                    trEl.textContent = `Trace: ${shortT}`;
                    trEl.title = `Last traceparent/X-Trace-Id: ${trace}`;
                    trEl.style.display = '';
                } else {
                    trEl.style.display = 'none';
                }
            }
            // Also update correlation snippets in endpoint sections
            try {
                const preEls = document.querySelectorAll('.endpoint-section pre[id$="_response"]');
                preEls.forEach((pre) => {
                    let box = pre.nextElementSibling;
                    if (!(box && box.classList && box.classList.contains('correlation-snippet'))) {
                        box = document.createElement('div');
                        box.className = 'correlation-snippet';
                        box.style.marginTop = '6px';
                        box.style.color = 'var(--color-text-muted)';
                        box.style.fontSize = '0.85em';
                        try { box.setAttribute('aria-live', 'polite'); } catch(_){}
                        const textSpan = document.createElement('span');
                        textSpan.className = 'corr-text';
                        const copyRidBtn = document.createElement('button');
                        copyRidBtn.type = 'button';
                        copyRidBtn.className = 'btn btn-compact corr-copy-btn';
                        copyRidBtn.textContent = 'Copy RID';
                        copyRidBtn.style.marginLeft = '8px';
                        copyRidBtn.addEventListener('click', async (e) => {
                            e.preventDefault();
                            try {
                                const ok = await Utils.copyToClipboard(String(rid || ''));
                                if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied X-Request-ID');
                            } catch (_) {}
                        });
                        const copyTraceBtn = document.createElement('button');
                        copyTraceBtn.type = 'button';
                        copyTraceBtn.className = 'btn btn-compact corr-copy-btn';
                        copyTraceBtn.textContent = 'Copy Trace';
                        copyTraceBtn.style.marginLeft = '6px';
                        copyTraceBtn.addEventListener('click', async (e) => {
                            e.preventDefault();
                            try {
                                const ok = await Utils.copyToClipboard(String(trace || ''));
                                if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied trace');
                            } catch (_) {}
                        });
                        box.appendChild(textSpan);
                        box.appendChild(copyRidBtn);
                        box.appendChild(copyTraceBtn);
                        pre.parentNode.insertBefore(box, pre.nextSibling);
                    }
                    const shortReq = rid && rid.length > 12 ? rid.slice(0, 12) + '…' : (rid || '-');
                    const shortTr = trace && trace.length > 24 ? trace.slice(0, 24) + '…' : (trace || '-');
                    // Update text span if present; else fallback to textContent
                    const textNode = box.querySelector('.corr-text');
                    const content = `Correlation: X-Request-ID=${shortReq}  trace=${shortTr}`;
                    if (textNode) textNode.textContent = content; else box.textContent = content;
                    box.title = `X-Request-ID=${rid || '-'}  traceparent/X-Trace-Id=${trace || '-'}`;
                });
            } catch (_) { /* ignore */ }
        } catch (e) { /* ignore */ }
    }

    // Observe DOM insertions and migrate inline handlers quickly to avoid CSP blocks
    installCSPGuard() {
        const migrateNode = (node) => {
            try {
                if (window.WebUISanitizer && typeof window.WebUISanitizer.migrateInlineHandlers === 'function') {
                    window.WebUISanitizer.migrateInlineHandlers(node);
                } else {
                    this.migrateInlineHandlers(node);
                }
            } catch (_) {}
        };
        try {
            const target = document.querySelector('.content-container') || document.getElementById('main-content-area') || document.body;
            if (!target) return;
            const mo = new MutationObserver((mutations) => {
                for (const m of mutations) {
                    if (m.type === 'childList') {
                        m.addedNodes && m.addedNodes.forEach((n) => { if (n && n.nodeType === 1) migrateNode(n); });
                    } else if (m.type === 'attributes') {
                        if (m.attributeName && m.attributeName.startsWith('on')) {
                            migrateNode(m.target);
                        }
                    }
                }
            });
            mo.observe(target, { subtree: true, childList: true, attributes: true, attributeFilter: ['onclick','onchange','oninput','onsubmit','onkeydown','onkeyup','onload','onerror'] });
            this._cspGuardObserver = mo;
        } catch (_) {}
        // Capture-phase guard for common events: migrate then continue
        const events = ['click','change','input','submit','keydown','keyup','dblclick','focus','blur','mouseenter','mouseleave','mouseover','mouseout','mouseup','mousedown','contextmenu','drag','dragstart','dragend','dragover','drop'];
        events.forEach((evt) => {
            try {
                document.addEventListener(evt, (e) => {
                    const path = (e.composedPath && e.composedPath()) || []; // includes ancestors
                    path.forEach((el) => { if (el && el.nodeType === 1) migrateNode(el); });
                }, true);
            } catch (_) {}
        });
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

            const applyHiddenState = (selector, hidden) => {
                const elements = document.querySelectorAll(selector);
                elements.forEach((el) => {
                    if (!el) return;
                    if (hidden) {
                        try { el.dataset.capabilityHidden = 'true'; } catch (_) { el.setAttribute('data-capability-hidden', 'true'); }
                        el.style.display = 'none';
                    } else {
                        if (el.dataset) {
                            delete el.dataset.capabilityHidden;
                        }
                        el.removeAttribute('data-capability-hidden');
                        el.style.display = '';
                    }
                });
            };
            Object.entries(capabilityToSelectors).forEach(([cap, selectors]) => {
                const enabled = !!caps[cap];
                selectors.forEach((selector) => applyHiddenState(selector, !enabled));
            });
        } catch (e) {
            // Non-fatal
            console.debug('Capability visibility fetch failed:', e);
        }
    }

    initSimpleAdvancedToggle() {
        try {
            const toggle = document.getElementById('toggle-advanced');
            const label = document.getElementById('advanced-toggle-label');
            if (!toggle || !label) return;

            // Determine default visibility: single-user -> hide advanced by default
            let saved = Utils.getFromStorage('show-advanced-panels');
            let defaultShow = true;
            try {
                if (window.apiClient && (window.apiClient.authMode === 'single-user')) {
                    defaultShow = false;
                }
            } catch (_) {}
            const show = (typeof saved === 'boolean') ? saved : defaultShow;
            toggle.checked = !!show;

            const apply = () => {
                const wantShow = !!toggle.checked;
                this.setAdvancedPanelsVisible(wantShow);
                Utils.saveToStorage('show-advanced-panels', wantShow);
                if (!wantShow) {
                    const allowed = new Set(['simple', 'general']);
                    const current = this.activeTopTabButton ? this.activeTopTabButton.dataset.toptab : '';
                    if (!allowed.has(current || '')) {
                        const btn = document.getElementById('top-tab-simple');
                        if (btn) this.activateTopTab(btn);
                    }
                }
            };

            toggle.addEventListener('change', apply);
            apply();
        } catch (e) { /* ignore */ }
    }

    setAdvancedPanelsVisible(visible) {
        try {
            const allowed = new Set(['simple', 'general']);
            document.querySelectorAll('.top-tab-button').forEach((btn) => {
                const t = btn.dataset.toptab;
                if (!t) return;
                if (allowed.has(t)) { btn.style.display = ''; return; }
                if (btn.getAttribute('data-capability-hidden') === 'true') {
                    btn.style.display = 'none';
                    return;
                }
                btn.style.display = visible ? '' : 'none';
            });
            // Hide corresponding subtab rows when advanced hidden
            const rows = document.querySelectorAll('.sub-tab-row');
            const advancedTargets = new Set(['chat', 'media', 'rag', 'workflows', 'prompts', 'notes', 'watchlists', 'persona', 'personalization', 'evaluations', 'keywords', 'embeddings', 'research', 'chatbooks', 'audio', 'admin', 'mcp']);
            rows.forEach((row) => {
                const id = row.id || '';
                if (!id) return;
                const t = id.endsWith('-subtabs') ? id.slice(0, -8) : id;
                if (!advancedTargets.has(t)) return;
                if (row.getAttribute('data-capability-hidden') === 'true') {
                    row.style.display = 'none';
                    return;
                }
                row.style.display = visible ? '' : 'none';
            });
        } catch (e) { /* ignore */ }
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
                // Handle tabs without sub-tabs
                // Map known top-level tabs to their content IDs
                let contentId = topTabName;
                if (topTabName === 'simple') {
                    // The Simple page uses 'tabSimpleLanding' as its content container
                    contentId = 'tabSimpleLanding';
                    // Ensure Simple group scripts are loaded so its initializer is available
                    try {
                        if (window.ModuleLoader && typeof window.ModuleLoader.ensureGroupScriptsLoaded === 'function') {
                            await window.ModuleLoader.ensureGroupScriptsLoaded('simple');
                        }
                    } catch (e) {
                        console.debug('ModuleLoader failed to load simple group scripts', e);
                    }
                }

                this.showContent(contentId);

                // When showing Simple landing directly, run its initializer and mount shared chat
                if (contentId === 'tabSimpleLanding') {
                    try { if (typeof window.initializeSimpleLanding === 'function') window.initializeSimpleLanding(); } catch (_) {}
                    try { if (window.SharedChatPortal && typeof window.SharedChatPortal.mount === 'function') window.SharedChatPortal.mount('simple'); } catch (_) {}
                }
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
        // Infer group for loader when tabs have no explicit loadGroup
        let loaderGroup = loadGroup;
        if (!loaderGroup && contentId) {
            if (contentId.startsWith('tabSimple')) loaderGroup = 'simple';
            else if (contentId.startsWith('tabChat')) loaderGroup = 'chat';
            else if (contentId.startsWith('tabAudio')) loaderGroup = 'audio';
            else if (contentId.startsWith('tabPrompts')) loaderGroup = 'prompts';
            else if (contentId.startsWith('tabRAG')) loaderGroup = 'rag';
            else if (contentId.startsWith('tabEvals') || contentId.startsWith('tabEvaluations')) loaderGroup = 'evaluations';
            else if (contentId.startsWith('tabKeywords')) loaderGroup = 'keywords';
            else if (contentId.startsWith('tabJobs')) loaderGroup = 'jobs';
            else if (contentId.startsWith('tabMedia')) loaderGroup = 'media';
            else if (contentId.startsWith('tabMaintenance')) loaderGroup = 'maintenance';
            else if (contentId.startsWith('tabAuth')) loaderGroup = 'auth';
        }
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

        // Ensure per-group scripts are loaded on demand (keeps initial bundle small)
        try {
            if (loaderGroup && window.ModuleLoader && typeof window.ModuleLoader.ensureGroupScriptsLoaded === 'function') {
                await window.ModuleLoader.ensureGroupScriptsLoaded(loaderGroup);
            }
        } catch (e) {
            console.debug('ModuleLoader ensureGroupScriptsLoaded failed for', loaderGroup, e);
            try {
                if (typeof Toast !== 'undefined' && Toast) {
                    Toast.warning(`Some features may be unavailable for ${loaderGroup} (script load failed)`);
                }
            } catch (_) {}
        }

        // Show the content
        this.showContent(contentId);

        // Re-initialize form handlers for any newly injected content (e.g., file inputs)
        try { this.initFormHandlers(); } catch (_) {}

        // Save active sub-tab to storage
        Utils.saveToStorage('active-sub-tab', contentId);

        // Initialize specific tab functionality if needed
        if (contentId && contentId.startsWith('tabWatchlists') && typeof initializeWatchlistsTab === 'function') {
            initializeWatchlistsTab(contentId);
        }

        if (contentId === 'tabChatCompletions' && typeof initializeChatCompletionsTab === 'function') {
            initializeChatCompletionsTab();
        }
        if (contentId === 'tabSimpleLanding' && typeof window.initializeSimpleLanding === 'function') {
            window.initializeSimpleLanding();
        }
        if (contentId === 'tabChatCompletions' && window.SharedChatPortal && typeof window.SharedChatPortal.mount === 'function') {
            window.SharedChatPortal.mount('advanced');
        }
        if (contentId === 'tabSimpleLanding' && window.SharedChatPortal && typeof window.SharedChatPortal.mount === 'function') {
            window.SharedChatPortal.mount('simple');
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

        if (contentId && (contentId.startsWith('tabAudio') || contentId === 'tabTranscriptSeg') && typeof bindAudioTabHandlers === 'function') {
            bindAudioTabHandlers();
        }
        if (contentId === 'tabAudioStreaming' && window.initializeAudioStreamingTab) {
            try { window.initializeAudioStreamingTab(); } catch (_) {}
        }

        // Metrics tab(s)
        if (contentId && contentId.startsWith('tabMetrics') && typeof window.initializeMetricsTab === 'function') {
            try { window.initializeMetricsTab(contentId); } catch (_) {}
        }

        // Flashcards tab
        if (contentId && contentId.startsWith('tabFlashcards') && typeof initializeFlashcardsTab === 'function') {
            initializeFlashcardsTab(contentId);
        }
        if (contentId && contentId.startsWith('tabMedia') && typeof bindMediaCommonHandlers === 'function') {
            bindMediaCommonHandlers();
        }

        // Vector Stores tab
        if (contentId === 'tabVectorStores' && window.initializeVectorStoresTab) {
            try { window.initializeVectorStoresTab(); } catch (_) {}
        }

        // Personalization tab
        if (contentId === 'tabPersonalization' && typeof window.initializePersonalizationTab === 'function') {
            window.initializePersonalizationTab();
        }

        // Workflows tab(s)
        if (contentId && contentId.startsWith('tabWorkflows') && typeof window.initializeWorkflowsTab === 'function') {
            try { window.initializeWorkflowsTab(contentId); } catch (_) {}
        }

        // Initialize model dropdowns for tabs that have LLM selection
        // This includes chat, media processing, and evaluation tabs
        const tabsWithModelSelection = [
            'tabChatCompletions', 'tabCharacterChat', 'tabConversations',
            'tabMediaIngestion', 'tabMediaProcessingNoDB',
            'tabEvalsOpenAI', 'tabEvalsGEval',
            'tabWebScrapingIngest', 'tabMultiItemAnalysis',
            // Flashcards Import panel includes a model selector for generation
            'tabFlashcardsImport',
            // Simple landing has model selects
            'tabSimpleLanding'
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
        // Resolve relative to current page to avoid base-path issues
        const url = new URL(`tabs/${groupName}_content.html`, window.location.href).toString();
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status} for tabs/${groupName}_content.html`);
        }

        const html = await response.text();
        const mainContentArea = document.getElementById('main-content-area');
        // Sanitize string first so the browser never sees inline handler attributes
        // during parsing (avoids CSP script-src-attr violations).
        const sanitizedHtml = this.sanitizeInlineHandlersAndScripts(html);
        const temp = document.createElement('div');
        temp.innerHTML = sanitizedHtml;
        // Convert preserved handler markers to listeners BEFORE insertion
        try {
            if (window.WebUISanitizer && typeof window.WebUISanitizer.migrateInlineHandlers === 'function') {
                window.WebUISanitizer.migrateInlineHandlers(temp);
            } else {
                this.migrateInlineHandlers(temp);
            }
        } catch (_) {}
        // Move the sanitized nodes into the live DOM to preserve bound listeners
        while (temp.firstChild) {
            mainContentArea.appendChild(temp.firstChild);
        }
        // Group-specific scripts are loaded via ModuleLoader when the tab is activated.

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

    // Remove all <script> tags and migrate inline on* handlers using shared sanitizer
    sanitizeInlineHandlersAndScripts(html) {
        try {
            if (window.WebUISanitizer && typeof window.WebUISanitizer.sanitizeInlineHandlersAndScripts === 'function') {
                return window.WebUISanitizer.sanitizeInlineHandlersAndScripts(html);
            }
            if (window.WebUISanitizer && typeof window.WebUISanitizer.sanitize === 'function') {
                return window.WebUISanitizer.sanitize(html);
            }
        } catch (_) { /* ignore and fall back */ }
        return String(html);
    }

    // Convert inline event attributes (onclick, onchange, etc.) to proper listeners
    migrateInlineHandlers(root) {
        // Delegate to the shared sanitizer as the single source of truth.
        try {
            if (window.WebUISanitizer && typeof window.WebUISanitizer.migrateInlineHandlers === 'function') {
                return window.WebUISanitizer.migrateInlineHandlers(root);
            }
        } catch (_) {}
        // No-op fallback if sanitizer unavailable (tests load sanitizer.js before this file).
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

        // Prefer Simple when advanced panels are hidden
        try {
            const showAdv = Utils.getFromStorage('show-advanced-panels');
            const advVisible = (typeof showAdv === 'boolean') ? showAdv : (window.apiClient?.authMode !== 'single-user');
            if (!advVisible) {
                const btn = document.getElementById('top-tab-simple');
                if (btn) { this.activateTopTab(btn); return; }
            }
        } catch (_) {}

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
                            if (typeof Toast !== 'undefined' && Toast) Toast.success('All endpoints loaded for search');
                        }
                    }
                } catch (e) {
                    if (typeof Toast !== 'undefined' && Toast) {
                        if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load endpoints');
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
        // Ensure any newly inserted file inputs get wrapped/styled
        try { this.initFormHandlers(); } catch (_) {}
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
                if (typeof Toast !== 'undefined' && Toast) Toast.info('No request history available');
            } else {
                alert('No request history available');
            }
            return;
        }

        let historyHtml = `
            <div class="history-list">
                <div class="history-controls mb-3">
                    <button class="btn btn-sm btn-danger" id="clear-history-btn">Clear History</button>
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

        // Bind Clear History button without inline handlers
        try {
            const btn = modal.modal && modal.modal.querySelector('#clear-history-btn');
            if (btn && !btn._bound) {
                btn._bound = true;
                btn.addEventListener('click', (e) => {
                    try { e.preventDefault(); } catch (_) {}
                    try { this.clearHistory(); } catch (_) {}
                });
            }
        } catch (_) { /* ignore */ }
    }

    clearHistory() {
        apiClient.clearHistory();
        if (typeof Toast !== 'undefined' && Toast) {
            if (typeof Toast !== 'undefined' && Toast) Toast.success('Request history cleared');
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
    // Expose instance on window so other modules can reliably detect readiness
    try { window.webUI = webUI; } catch (_) {}
    try { document.dispatchEvent(new Event('webui-ready')); } catch (_) {}
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebUI;
}
