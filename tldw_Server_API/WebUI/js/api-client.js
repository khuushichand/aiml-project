/**
 * API Client for making requests to the backend
 */

class APIClient {
    constructor() {
        this.baseUrl = 'http://localhost:8000';
        this.token = '';  // Token should be set by user, not hardcoded
        this.requestHistory = [];
        this.maxHistorySize = 50;
        this.configLoaded = false;
        this.authMode = 'unknown'; // 'single-user', 'multi-user', or 'unknown'
        this.preferApiKeyInMultiUser = false; // prefer X-API-KEY in multi-user when supported
        this.websockets = new Map(); // Store active WebSocket connections
        this.activeRequests = new Map(); // Track active fetch requests
        this.csrfToken = null; // Cached CSRF token (double-submit pattern)
        this.includeTokenInCurl = false; // UI preference for cURL token masking
        this.init();
    }

    // Cleanup method to close all connections
    cleanup() {
        // Close all WebSocket connections
        this.websockets.forEach((ws, key) => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.close();
            }
        });
        this.websockets.clear();

        // Abort all active requests
        this.activeRequests.forEach((controller, key) => {
            if (controller) {
                controller.abort();
            }
        });
        this.activeRequests.clear();
    }

    // Create or get WebSocket connection
    getWebSocket(url, options = {}) {
        const key = `${url}_${JSON.stringify(options)}`;

        // Check if we have an existing connection
        if (this.websockets.has(key)) {
            const ws = this.websockets.get(key);
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
                return ws;
            }
            // Connection is closed, remove it
            this.websockets.delete(key);
        }

        // Create new WebSocket
        const ws = new WebSocket(url);

        // Set up auto-cleanup on close
        ws.addEventListener('close', () => {
            this.websockets.delete(key);
        });

        ws.addEventListener('error', () => {
            this.websockets.delete(key);
        });

        // Store the connection
        this.websockets.set(key, ws);

        return ws;
    }

    async init() {
        // Check if we're served from the same origin
        const currentUrl = window.location.href;
        if (currentUrl.includes('/webui/')) {
            // We're being served from the FastAPI server - use same origin
            this.baseUrl = window.location.origin;
            console.log('WebUI served from same origin, using:', this.baseUrl);

            // Try to load dynamic configuration from the server
            try {
                const response = await fetch('/webui/config.json');
                if (response.ok) {
                    const config = await response.json();

                    // Store the loaded config for later use (includes LLM providers)
                    this.loadedConfig = config;

                    // Use apiUrl if provided, otherwise keep same origin
                    if (config.apiUrl) {
                        this.baseUrl = config.apiUrl;
                    }

                    // Store the authentication mode
                    this.authMode = config.mode || 'unknown';
                    // Load multi-user API-key preference
                    try {
                        if (config.auth && typeof config.auth.preferApiKeyInMultiUser !== 'undefined') {
                            const saved = Utils.getFromStorage('api-auth-prefs');
                            if (saved && typeof saved.preferApiKeyInMultiUser === 'boolean') {
                                this.preferApiKeyInMultiUser = saved.preferApiKeyInMultiUser;
                            } else {
                                this.preferApiKeyInMultiUser = !!config.auth.preferApiKeyInMultiUser;
                            }
                        }
                    } catch (e) { /* ignore */ }

                    // Check for API key (will be present in single user mode)
                    if (config.apiKey && config.apiKey !== '') {
                        this.token = config.apiKey;
                        this.configLoaded = true;
                        console.log(`✅ Auto-configured for ${this.authMode} mode`);

                        // Show success message if we got an API key
                        if (this.authMode === 'single-user') {
                            console.log('🔑 API key automatically configured from server');

                            // Update the UI to show auto-configuration
                            setTimeout(() => {
                                const apiKeyInput = document.getElementById('apiKeyInput');
                                if (apiKeyInput) {
                                    apiKeyInput.value = '(Auto-configured)';
                                    apiKeyInput.disabled = true;
                                    apiKeyInput.style.backgroundColor = '#e8f5e9';
                                }

                                // Update any status message
                                const statusElement = document.querySelector('.api-status-text');
                                if (statusElement) {
                                    statusElement.textContent = 'Connected (Single User Mode)';
                                }
                            }, 100);
                        }
                    } else if (this.authMode === 'multi-user') {
                        console.log('🔐 Multi-user mode - manual authentication required');
                    }
                }
            } catch (error) {
                console.log('Could not load dynamic config:', error.message);
            }
        } else {
            // Try to load static configuration from webui-config.json
            try {
                const configPath = '/webui-config.json';
                const response = await fetch(configPath);
                if (response.ok) {
                    const config = await response.json();
                    if (config.apiUrl) {
                        this.baseUrl = config.apiUrl;
                    }
                    if (config.apiKey && config.apiKey !== '') {
                        this.token = config.apiKey;
                        this.configLoaded = true;
                        console.log('Loaded API configuration from webui-config.json');
                    }
                }
            } catch (error) {
                // Config file not found or error reading it, that's okay
                console.log('No webui-config.json found, using defaults');
            }
        }

        // Then load any saved configuration (user overrides)
        const savedConfig = Utils.getFromStorage('api-config');
        if (savedConfig) {
            // Only override if user has explicitly saved settings
            if (savedConfig.baseUrl) {
                this.baseUrl = savedConfig.baseUrl;
            }
            if (savedConfig.token) {
                this.token = savedConfig.token;
            }
        }

        // Load saved auth prefs if present
        try {
            const savedAuth = Utils.getFromStorage('api-auth-prefs');
            if (savedAuth && typeof savedAuth.preferApiKeyInMultiUser === 'boolean') {
                this.preferApiKeyInMultiUser = savedAuth.preferApiKeyInMultiUser;
            }
        } catch (e) { /* ignore */ }

        // Load request history
        const savedHistory = Utils.getFromStorage('request-history');
        if (savedHistory && Array.isArray(savedHistory)) {
            this.requestHistory = savedHistory;
        }

        // Load UI prefs
        try {
            const prefs = Utils.getFromStorage('webui-prefs');
            if (prefs && typeof prefs.includeTokenInCurl === 'boolean') {
                this.includeTokenInCurl = !!prefs.includeTokenInCurl;
            }
        } catch (e) { /* ignore */ }
    }

    setBaseUrl(url) {
        this.baseUrl = url;
        this.saveConfig();
    }

    setToken(token) {
        this.token = token;
        this.saveConfig();
    }

    saveConfig() {
        Utils.saveToStorage('api-config', {
            baseUrl: this.baseUrl,
            token: this.token
        });
    }

    setIncludeTokenInCurl(val) {
        this.includeTokenInCurl = !!val;
        try {
            const prefs = Utils.getFromStorage('webui-prefs') || {};
            prefs.includeTokenInCurl = this.includeTokenInCurl;
            Utils.saveToStorage('webui-prefs', prefs);
        } catch (e) { /* ignore */ }
    }

    _determineCredentialsMode() {
        if (typeof window === 'undefined') {
            return undefined;
        }
        try {
            const resolved = new URL(this.baseUrl, window.location.origin);
            return resolved.origin === window.location.origin ? 'include' : 'omit';
        } catch (e) {
            return undefined;
        }
    }

    _readCsrfFromCookie() {
        if (typeof document === 'undefined') {
            return null;
        }
        try {
            const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
            if (match) {
                return decodeURIComponent(match[1]);
            }
        } catch (e) {
            console.warn('Failed to read CSRF cookie:', e);
        }
        return null;
    }

    _getCsrfToken() {
        const fromCookie = this._readCsrfFromCookie();
        if (fromCookie) {
            this.csrfToken = fromCookie;
            return fromCookie;
        }
        return this.csrfToken;
    }

    _syncCsrfFromResponse(response) {
        try {
            const headerToken = response.headers.get('X-CSRF-Token');
            if (headerToken) {
                this.csrfToken = headerToken;
            }
        } catch (e) {
            console.warn('Failed to read CSRF header:', e);
        }
        const cookieToken = this._readCsrfFromCookie();
        if (cookieToken) {
            this.csrfToken = cookieToken;
        }
    }

    setPreferApiKeyInMultiUser(val) {
        this.preferApiKeyInMultiUser = !!val;
        Utils.saveToStorage('api-auth-prefs', {
            preferApiKeyInMultiUser: this.preferApiKeyInMultiUser
        });
    }

    getTimeoutForEndpoint(path, customTimeout) {
        // If custom timeout is provided, use it
        if (customTimeout !== undefined) {
            return customTimeout;
        }

        // Define longer timeouts for specific endpoints
        const longTimeoutEndpoints = {
            '/api/v1/media/process-videos': 600000,    // 10 minutes
            '/api/v1/media/process-audios': 600000,    // 10 minutes
            '/api/v1/media/process-ebooks': 300000,    // 5 minutes
            '/api/v1/media/process-documents': 300000, // 5 minutes
            '/api/v1/media/process-pdfs': 300000,      // 5 minutes
            '/api/v1/evaluations/ocr-pdf': 300000,      // 5 minutes
            '/api/v1/media/add': 600000,               // 10 minutes
            '/api/v1/media/ingest-web-content': 300000,// 5 minutes
            '/api/v1/media/mediawiki/ingest-dump': 600000, // 10 minutes
            '/api/v1/media/mediawiki/process-dump': 600000, // 10 minutes
        };

        // Check if path matches any long timeout endpoint
        for (const [endpoint, timeout] of Object.entries(longTimeoutEndpoints)) {
            if (path.includes(endpoint)) {
                console.log(`Using extended timeout of ${timeout}ms for ${path}`);
                return timeout;
            }
        }

        // Default timeout for regular endpoints
        return 30000; // 30 seconds
    }

    async makeRequest(method, path, options = {}) {
        const {
            body = null,
            query = {},
            headers = {},
            streaming = false,
            onProgress = null,
            timeout = this.getTimeoutForEndpoint(path, options.timeout),  // Dynamic timeout based on endpoint
            responseType = undefined
        } = options;

        // Build URL with query parameters
        const url = new URL(`${this.baseUrl}${path}`);
        Object.keys(query).forEach(key => {
            if (query[key] !== undefined && query[key] !== null && query[key] !== '') {
                url.searchParams.append(key, query[key]);
            }
        });

        // Prepare fetch options
        const fetchOptions = {
            method,
            headers: {
                'Accept': responseType === 'blob' ? '*/*' : (streaming ? 'text/event-stream' : 'application/json'),
                ...headers
            }
        };

        const credsMode = this._determineCredentialsMode();
        if (credsMode) {
            fetchOptions.credentials = credsMode;
        }

        // Add appropriate authentication header based on mode
        if (this.token) {
            if (this.authMode === 'single-user') {
                fetchOptions.headers['X-API-KEY'] = this.token;
            } else if (this.authMode === 'multi-user') {
                if (this.preferApiKeyInMultiUser) {
                    fetchOptions.headers['X-API-KEY'] = this.token;
                } else {
                    fetchOptions.headers['Authorization'] = `Bearer ${this.token}`;
                }
            } else {
                // Unknown mode - try X-API-KEY first (common for manual setup)
                fetchOptions.headers['X-API-KEY'] = this.token;
            }
        }

        const upperMethod = method.toUpperCase();
        const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(upperMethod);
        if (needsCsrf) {
            const csrfToken = this._getCsrfToken();
            if (csrfToken) {
                fetchOptions.headers['X-CSRF-Token'] = csrfToken;
            }
        }

        // Add body if present
        if (body) {
            if (body instanceof FormData) {
                fetchOptions.body = body;
            } else {
                fetchOptions.headers['Content-Type'] = 'application/json';
                fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body);
            }
        }

        // Record request start time
        const startTime = Date.now();
        const requestKey = `${method}_${path}_${Date.now()}`;

        try {
            // Create abort controller for timeout and tracking
            const controller = new AbortController();
            this.activeRequests.set(requestKey, controller);

            const timeoutId = setTimeout(() => {
                controller.abort();
                this.activeRequests.delete(requestKey);
            }, timeout);

            fetchOptions.signal = controller.signal;

            const response = await fetch(url.toString(), fetchOptions);
            clearTimeout(timeoutId);
            this.activeRequests.delete(requestKey);

            const duration = Date.now() - startTime;

            this._syncCsrfFromResponse(response);

            // Save to history
            this.addToHistory({
                method,
                path,
                url: url.toString(),
                timestamp: startTime,
                duration,
                status: response.status,
                success: response.ok
            });

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                let errorDetails = null;

                try {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        errorDetails = await response.json();
                        // Handle different error response formats
                        if (typeof errorDetails === 'object') {
                            // OpenAI-style error format (used by evaluations endpoint)
                            if (errorDetails.error && typeof errorDetails.error === 'object') {
                                errorMessage = errorDetails.error.message || errorDetails.error.detail || errorMessage;
                            }
                            // FastAPI default error format
                            else if (errorDetails.detail) {
                                // detail can be a string or an array of validation errors
                                if (typeof errorDetails.detail === 'string') {
                                    errorMessage = errorDetails.detail;
                                } else if (Array.isArray(errorDetails.detail)) {
                                    // Validation errors array
                                    errorMessage = errorDetails.detail.map(err =>
                                        err.msg || err.message || JSON.stringify(err)
                                    ).join(', ');
                                } else if (typeof errorDetails.detail === 'object') {
                                    // Complex error object in detail
                                    errorMessage = errorDetails.detail.message || JSON.stringify(errorDetails.detail);
                                }
                            }
                            // Simple message field
                            else if (errorDetails.message) {
                                errorMessage = errorDetails.message;
                            }
                        }
                    } else {
                        const errorText = await response.text();
                        if (errorText) {
                            errorMessage = `${errorMessage}: ${errorText}`;
                        }
                    }
                } catch (e) {
                    // If response parsing fails, use original message
                    console.warn('Failed to parse error response:', e);
                }

                if (response.status === 403) {
                    const notifyCsrfReset = () => {
                        if (typeof Toast !== 'undefined') {
                            Toast.warning('Your session security token expired. A new one was issued-please retry the action.');
                        }
                    };
                    try {
                        if (errorDetails && (errorDetails.detail === 'CSRF token validation failed' || errorDetails.error === 'CSRF token validation failed')) {
                            this.csrfToken = null;
                            notifyCsrfReset();
                        }
                    } catch (e) {
                        this.csrfToken = null;
                        notifyCsrfReset();
                    }
                }

                const error = new Error(errorMessage);
                error.status = response.status;
                error.statusText = response.statusText;
                error.details = errorDetails;
                error.response = response;
                throw error;
            }

            // Handle 204 No Content responses (e.g., DELETE operations)
            if (response.status === 204) {
                return null; // No content to parse
            }

            // Handle streaming responses
            if (streaming && response.body) {
                return this.handleStreamingResponse(response, onProgress);
            }

            // Explicit response type handling for binary/text
            if (responseType === 'blob') {
                return await response.blob();
            }
            if (responseType === 'arraybuffer') {
                return await response.arrayBuffer();
            }
            if (responseType === 'text') {
                return await response.text();
            }

            // Handle regular JSON responses
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }

            return await response.text();
        } catch (error) {
            // Enhanced error handling
            const duration = Date.now() - startTime;

            // Check if it's a timeout error
            let finalError = error;
            if (error.name === 'AbortError') {
                // Create a new error object instead of modifying the existing one
                // (Some browsers have read-only error.message property)
                finalError = new Error(`Request timeout after ${timeout}ms`);
                finalError.name = 'TimeoutError';
                finalError.isTimeout = true;
                finalError.originalError = error;
            }

            // Record error in history with more details
            this.addToHistory({
                method,
                path,
                url: url.toString(),
                timestamp: startTime,
                duration,
                error: finalError.message,
                errorStatus: finalError.status,
                success: false
            });

            // Add request context to error
            finalError.request = {
                method,
                path,
                url: url.toString(),
                duration
            };

            throw finalError;
        }
    }

    async handleStreamingResponse(response, onProgress) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        const chunks = [];

        // Accumulate event lines until a blank line terminates the event
        let eventLines = [];

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const rawLine of lines) {
                const line = rawLine.replace(/\r$/, '');
                if (line === '') {
                    // End of event; join collected data lines
                    if (eventLines.length > 0) {
                        const dataStr = eventLines.join('\n').trim();
                        eventLines = [];
                        if (dataStr === '[DONE]') {
                            return chunks;
                        }
                        if (!dataStr) continue;
                        try {
                            const parsed = JSON.parse(dataStr);
                            chunks.push(parsed);
                            if (onProgress) onProgress(parsed);
                        } catch (e) {
                            console.warn('Failed to parse SSE data:', dataStr);
                        }
                    }
                    continue;
                }

                // Collect only data: lines; allow optional space after colon
                if (line.startsWith('data:')) {
                    const val = line.slice(5).trimStart();
                    eventLines.push(val);
                }
                // Ignore other SSE fields (id:, event:, retry:)
            }
        }

        // Flush any trailing event if stream ended without final blank line
        if (eventLines.length > 0) {
            const dataStr = eventLines.join('\n').trim();
            if (dataStr && dataStr !== '[DONE]') {
                try {
                    const parsed = JSON.parse(dataStr);
                    chunks.push(parsed);
                    if (onProgress) onProgress(parsed);
                } catch (e) {
                    console.warn('Failed to parse SSE data:', dataStr);
                }
            }
        }

        return chunks;
    }

    addToHistory(request) {
        this.requestHistory.unshift(request);
        if (this.requestHistory.length > this.maxHistorySize) {
            this.requestHistory = this.requestHistory.slice(0, this.maxHistorySize);
        }
        Utils.saveToStorage('request-history', this.requestHistory);
    }

    getHistory() {
        return this.requestHistory;
    }

    clearHistory() {
        this.requestHistory = [];
        Utils.saveToStorage('request-history', []);
    }

    // Convenience methods for common HTTP methods
    async get(path, query = {}, options = {}) {
        return this.makeRequest('GET', path, { query, ...options });
    }

    async post(path, body = null, options = {}) {
        return this.makeRequest('POST', path, { body, ...options });
    }

    async put(path, body = null, options = {}) {
        return this.makeRequest('PUT', path, { body, ...options });
    }

    async delete(path, options = {}) {
        return this.makeRequest('DELETE', path, options);
    }

    async patch(path, body = null, options = {}) {
        return this.makeRequest('PATCH', path, { body, ...options });
    }

    // ------------------------------------------------------------
    // Streaming helpers
    // ------------------------------------------------------------
    /**
     * Stream Server-Sent Events and emit parsed JSON events via callback.
     * Returns a handle with abort() and a done promise.
     */
    streamSSE(path, { method = 'GET', query = {}, headers = {}, body = null, onEvent = null, timeout = 600000 } = {}) {
        const url = new URL(`${this.baseUrl}${path}`);
        Object.keys(query || {}).forEach((k) => {
            const v = query[k];
            if (v !== undefined && v !== null && v !== '') url.searchParams.append(k, v);
        });

        const ctrl = new AbortController();
        const fetchHeaders = { 'Accept': 'text/event-stream', ...headers };

        const credsMode = this._determineCredentialsMode();
        if (this.token) {
            if (this.authMode === 'single-user' || (this.authMode === 'multi-user' && this.preferApiKeyInMultiUser)) fetchHeaders['X-API-KEY'] = this.token;
            else if (this.authMode === 'multi-user') fetchHeaders['Authorization'] = `Bearer ${this.token}`;
            else fetchHeaders['X-API-KEY'] = this.token;
        }

        // CSRF for modifying requests (rare for SSE, but be safe)
        const upper = (method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(upper)) {
            const csrf = this._getCsrfToken();
            if (csrf) fetchHeaders['X-CSRF-Token'] = csrf;
        }

        const fetchOptions = { method, headers: fetchHeaders, signal: ctrl.signal };
        if (credsMode) fetchOptions.credentials = credsMode;
        if (body) fetchOptions.body = (typeof body === 'string' || body instanceof FormData) ? body : JSON.stringify(body);

        // Timeout support
        const timer = timeout ? setTimeout(() => { try { ctrl.abort(); } catch(_){} }, timeout) : null;

        const done = (async () => {
            const response = await fetch(url.toString(), fetchOptions);
            if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let eventLines = [];
            try {
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';
                    for (const rawLine of lines) {
                        const line = rawLine.replace(/\r$/, '');
                        if (line === '') {
                            if (eventLines.length > 0) {
                                const dataStr = eventLines.join('\n').trim();
                                eventLines = [];
                                if (dataStr && dataStr !== '[DONE]') {
                                    try {
                                        const parsed = JSON.parse(dataStr);
                                        if (onEvent) onEvent(parsed);
                                    } catch (_) { /* ignore non-JSON */ }
                                }
                            }
                            continue;
                        }
                        if (line.startsWith('data:')) {
                            const val = line.slice(5).trimStart();
                            eventLines.push(val);
                        }
                    }
                }
            } finally {
                if (timer) clearTimeout(timer);
            }
        })();

        return { controller: ctrl, abort: () => ctrl.abort(), done };
    }

    /**
     * Stream binary (or fetch non-streaming binary) with auth/CSRF handled.
     * Returns { response, controller } so callers can read the stream.
     */
    async streamBinary(path, { method = 'POST', headers = {}, body = null, timeout = 600000 } = {}) {
        const url = new URL(`${this.baseUrl}${path}`);
        const ctrl = new AbortController();
        const fetchHeaders = { ...headers };

        const credsMode = this._determineCredentialsMode();
        if (this.token) {
            if (this.authMode === 'single-user' || (this.authMode === 'multi-user' && this.preferApiKeyInMultiUser)) fetchHeaders['X-API-KEY'] = this.token;
            else if (this.authMode === 'multi-user') fetchHeaders['Authorization'] = `Bearer ${this.token}`;
            else fetchHeaders['X-API-KEY'] = this.token;
        }
        const upper = (method || 'POST').toUpperCase();
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(upper)) {
            const csrf = this._getCsrfToken();
            if (csrf) fetchHeaders['X-CSRF-Token'] = csrf;
        }

        const fetchOptions = { method, headers: fetchHeaders, signal: ctrl.signal };
        if (credsMode) fetchOptions.credentials = credsMode;
        if (body) fetchOptions.body = (typeof body === 'string' || body instanceof FormData) ? body : JSON.stringify(body);
        const timer = timeout ? setTimeout(() => { try { ctrl.abort(); } catch(_){} }, timeout) : null;
        try {
            const response = await fetch(url.toString(), fetchOptions);
            if (!response.ok) {
                let msg = `HTTP ${response.status}`;
                try { const t = await response.text(); if (t) msg += `: ${t}`; } catch(_){}
                const err = new Error(msg);
                err.status = response.status;
                throw err;
            }
            return { response, controller: ctrl };
        } finally {
            if (timer) clearTimeout(timer);
        }
    }

    // Generate cURL command for a request
    generateCurl(method, path, options = {}) {
        return this.generateCurlV2(method, path, options);
    }


    // Generate cURL command (auth-aware)
    generateCurlV2(method, path, options = {}) {
        const { body = null, query = {}, headers = {} } = options;

        // Build URL with query parameters
        const url = new URL(`${this.baseUrl}${path}`);
        Object.keys(query).forEach(key => {
            if (query[key] !== undefined && query[key] !== null && query[key] !== '') {
                url.searchParams.append(key, query[key]);
            }
        });

        let curl = `curl -X ${method} "${url.toString()}"`;

        // Add headers
        curl += ` \\
  -H "Accept: application/json"`;

        // Auth header mirrors request behavior (masked by default)
        if (this.token) {
            const shownToken = this.includeTokenInCurl ? this.token : '[REDACTED]';
            if (this.authMode === 'single-user' || (this.authMode === 'multi-user' && this.preferApiKeyInMultiUser)) {
                curl += ` \\
  -H "X-API-KEY: ${shownToken}"`;
            } else if (this.authMode === 'multi-user') {
                curl += ` \\
  -H "Authorization: Bearer ${shownToken}"`;
            } else {
                // Unknown mode - default to API key header
                curl += ` \\
  -H "X-API-KEY: ${shownToken}"`;
            }
        }

        Object.keys(headers).forEach(key => {
            curl += ` \\
  -H "${key}: ${headers[key]}"`;
        });

        // Add body
        if (body) {
            if (body instanceof FormData) {
                for (let [k, value] of body.entries()) {
                    if (value instanceof File) {
                        curl += ` \\
  -F "${k}=@${value.name}"`;
                    } else {
                        curl += ` \\
  -F "${k}=${value}"`;
                    }
                }
            } else {
                curl += ` \\
  -H "Content-Type: application/json"`;
                const bodyStr = typeof body === 'string' ? body : JSON.stringify(body, null, 2);
                curl += ` \\
  -d '${Utils.escapeCurlData(bodyStr)}'`;
            }
        }

        return curl;
    }

    // Check API health/status
    async checkHealth() {
        try {
            const response = await this.get('/health');
            return { online: true, ...response };
        } catch (error) {
            return { online: false, error: error.message };
        }
    }

    // ============================================================
    // LLM Provider Management
    // ============================================================

    /**
     * Get all configured LLM providers with their models
     * @returns {Promise<Object>} Provider information including models
     */
    async getAvailableProviders() {
        try {
            // Check if providers are already cached in config
            if (this.cachedProviders && this.cacheTimestamp &&
                (Date.now() - this.cacheTimestamp) < 300000) { // Cache for 5 minutes
                return this.cachedProviders;
            }

            // Try to get from config first (loaded at startup)
            const config = await this.loadedConfig;
            if (config && config.llm_providers) {
                this.cachedProviders = config.llm_providers;
                this.cacheTimestamp = Date.now();
                return config.llm_providers;
            }

            // Fallback to API endpoint
            const response = await this.get('/api/v1/llm/providers');
            this.cachedProviders = response;
            this.cacheTimestamp = Date.now();
            return response;
        } catch (error) {
            console.error('Failed to get LLM providers:', error);
            // Return empty providers list as fallback
            return {
                providers: [],
                default_provider: 'openai',
                total_configured: 0,
                error: error.message
            };
        }
    }

    /**
     * Get details for a specific provider
     * @param {string} providerName - Name of the provider (e.g., 'openai', 'anthropic')
     * @returns {Promise<Object>} Provider details
     */
    async getProviderDetails(providerName) {
        try {
            const response = await this.get(`/api/v1/llm/providers/${providerName}`);
            return response;
        } catch (error) {
            console.error(`Failed to get provider details for ${providerName}:`, error);
            throw error;
        }
    }

    /**
     * Get all available models across all providers
     * @returns {Promise<Array>} List of all available models
     */
    async getAllAvailableModels() {
        try {
            const response = await this.get('/api/v1/llm/models');
            return response;
        } catch (error) {
            console.error('Failed to get all models:', error);
            return [];
        }
    }

    /**
     * Clear the cached providers to force a refresh
     */
    clearProvidersCache() {
        this.cachedProviders = null;
        this.cacheTimestamp = null;
    }

    /**
     * Populate all model select dropdowns with available LLM providers and models
     */
    async populateModelDropdowns() {
        try {
            // Get available providers from API
            const providersInfo = await this.getAvailableProviders();

            if (!providersInfo || !providersInfo.providers || providersInfo.providers.length === 0) {
                console.warn('No LLM providers configured');
                // Update dropdowns to show no providers available
                document.querySelectorAll('.llm-model-select').forEach(select => {
                    select.innerHTML = '<option value="">No models available - check configuration</option>';
                });
                return;
            }

            // Build options HTML grouped by provider
            let optionsHtml = '';
            const defaultProvider = providersInfo.default_provider;
            let defaultModel = null;

            // Sort providers by type (commercial first, then local)
            const sortedProviders = providersInfo.providers.sort((a, b) => {
                if (a.type === 'commercial' && b.type === 'local') return -1;
                if (a.type === 'local' && b.type === 'commercial') return 1;
                return a.display_name.localeCompare(b.display_name);
            });

            // Group models by provider
            sortedProviders.forEach(provider => {
                if (provider.models && provider.models.length > 0) {
                    // Add indicator if provider is not configured
                    const configStatus = provider.is_configured === false ? ' (Not Configured)' : '';
                    const labelStyle = provider.is_configured === false ? ' style="color: #888;"' : '';

                    optionsHtml += `<optgroup label="${provider.display_name}${configStatus}"${labelStyle}>`;

                    provider.models.forEach(model => {
                        const value = `${provider.name}/${model}`;
                        const displayName = model;
                        const isDefault = provider.name === defaultProvider && provider.default_model === model;

                        if (isDefault) {
                            defaultModel = value;
                        }

                        // Disable option if provider is not configured
                        const disabled = provider.is_configured === false ? ' disabled' : '';
                        const disabledText = provider.is_configured === false ? ' (requires API key)' : '';

                        optionsHtml += `<option value="${value}"${isDefault ? ' data-default="true"' : ''}${disabled}>${displayName}${isDefault ? ' (default)' : ''}${disabledText}</option>`;
                    });

                    optionsHtml += '</optgroup>';
                }
            });

            // Update all model select dropdowns
            document.querySelectorAll('.llm-model-select').forEach(select => {
                const currentValue = select.value;
                const hasUseDefault = select.querySelector('option[value=""]');

                // Build the complete HTML
                let html = '';
                if (hasUseDefault && hasUseDefault.textContent.includes('Use default')) {
                    html = '<option value="">Use default</option>';
                }
                html += optionsHtml;

                select.innerHTML = html;

                // Restore previous selection or set default
                if (currentValue) {
                    select.value = currentValue;
                } else if (defaultModel && !hasUseDefault) {
                    select.value = defaultModel;
                }
            });

            console.log(`Populated model dropdowns with ${providersInfo.total_configured || providersInfo.providers.length} providers`);

        } catch (error) {
            console.error('Failed to populate model dropdowns:', error);
            // Show error in dropdowns
            document.querySelectorAll('.llm-model-select').forEach(select => {
                select.innerHTML = '<option value="">Error loading models</option>';
            });
        }
    }

    // ============================================================
    // WebSocket Support
    // ============================================================

    /**
     * Create a WebSocket connection
     * @param {string} path - WebSocket endpoint path (e.g., '/api/v1/mcp/ws')
     * @param {Object} options - WebSocket options
     * @returns {WebSocketManager} WebSocket manager instance
     */
    createWebSocket(path, options = {}) {
        const {
            id = `ws_${Date.now()}`,
            protocols = [],
            reconnect = true,
            reconnectDelay = 1000,
            maxReconnectDelay = 30000,
            reconnectDecay = 1.5,
            maxReconnectAttempts = null,
            onOpen = null,
            onMessage = null,
            onError = null,
            onClose = null,
            onReconnecting = null,
            heartbeatInterval = 30000,
            heartbeatMessage = JSON.stringify({ type: 'ping' })
        } = options;

        // Convert HTTP URL to WebSocket URL
        const wsUrl = this.baseUrl.replace(/^http/, 'ws') + path;

        // Add token to URL if available
        const url = new URL(wsUrl);
        if (this.token) {
            url.searchParams.append('token', this.token);
        }

        // Create WebSocket manager
        const manager = new WebSocketManager({
            url: url.toString(),
            protocols,
            reconnect,
            reconnectDelay,
            maxReconnectDelay,
            reconnectDecay,
            maxReconnectAttempts,
            onOpen,
            onMessage,
            onError,
            onClose,
            onReconnecting,
            heartbeatInterval,
            heartbeatMessage
        });

        // Store the WebSocket manager
        this.websockets.set(id, manager);

        return manager;
    }

    /**
     * Get existing WebSocket connection
     * @param {string} id - WebSocket ID
     * @returns {WebSocketManager|null} WebSocket manager or null if not found
     */
    getWebSocket(id) {
        return this.websockets.get(id) || null;
    }

    /**
     * Close WebSocket connection
     * @param {string} id - WebSocket ID
     */
    closeWebSocket(id) {
        const manager = this.websockets.get(id);
        if (manager) {
            manager.close();
            this.websockets.delete(id);
        }
    }

    /**
     * Close all WebSocket connections
     */
    closeAllWebSockets() {
        this.websockets.forEach(manager => manager.close());
        this.websockets.clear();
    }

    /**
     * Get all active WebSocket connections
     * @returns {Array} Array of WebSocket IDs and their states
     */
    getActiveWebSockets() {
        const active = [];
        this.websockets.forEach((manager, id) => {
            active.push({
                id,
                url: manager.url,
                readyState: manager.readyState,
                readyStateText: manager.readyStateText,
                reconnectCount: manager.reconnectCount
            });
        });
        return active;
    }
}

/**
 * WebSocket Manager class with auto-reconnect and heartbeat support
 */
class WebSocketManager {
    constructor(options) {
        this.url = options.url;
        this.protocols = options.protocols;
        this.reconnect = options.reconnect;
        this.reconnectDelay = options.reconnectDelay;
        this.maxReconnectDelay = options.maxReconnectDelay;
        this.reconnectDecay = options.reconnectDecay;
        this.maxReconnectAttempts = options.maxReconnectAttempts;
        this.onOpen = options.onOpen;
        this.onMessage = options.onMessage;
        this.onError = options.onError;
        this.onClose = options.onClose;
        this.onReconnecting = options.onReconnecting;
        this.heartbeatInterval = options.heartbeatInterval;
        this.heartbeatMessage = options.heartbeatMessage;

        this.ws = null;
        this.reconnectCount = 0;
        this.reconnectTimeout = null;
        this.heartbeatTimeout = null;
        this.messageQueue = [];
        this.isIntentionallyClosed = false;

        this.connect();
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url, this.protocols);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            if (this.onError) this.onError(error);
            this.handleReconnect();
        }
    }

    setupEventHandlers() {
        this.ws.onopen = (event) => {
            console.log('WebSocket connected:', this.url);
            this.reconnectCount = 0;
            this.reconnectDelay = this.constructor.reconnectDelay;

            // Process queued messages
            while (this.messageQueue.length > 0) {
                const message = this.messageQueue.shift();
                this.send(message);
            }

            // Start heartbeat
            this.startHeartbeat();

            if (this.onOpen) this.onOpen(event);
        };

        this.ws.onmessage = (event) => {
            // Reset heartbeat on any message
            this.startHeartbeat();

            // Try to parse JSON messages
            let data = event.data;
            try {
                data = JSON.parse(event.data);
            } catch (e) {
                // Not JSON, use as-is
            }

            if (this.onMessage) this.onMessage(data, event);
        };

        this.ws.onerror = (event) => {
            console.error('WebSocket error:', event);
            if (this.onError) this.onError(event);
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
            this.stopHeartbeat();

            if (this.onClose) this.onClose(event);

            if (!this.isIntentionallyClosed && this.reconnect) {
                this.handleReconnect();
            }
        };
    }

    handleReconnect() {
        if (this.maxReconnectAttempts && this.reconnectCount >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        this.reconnectCount++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(this.reconnectDecay, this.reconnectCount - 1),
            this.maxReconnectDelay
        );

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectCount})`);

        if (this.onReconnecting) {
            this.onReconnecting(this.reconnectCount, delay);
        }

        this.reconnectTimeout = setTimeout(() => {
            this.connect();
        }, delay);
    }

    startHeartbeat() {
        this.stopHeartbeat();

        if (this.heartbeatInterval && this.heartbeatMessage) {
            this.heartbeatTimeout = setTimeout(() => {
                if (this.isConnected()) {
                    this.send(this.heartbeatMessage);
                    this.startHeartbeat();
                }
            }, this.heartbeatInterval);
        }
    }

    stopHeartbeat() {
        if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
        }
    }

    /**
     * Send a message through WebSocket
     * @param {string|Object} message - Message to send (will be JSON stringified if object)
     */
    send(message) {
        if (typeof message === 'object') {
            message = JSON.stringify(message);
        }

        if (this.isConnected()) {
            try {
                this.ws.send(message);
                return true;
            } catch (error) {
                console.error('Failed to send message:', error);
                this.messageQueue.push(message);
                return false;
            }
        } else {
            // Queue message for sending when connected
            this.messageQueue.push(message);
            return false;
        }
    }

    /**
     * Close the WebSocket connection
     * @param {number} code - Close code
     * @param {string} reason - Close reason
     */
    close(code = 1000, reason = 'Normal closure') {
        this.isIntentionallyClosed = true;

        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }

        this.stopHeartbeat();

        if (this.ws) {
            this.ws.close(code, reason);
            this.ws = null;
        }
    }

    /**
     * Check if WebSocket is connected
     * @returns {boolean} Connection status
     */
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    /**
     * Get WebSocket ready state
     * @returns {number} Ready state
     */
    get readyState() {
        return this.ws ? this.ws.readyState : WebSocket.CLOSED;
    }

    /**
     * Get human-readable ready state
     * @returns {string} Ready state text
     */
    get readyStateText() {
        if (!this.ws) return 'CLOSED';
        switch (this.ws.readyState) {
            case WebSocket.CONNECTING: return 'CONNECTING';
            case WebSocket.OPEN: return 'OPEN';
            case WebSocket.CLOSING: return 'CLOSING';
            case WebSocket.CLOSED: return 'CLOSED';
            default: return 'UNKNOWN';
        }
    }

    /**
     * Add event listener
     * @param {string} event - Event name (open, message, error, close)
     * @param {Function} handler - Event handler
     */
    on(event, handler) {
        switch (event) {
            case 'open': this.onOpen = handler; break;
            case 'message': this.onMessage = handler; break;
            case 'error': this.onError = handler; break;
            case 'close': this.onClose = handler; break;
            case 'reconnecting': this.onReconnecting = handler; break;
        }
    }

    /**
     * Remove event listener
     * @param {string} event - Event name
     */
    off(event) {
        switch (event) {
            case 'open': this.onOpen = null; break;
            case 'message': this.onMessage = null; break;
            case 'error': this.onError = null; break;
            case 'close': this.onClose = null; break;
            case 'reconnecting': this.onReconnecting = null; break;
        }
    }
}

// Create global instance
const apiClient = new APIClient();

// Make apiClient globally accessible
window.apiClient = apiClient;

// Global function for populating model dropdowns
window.populateModelDropdowns = async function() {
    return apiClient.populateModelDropdowns();
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { APIClient, apiClient, WebSocketManager };
}
