(() => {
    'use strict';

    function removeChatMessage(prefix, id) {
        if (typeof chatUI !== 'undefined') {
            chatUI.removeMessage(prefix, id);
        }
    }

    function addChatMessage(prefix, role, content) {
        if (typeof chatUI !== 'undefined') {
            chatUI.addMessage(prefix, role, content);
        }
    }

    function toggleRawJson(prefix) {
        const useRawJsonCheckbox = document.getElementById(`${prefix}_useRawJson`);
        if (!useRawJsonCheckbox) return;
        const useRawJson = useRawJsonCheckbox.checked;

        const formFieldsDiv = document.getElementById(`${prefix}_formFields`);
        const rawJsonContainerDiv = document.getElementById(`${prefix}_rawJsonContainer`);
        const rawPayloadTextarea = document.getElementById(`${prefix}_payload_raw`);

        if (formFieldsDiv) formFieldsDiv.style.display = useRawJson ? 'none' : 'block';
        if (rawJsonContainerDiv) rawJsonContainerDiv.style.display = useRawJson ? 'block' : 'none';

        if (useRawJson && rawPayloadTextarea && typeof chatUI !== 'undefined') {
            try {
                const currentPayload = chatUI.buildPayload(prefix);
                rawPayloadTextarea.value = JSON.stringify(currentPayload, null, 2);
            } catch (e) {
                console.warn('Could not build payload for raw view:', e.message);
                rawPayloadTextarea.value = JSON.stringify({ error_building_payload: e.message }, null, 2);
            }
        }
    }

    function handleChatCompletionsRequest() {
        if (typeof chatUI !== 'undefined') {
            chatUI.sendChatRequest();
        }
    }

    async function makeRequest(endpointId, method, path, bodyType = 'none', queryParams = {}) {
        const responseArea = document.getElementById(`${endpointId}_response`);
        const curlEl = document.getElementById(`${endpointId}_curl`);

        if (!responseArea) {
            console.error(`Response area not found for ${endpointId}`);
            return;
        }

        let processedPath = path;
        let pathParams = [];
        let query = {};
        let body = null;

        try {
            const longRunningPaths = [
                'process-videos', 'process-audios', 'process-ebooks',
                'process-documents', 'process-pdfs', 'mediawiki/ingest-dump',
                'mediawiki/process-dump', 'ingest-web-content'
            ];
            const isLongRunning = longRunningPaths.some((p) => path.includes(p));

            if (isLongRunning) {
                Loading.show(responseArea.parentElement, 'Processing... This may take several minutes. Please wait...');
                responseArea.innerHTML = '<div style="padding: 10px; background: #f0f8ff; border-left: 4px solid #2196F3; margin: 10px 0;">'
                    + '<strong>⏳ Processing in progress...</strong><br>'
                    + 'This operation may take several minutes depending on the file size and processing options.<br>'
                    + 'Please do not refresh the page or close this tab.'
                    + '</div>';
            } else {
                Loading.show(responseArea.parentElement, 'Sending request...');
                responseArea.textContent = '';
            }

            const pathParamRegex = /\{([^}]+)\}/g;
            let match;
            while ((match = pathParamRegex.exec(path)) !== null) {
                pathParams.push(match[1]);
            }

            pathParams.forEach((param) => {
                const inputEl = document.getElementById(`${endpointId}_${param}`);
                if (!inputEl) {
                    Toast.error(`Input field not found for required parameter: ${param}`);
                    throw new Error(`Input field not found for required parameter: ${param}`);
                }

                let value = inputEl.value;
                if (!value || value.trim() === '') {
                    Toast.error(`${param} is required but is empty`);
                    throw new Error(`Missing required path parameter: ${param}`);
                }

                if (inputEl.type === 'number') {
                    const numValue = parseInt(value, 10);
                    if (Number.isNaN(numValue)) {
                        Toast.error(`${param} must be a valid number`);
                        throw new Error(`Invalid number for parameter: ${param}`);
                    }
                    value = numValue;
                }

                processedPath = processedPath.replace(`{${param}}`, value);
            });

            if (bodyType === 'json' || bodyType === 'json_with_query') {
                const payloadEl = document.getElementById(`${endpointId}_payload`);
                if (payloadEl) {
                    body = JSON.parse(payloadEl.value);
                } else if (endpointId === 'embeddingsCreate') {
                    const inputEl = document.getElementById('embeddingsCreate_input');
                    const modelEl = document.getElementById('embeddingsCreate_model');
                    const formatEl = document.getElementById('embeddingsCreate_encoding_format');

                    if (inputEl) {
                        body = {
                            input: inputEl.value || '',
                            model: modelEl ? modelEl.value : 'text-embedding-ada-002',
                            encoding_format: formatEl ? formatEl.value : 'float',
                        };
                    }
                }
            }

            if (bodyType === 'query' || bodyType === 'json_with_query') {
                const formGroup = document.getElementById(endpointId);
                if (formGroup) {
                    const inputs = formGroup.querySelectorAll('input[type="text"], input[type="number"], input[type="checkbox"], select');
                    inputs.forEach((input) => {
                        const paramName = input.id.replace(`${endpointId}_`, '');
                        if (pathParams.includes(paramName)) return;
                        if (input.type === 'checkbox') {
                            if (input.checked) query[paramName] = true;
                        } else if (input.value) {
                            query[paramName] = input.value;
                        }
                    });
                }
            }

            if (bodyType === 'form') {
                body = new FormData();
                const formGroup = document.getElementById(endpointId);
                if (formGroup) {
                    const inputs = formGroup.querySelectorAll('input, textarea, select');
                    inputs.forEach((input) => {
                        const key = input.name || input.id.replace(`${endpointId}_`, '');
                        if (key === 'api_name' && input.value && input.value.includes(':')) {
                            const [provider, ...modelParts] = input.value.split(':');
                            body.append('api_provider', provider);
                            body.append('model_name', modelParts.join(':'));
                            body.append('api_name', input.value);
                        } else if (input.type === 'file' && input.files.length > 0) {
                            Array.from(input.files).forEach((file) => body.append(key, file));
                        } else if (input.type === 'checkbox') {
                            body.append(key, input.checked);
                        } else if (input.value) {
                            body.append(key, input.value);
                        }
                    });
                }
            }

            const curlCommand = (typeof apiClient.generateCurlV2 === 'function'
                ? apiClient.generateCurlV2(method, processedPath, { body, query })
                : apiClient.generateCurl(method, processedPath, { body, query }));
            if (curlEl) {
                curlEl.textContent = curlCommand;
            }

            const dlToggle = document.getElementById(`${endpointId}_download`);
            if (dlToggle && dlToggle.checked) {
                const baseUrl = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
                const url = new URL(`${baseUrl}${processedPath}`);
                Object.keys(query || {}).forEach((k) => {
                    const v = query[k];
                    if (v !== undefined && v !== null && v !== '') url.searchParams.append(k, v);
                });
                const headers = {};
                const token = (window.apiClient && window.apiClient.token) ? window.apiClient.token : '';
                if (token) headers['X-API-KEY'] = token;
                const resp = await fetch(url.toString(), { method, headers });
                if (!resp.ok) {
                    const text = await resp.text();
                    throw new Error(`HTTP ${resp.status}: ${text}`);
                }
                const blob = await resp.blob();
                const ct = resp.headers.get('content-type') || '';
                const ext = ct.includes('xml') ? 'xml'
                    : ct.includes('csv') ? 'csv'
                        : ct.includes('html') ? 'html'
                            : 'json';
                const fnameEl = document.getElementById(`${endpointId}_filename`);
                const filename = `${(fnameEl && fnameEl.value) ? fnameEl.value : endpointId}.${ext}`;
                const a = document.createElement('a');
                const href = URL.createObjectURL(blob);
                a.href = href;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(href);
                responseArea.textContent = `(Downloaded ${filename})`;
                return;
            }

            const response = await apiClient.makeRequest(method, processedPath, { body, query });
            if (response === null || response === undefined) {
                responseArea.textContent = '(No content - operation successful)';
            } else if (typeof response === 'object') {
                if (endpointId === 'embeddingsModelsList') {
                    try {
                        const ap = document.getElementById('embeddingsModelsList_allowedProviders');
                        const am = document.getElementById('embeddingsModelsList_allowedModels');
                        if (ap) ap.textContent = JSON.stringify(response.allowed_providers ?? [], null, 2);
                        if (am) am.textContent = JSON.stringify(response.allowed_models ?? [], null, 2);
                    } catch (e) {
                        console.warn('Failed to render allowed lists:', e);
                    }
                }

                // eslint-disable-next-line no-new
                new JSONViewer(responseArea, response, {
                    expanded: 2,
                    theme: webUI.theme,
                    enableCopy: true,
                    enableCollapse: true,
                });

                if (endpointId === 'notesList') {
                    try {
                        const notes = (response && (response.notes || response.items || response.results)) || [];
                        const count = (typeof response.count === 'number') ? response.count : notes.length;
                        const total = (typeof response.total === 'number') ? response.total : '';
                        const limit = (typeof response.limit === 'number') ? response.limit : '';
                        const offset = (typeof response.offset === 'number') ? response.offset : '';

                        const summary = document.getElementById('notesList_summary');
                        if (summary) {
                            summary.textContent = `count=${count}  total=${total}  limit=${limit}  offset=${offset}`;
                        }

                        const table = document.getElementById('notesList_table');
                        if (table) {
                            const tbody = table.querySelector('tbody');
                            if (tbody) {
                                if (!Array.isArray(notes) || notes.length === 0) {
                                    tbody.innerHTML = '<tr><td colspan="4"><em>No notes</em></td></tr>';
                                } else {
                                    const rows = notes.map((n) => {
                                        const title = Utils.escapeHtml(String(n.title ?? 'Untitled'));
                                        const id = Utils.escapeHtml(String(n.id ?? ''));
                                        const ver = Utils.escapeHtml(String(n.version ?? ''));
                                        const lm = Utils.escapeHtml(String(n.last_modified ?? n.updated_at ?? ''));
                                        return `<tr><td>${title}</td><td>${id}</td><td>${ver}</td><td>${lm}</td></tr>`;
                                    }).join('');
                                    tbody.innerHTML = rows;
                                }
                            }
                        }
                    } catch (e) {
                        console.warn('Failed to render notes list summary/table:', e);
                    }
                }

                if (endpointId === 'notesSearch') {
                    try {
                        const notes = Array.isArray(response)
                            ? response
                            : ((response && (response.notes || response.items || response.results)) || []);
                        const count = Array.isArray(notes) ? notes.length : 0;

                        const summary = document.getElementById('notesSearch_summary');
                        if (summary) {
                            summary.textContent = `count=${count}`;
                        }

                        const table = document.getElementById('notesSearch_table');
                        if (table) {
                            const tbody = table.querySelector('tbody');
                            if (tbody) {
                                if (!Array.isArray(notes) || notes.length === 0) {
                                    tbody.innerHTML = '<tr><td colspan="4"><em>No results</em></td></tr>';
                                } else {
                                    const rows = notes.map((n) => {
                                        const title = Utils.escapeHtml(String(n.title ?? 'Untitled'));
                                        const id = Utils.escapeHtml(String(n.id ?? ''));
                                        const ver = Utils.escapeHtml(String(n.version ?? ''));
                                        const lm = Utils.escapeHtml(String(n.last_modified ?? n.updated_at ?? ''));
                                        return `<tr><td>${title}</td><td>${id}</td><td>${ver}</td><td>${lm}</td></tr>`;
                                    }).join('');
                                    tbody.innerHTML = rows;
                                }
                            }
                        }
                    } catch (e) {
                        console.warn('Failed to render notes search summary/table:', e);
                    }
                }
            } else {
                responseArea.textContent = response;
            }

            Toast.success('Request completed successfully');
        } catch (error) {
            console.error('Request error:', error);

            if (error.isTimeout) {
                responseArea.innerHTML = '<div style="padding: 10px; background: #ffebee; border-left: 4px solid #f44336; margin: 10px 0;">'
                    + '<strong>⏱️ Request Timeout</strong><br>'
                    + 'The operation took longer than expected and timed out.<br>'
                    + 'For large files, try:<br>'
                    + '• Using smaller files or shorter videos<br>'
                    + '• Reducing quality settings if available<br>'
                    + '• Processing files one at a time<br><br>'
                    + `<small>Error: ${error.message}</small>`
                    + '</div>';
                Toast.error('Request timed out. The operation may still be processing on the server.');
            } else {
                let hinted = false;
                try {
                    if (error.status === 403 && (processedPath || '').startsWith('/api/v1/mcp')) {
                        let hintText = '';
                        const details = error.details;
                        if (details && typeof details === 'object') {
                            const det = details.detail || details;
                            if (typeof det === 'object' && det.hint) hintText = det.hint;
                            else if (det && det.hint) hintText = det.hint;
                        }
                        if (!hintText) {
                            hintText = 'Permission denied. Ask an admin to grant tools.execute:<tool> or tools.execute:* to your role (Admin → Access Control).';
                        }
                        responseArea.innerHTML = '<div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107; margin: 10px 0;">'
                            + `<strong>🚫 Insufficient permissions</strong><br>${Utils.escapeHtml(hintText)}`
                            + '</div>';
                        Toast.warning('Permission denied (HTTP 403)');
                        hinted = true;
                    }
                } catch (e) {
                    // ignore
                }

                if (!hinted) {
                    responseArea.textContent = `Error: ${error.message}`;
                    Toast.error(`Request failed: ${error.message}`);
                }
            }
        } finally {
            Loading.hide(responseArea.parentElement);
        }
    }

    async function embeddingsAdminSubmit(baseId, endpointPath) {
        try {
            const model = (document.getElementById(`${baseId}_model`)?.value || '').trim();
            const providerInput = (document.getElementById(`${baseId}_provider`)?.value || '').trim();
            if (!model) { alert('Enter a model ID'); return; }

            let allowedProviders = null;
            let allowedModels = null;
            try {
                const lists = await apiClient.makeRequest('GET', '/api/v1/embeddings/models');
                allowedProviders = lists?.allowed_providers ?? null;
                allowedModels = lists?.allowed_models ?? null;
            } catch (e) {
                console.warn('Could not fetch models list for pre-check:', e?.message || e);
            }

            const guessProvider = (m) => {
                if (providerInput) return providerInput.toLowerCase();
                if (m.includes('/')) return 'huggingface';
                const knownOpenAI = ['text-embedding-ada-002', 'text-embedding-3-small', 'text-embedding-3-large'];
                if (knownOpenAI.includes(m)) return 'openai';
                return 'huggingface';
            };
            const provider = guessProvider(model);

            let proceed = true;
            const matchesAllowedModel = (m, patterns) => patterns.some((p) => (p.endsWith('*') ? m.startsWith(p.slice(0, -1)) : m === p));
            if (Array.isArray(allowedProviders) && allowedProviders.length > 0 && !allowedProviders.includes(provider)) {
                proceed = confirm(`Provider "${provider}" may be disallowed by policy. Continue anyway?`);
            }
            if (proceed && Array.isArray(allowedModels) && allowedModels.length > 0 && !matchesAllowedModel(model, allowedModels)) {
                proceed = confirm(`Model "${model}" may be disallowed by policy. Continue anyway?`);
            }
            if (!proceed) return;

            const payloadEl = document.getElementById(`${baseId}_payload`);
            const body = providerInput ? { model, provider: providerInput } : { model };
            if (payloadEl) payloadEl.value = JSON.stringify(body, null, 2);
            await makeRequest(baseId, 'POST', endpointPath, 'json');
        } catch (e) {
            alert(`Failed to submit: ${e?.message || e}`);
        }
    }

    async function notesExportDownload(params, filenameBase) {
        try {
            const baseUrl = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
            const url = new URL(`${baseUrl}/api/v1/notes/export`);
            Object.entries(params || {}).forEach(([k, v]) => {
                if (v !== undefined && v !== null && v !== '') url.searchParams.append(k, String(v));
            });
            url.searchParams.set('format', 'csv');

            const headers = {};
            const token = (window.apiClient && window.apiClient.token) ? window.apiClient.token : '';
            if (token) headers['X-API-KEY'] = token;

            const resp = await fetch(url.toString(), { method: 'GET', headers });
            if (!resp.ok) {
                const text = await resp.text();
                throw new Error(`HTTP ${resp.status}: ${text}`);
            }
            const blob = await resp.blob();
            const a = document.createElement('a');
            const href = URL.createObjectURL(blob);
            a.href = href;
            a.download = `${filenameBase || 'notes_export'}.csv`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(href);
            Toast.success('Downloaded CSV');
        } catch (e) {
            Toast.error(e?.message || String(e));
        }
    }

    async function notesDownloadVisibleList() {
        try {
            const limit = document.getElementById('notesList_limit')?.value || '20';
            const offset = document.getElementById('notesList_offset')?.value || '0';
            const includeKeywords = document.getElementById('notesList_include_keywords')?.checked ? 'true' : '';
            const filename = document.getElementById('notesList_dl_filename')?.value || 'notes_visible';
            await notesExportDownload({ limit, offset, include_keywords: includeKeywords }, filename);
        } catch (e) {
            // no-op
        }
    }

    async function notesDownloadVisibleSearch() {
        try {
            const q = document.getElementById('notesSearch_query')?.value || '';
            const limit = document.getElementById('notesSearch_limit')?.value || '10';
            const includeKeywords = document.getElementById('notesSearch_include_keywords')?.checked ? 'true' : '';
            const filename = document.getElementById('notesSearch_dl_filename')?.value || 'notes_search';
            await notesExportDownload({ q, limit, offset: 0, include_keywords: includeKeywords }, filename);
        } catch (e) {
            // no-op
        }
    }

    window.removeChatMessage = removeChatMessage;
    window.addChatMessage = addChatMessage;
    window.toggleRawJson = toggleRawJson;
    window.handleChatCompletionsRequest = handleChatCompletionsRequest;
    window.makeRequest = makeRequest;
    window.embeddingsAdminSubmit = embeddingsAdminSubmit;
    window.notesExportDownload = notesExportDownload;
    window.notesDownloadVisibleList = notesDownloadVisibleList;
    window.notesDownloadVisibleSearch = notesDownloadVisibleSearch;
})();

// Populate the Create Embeddings model dropdown from backend listing
async function populateEmbeddingsCreateModelDropdown() {
    try {
        const sel = document.getElementById('embeddingsCreate_model');
        if (!sel) return;
        // Show loading state
        sel.innerHTML = '';
        const loading = document.createElement('option');
        loading.value = '';
        loading.textContent = 'Loading models…';
        sel.appendChild(loading);

        const baseUrl = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
        const token = (window.apiClient && window.apiClient.token) ? window.apiClient.token : '';
        const res = await fetch(`${baseUrl}/api/v1/embeddings/models`, {
            headers: {
                ...(token ? { 'X-API-KEY': token } : {}),
            }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        const items = Array.isArray(payload?.data) ? payload.data : [];
        const allowed = items.filter(i => i && (i.allowed !== false));
        // Group options by provider
        sel.innerHTML = '';
        const providers = {};
        allowed.forEach(i => {
            const p = String(i.provider || '').toLowerCase() || 'unknown';
            if (!providers[p]) providers[p] = [];
            providers[p].push(i);
        });
        let selectedSet = false;
        Object.keys(providers).sort().forEach(p => {
            const og = document.createElement('optgroup');
            og.label = p;
            providers[p].sort((a,b) => String(a.model).localeCompare(String(b.model))).forEach(i => {
                const opt = document.createElement('option');
                opt.value = i.model;
                const isDefault = !!i.default;
                opt.textContent = `${p}:${i.model}${isDefault ? ' (default)' : ''}`;
                if (isDefault && !selectedSet) {
                    opt.selected = true;
                    selectedSet = true;
                }
                og.appendChild(opt);
            });
            sel.appendChild(og);
        });
        // Fallback default if none marked
        if (!selectedSet && sel.options.length > 0) {
            sel.selectedIndex = 0;
        }
    } catch (e) {
        // Fallback to a minimal static list if server call fails
        try {
            const sel = document.getElementById('embeddingsCreate_model');
            if (!sel) return;
            sel.innerHTML = '';
            const opts = [
                { value: 'text-embedding-3-small', label: 'openai:text-embedding-3-small' },
                { value: 'sentence-transformers/all-MiniLM-L6-v2', label: 'huggingface:sentence-transformers/all-MiniLM-L6-v2' },
            ];
            opts.forEach(o => { const opt = document.createElement('option'); opt.value = o.value; opt.textContent = o.label; sel.appendChild(opt); });
        } catch (_) { /* ignore */ }
    }
}

// Expose for main.js to invoke on tab activation
window.populateEmbeddingsCreateModelDropdown = populateEmbeddingsCreateModelDropdown;
