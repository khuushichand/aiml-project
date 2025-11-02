/**
 * Reusable UI Components for the API WebUI
 */

class ToastManager {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        if (!document.getElementById('toast-container')) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('toast-container');
        }
    }

    show(message, type = 'info', duration = 5000, title = null) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        // Create toast elements safely
        const iconSpan = document.createElement('span');
        iconSpan.className = 'toast-icon';
        iconSpan.textContent = icons[type] || icons.info;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'toast-content';

        if (title) {
            const titleDiv = document.createElement('div');
            titleDiv.className = 'toast-title';
            titleDiv.textContent = title;
            contentDiv.appendChild(titleDiv);
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = 'toast-message';
        messageDiv.textContent = message;  // Safe text content
        contentDiv.appendChild(messageDiv);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.setAttribute('aria-label', 'Close');
        closeBtn.textContent = '×';
        closeBtn.onclick = () => this.remove(toast);

        toast.appendChild(iconSpan);
        toast.appendChild(contentDiv);
        toast.appendChild(closeBtn);

        this.container.appendChild(toast);

        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => this.remove(toast), duration);
        }

        return toast;
    }

    remove(toast) {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    success(message, duration = 5000) {
        return this.show(message, 'success', duration, 'Success');
    }

    error(message, duration = 5000) {
        return this.show(message, 'error', duration, 'Error');
    }

    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration, 'Warning');
    }

    info(message, duration = 5000) {
        return this.show(message, 'info', duration, 'Info');
    }
}

class LoadingIndicator {
    constructor() {
        this.activeLoaders = new Map();
    }

    show(element, message = 'Loading...') {
        if (!element) return;

        const loaderId = Utils.generateId('loader');
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.id = loaderId;
        // Create loading elements safely
        const contentDiv = document.createElement('div');
        contentDiv.className = 'loading-content';

        const spinnerDiv = document.createElement('div');
        spinnerDiv.className = 'loading-spinner';

        const messageDiv = document.createElement('div');
        messageDiv.className = 'loading-message';
        messageDiv.textContent = message;  // Safe text content

        contentDiv.appendChild(spinnerDiv);
        contentDiv.appendChild(messageDiv);
        overlay.appendChild(contentDiv);

        element.style.position = 'relative';
        element.appendChild(overlay);
        this.activeLoaders.set(element, loaderId);

        return loaderId;
    }

    hide(element) {
        if (!element || !this.activeLoaders.has(element)) return;

        const loaderId = this.activeLoaders.get(element);
        const overlay = document.getElementById(loaderId);
        if (overlay) {
            overlay.remove();
        }
        this.activeLoaders.delete(element);
    }

    hideAll() {
        this.activeLoaders.forEach((loaderId, element) => {
            const overlay = document.getElementById(loaderId);
            if (overlay) {
                overlay.remove();
            }
        });
        this.activeLoaders.clear();
    }
}

class Modal {
    constructor(options = {}) {
        this.options = {
            title: 'Modal',
            content: '',
            size: 'medium', // small, medium, large, full
            closeButton: true,
            backdrop: true,
            keyboard: true,
            ...options
        };
        this.modal = null;
        this.backdrop = null;
        this.create();
    }

    create() {
        // Create backdrop
        if (this.options.backdrop) {
            this.backdrop = document.createElement('div');
            this.backdrop.className = 'modal-backdrop';
            this.backdrop.setAttribute('aria-hidden', 'true');
            this.backdrop.onclick = () => {
                if (this.options.backdrop === 'static') return;
                this.close();
            };
        }

        // Create modal
        this.modal = document.createElement('div');
        this.modal.className = `modal modal-${this.options.size}`;
        this.modal.innerHTML = `
            <div class="modal-header">
                <h2 class="modal-title">${this.options.title}</h2>
                ${this.options.closeButton ? '<button class="modal-close" aria-label="Close">×</button>' : ''}
            </div>
            <div class="modal-body">
                ${this.options.content}
            </div>
            ${this.options.footer ? `<div class="modal-footer">${this.options.footer}</div>` : ''}
        `;

        // ARIA roles and labelling
        try {
            this.modal.setAttribute('role', 'dialog');
            this.modal.setAttribute('aria-modal', 'true');
            const titleEl = this.modal.querySelector('.modal-title');
            if (titleEl) {
                const titleId = `modal-title-${Math.random().toString(36).slice(2)}`;
                titleEl.id = titleId;
                this.modal.setAttribute('aria-labelledby', titleId);
            }
        } catch (e) { /* ignore */ }

        if (this.options.closeButton) {
            const closeBtn = this.modal.querySelector('.modal-close');
            closeBtn.onclick = () => this.close();
        }

        // Keyboard events
        if (this.options.keyboard) {
            document.addEventListener('keydown', this.handleKeydown.bind(this));
        }
    }

    handleKeydown(e) {
        if (e.key === 'Escape') {
            this.close();
        }
        if (e.key === 'Tab') {
            // trap focus inside the modal
            const focusable = this.modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        }
    }

    show() {
        if (this.backdrop) {
            document.body.appendChild(this.backdrop);
        }
        document.body.appendChild(this.modal);
        document.body.style.overflow = 'hidden';

        // Focus management
        const focusable = this.modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (focusable.length) {
            focusable[0].focus();
        }
    }

    close() {
        if (this.backdrop && this.backdrop.parentNode) {
            this.backdrop.parentNode.removeChild(this.backdrop);
        }
        if (this.modal && this.modal.parentNode) {
            this.modal.parentNode.removeChild(this.modal);
        }
        document.body.style.overflow = '';

        if (this.options.keyboard) {
            document.removeEventListener('keydown', this.handleKeydown.bind(this));
        }

        if (this.options.onClose) {
            this.options.onClose();
        }
    }

    setContent(content) {
        const body = this.modal.querySelector('.modal-body');
        if (body) {
            body.innerHTML = content;
        }
    }
}

class JSONViewer {
    constructor(container, json, options = {}) {
        this.container = container;
        this.json = json;
        this.options = {
            expanded: 1, // Levels to expand by default
            theme: 'light',
            enableCopy: true,
            enableCollapse: true,
            ...options
        };
        this.render();
    }

    render() {
        this.container.innerHTML = '';
        const wrapper = document.createElement('div');
        wrapper.className = `json-viewer json-viewer-${this.options.theme}`;

        if (this.options.enableCopy) {
            const toolbar = document.createElement('div');
            toolbar.className = 'json-viewer-toolbar';
            toolbar.innerHTML = `
                <button class="btn btn-sm" onclick="Utils.copyToClipboard('${Utils.escapeHtml(JSON.stringify(this.json, null, 2))}')">
                    Copy JSON
                </button>
                <button class="btn btn-sm" onclick="Utils.downloadData(${Utils.escapeHtml(JSON.stringify(this.json))}, 'data.json')">
                    Download
                </button>
            `;
            wrapper.appendChild(toolbar);
        }

        const content = document.createElement('div');
        content.className = 'json-viewer-content';
        content.innerHTML = this.renderValue(this.json, 0);
        wrapper.appendChild(content);

        this.container.appendChild(wrapper);

        // Add collapse/expand functionality
        if (this.options.enableCollapse) {
            this.attachCollapseHandlers();
        }
    }

    renderValue(value, depth) {
        if (value === null) {
            return '<span class="json-null">null</span>';
        }
        if (typeof value === 'boolean') {
            return `<span class="json-boolean">${value}</span>`;
        }
        if (typeof value === 'number') {
            return `<span class="json-number">${value}</span>`;
        }
        if (typeof value === 'string') {
            return `<span class="json-string">"${Utils.escapeHtml(value)}"</span>`;
        }
        if (Array.isArray(value)) {
            return this.renderArray(value, depth);
        }
        if (typeof value === 'object') {
            return this.renderObject(value, depth);
        }
        return Utils.escapeHtml(String(value));
    }

    renderArray(arr, depth) {
        if (arr.length === 0) {
            return '<span class="json-bracket">[]</span>';
        }

        const expanded = depth < this.options.expanded;
        let html = `<span class="json-toggle ${expanded ? 'expanded' : 'collapsed'}" data-type="array">▼</span>`;
        html += '<span class="json-bracket">[</span>';
        html += `<div class="json-content" ${expanded ? '' : 'style="display:none"'}>`;

        arr.forEach((item, index) => {
            html += '<div class="json-item">';
            html += this.renderValue(item, depth + 1);
            if (index < arr.length - 1) {
                html += '<span class="json-comma">,</span>';
            }
            html += '</div>';
        });

        html += '</div>';
        html += '<span class="json-bracket">]</span>';
        return html;
    }

    renderObject(obj, depth) {
        const keys = Object.keys(obj);
        if (keys.length === 0) {
            return '<span class="json-bracket">{}</span>';
        }

        const expanded = depth < this.options.expanded;
        let html = `<span class="json-toggle ${expanded ? 'expanded' : 'collapsed'}" data-type="object">▼</span>`;
        html += '<span class="json-bracket">{</span>';
        html += `<div class="json-content" ${expanded ? '' : 'style="display:none"'}>`;

        keys.forEach((key, index) => {
            html += '<div class="json-item">';
            html += `<span class="json-key">"${Utils.escapeHtml(key)}"</span>`;
            html += '<span class="json-colon">:</span> ';
            html += this.renderValue(obj[key], depth + 1);
            if (index < keys.length - 1) {
                html += '<span class="json-comma">,</span>';
            }
            html += '</div>';
        });

        // Inject quick action: Add to Batch, when object looks like a paper item
        try {
            const batchItem = this.detectBatchItem(obj);
            const pmcItem = this.detectPmcBatchItem(obj);
            const zenodoItem = this.detectZenodoIngestItem(obj);
            const vixraItem = this.detectVixraIngestItem(obj);
            const figshareItem = this.detectFigshareIngestItem(obj);
            const halItem = this.detectHalIngestItem(obj);
            const osfItem = this.detectOsfIngestItem(obj);
            if (batchItem || pmcItem || zenodoItem || vixraItem || figshareItem || halItem || osfItem) {
                html += `<div class="json-item">`;
                if (batchItem) {
                    const payload = encodeURIComponent(JSON.stringify(batchItem));
                    html += `<button class="btn btn-sm" onclick="addSearchItemToBatchFromPayload(this)" data-payload="${payload}">➕ Add to Batch</button>`;
                }
                if (pmcItem) {
                    const payloadPmc = encodeURIComponent(JSON.stringify(pmcItem));
                    html += ` <button class="btn btn-sm" onclick="addPmcItemToBatchFromPayload(this)" data-payload="${payloadPmc}">➕ Add to PMC Batch</button>`;
                }
                if (zenodoItem) {
                    const payloadZen = encodeURIComponent(JSON.stringify(zenodoItem));
                    html += ` <button class="btn btn-sm" onclick="ingestZenodoFromPayload(this)" data-payload="${payloadZen}">🚀 Ingest (Zenodo)</button>`;
                }
                if (vixraItem) {
                    const payloadVix = encodeURIComponent(JSON.stringify(vixraItem));
                    html += ` <button class="btn btn-sm" onclick="ingestVixraFromPayload(this)" data-payload="${payloadVix}">🚀 Ingest (viXra)</button>`;
                }
                if (figshareItem) {
                    const payloadFig = encodeURIComponent(JSON.stringify(figshareItem));
                    html += ` <button class="btn btn-sm" onclick="ingestFigshareFromPayload(this)" data-payload="${payloadFig}">🚀 Ingest (Figshare)</button>`;
                }
                if (halItem) {
                    const payloadHal = encodeURIComponent(JSON.stringify(halItem));
                    html += ` <button class="btn btn-sm" onclick="ingestHalFromPayload(this)" data-payload="${payloadHal}">🚀 Ingest (HAL)</button>`;
                }
                if (osfItem) {
                    const payloadOsf = encodeURIComponent(JSON.stringify(osfItem));
                    html += ` <button class="btn btn-sm" onclick="ingestOsfFromPayload(this)" data-payload="${payloadOsf}">🚀 Ingest (OSF)</button>`;
                }
                html += `</div>`;
            }
        } catch (e) { /* noop */ }

        html += '</div>';
        html += '<span class="json-bracket">}</span>';
        return html;
    }

    attachCollapseHandlers() {
        const toggles = this.container.querySelectorAll('.json-toggle');
        toggles.forEach(toggle => {
            toggle.onclick = (e) => {
                e.stopPropagation();
                const content = toggle.nextElementSibling.nextElementSibling;
                if (toggle.classList.contains('expanded')) {
                    toggle.classList.remove('expanded');
                    toggle.classList.add('collapsed');
                    toggle.textContent = '▶';
                    content.style.display = 'none';
                } else {
                    toggle.classList.remove('collapsed');
                    toggle.classList.add('expanded');
                    toggle.textContent = '▼';
                    content.style.display = 'block';
                }
            };
        });
    }

    detectBatchItem(obj) {
        if (!obj || typeof obj !== 'object') return null;
        // Known fields
        let doi = obj.doi || (obj.externalIds && obj.externalIds.DOI) || null;
        let pdf_url = obj.pdf_url || null;
        // Semantic Scholar shape
        if (!pdf_url && obj.openAccessPdf && obj.openAccessPdf.url) {
            pdf_url = obj.openAccessPdf.url;
        }
        // PubMed/PMC shapes: infer PDF from PMCID or links if present
        let pmcid = obj.pmcid || obj.PMCID || obj.pmcId || (obj.pmc_url && String(obj.pmc_url).match(/PMC\d+/)?.[0]) || null;
        if (!pdf_url && pmcid) {
            const id = String(pmcid).toUpperCase().startsWith('PMC') ? String(pmcid).toUpperCase() : `PMC${pmcid}`;
            pdf_url = `https://www.ncbi.nlm.nih.gov/pmc/articles/${id}/pdf`;
        }
        if (!pdf_url && Array.isArray(obj.links)) {
            const link = obj.links.find(lk => (lk?.format||'').toLowerCase()==='pdf' || (lk?.href||'').toLowerCase().endsWith('.pdf'));
            if (link && link.href) pdf_url = link.href;
        }
        // arXiv shapes: arxiv_id or DOI 10.48550/arXiv.X
        const arxivIdFromObj = obj.arxiv_id || obj.arXiv || obj.ArXiv || (typeof obj.id === 'string' && /arxiv[:\s]?/i.test(obj.id) ? obj.id.replace(/.*arxiv[:\s]?/i, '') : null);
        const arxivIdFromDoi = (typeof doi === 'string' && /10\.48550\/arXiv\./i.test(doi)) ? doi.split('arXiv.')[1] : null;
        const arxIdRaw = (arxivIdFromObj || arxivIdFromDoi || '').trim();
        const arxMatch = arxIdRaw && arxIdRaw.match(/^(\d{4}\.\d{4,5}|[a-z\-]+\/\d{7})(v\d+)?$/i);
        if (!pdf_url && arxMatch) {
            const coreId = arxMatch[1];
            pdf_url = `https://arxiv.org/pdf/${coreId}.pdf`;
            // If DOI missing but we can synthesize from arXiv pattern, keep doi null; ingest_batch handles pdf_url-only
        }
        // Title / authors
        let title = obj.title || null;
        let author = null;
        if (typeof obj.authors === 'string') author = obj.authors;
        else if (Array.isArray(obj.authors)) author = obj.authors.map(a => a.name || a).filter(Boolean).join(', ');

        if (!doi && !pdf_url) return null;
        return { doi, pdf_url, title, author };
    }

    // Detect PMC batch-able item (prefer PMCID to go through PMC-optimized ingest)
    detectPmcBatchItem(obj) {
        if (!obj || typeof obj !== 'object') return null;
        let pmcid = obj.pmcid || obj.PMCID || obj.pmcId || (obj.pmc_url && String(obj.pmc_url).match(/PMC\d+/)?.[0]) || null;
        // Also handle PMC OA record shape where id is PMCxxxxx
        if (!pmcid && typeof obj.id === 'string' && /^PMC\d+$/i.test(obj.id)) {
            pmcid = obj.id;
        }
        if (!pmcid) return null;
        const id = String(pmcid).toUpperCase().startsWith('PMC') ? String(pmcid).toUpperCase() : `PMC${pmcid}`;
        let title = obj.title || null;
        let author = null;
        if (typeof obj.authors === 'string') author = obj.authors;
        else if (Array.isArray(obj.authors)) author = obj.authors.map(a => a.name || a).filter(Boolean).join(', ');
        return { pmcid: id, title, author };
    }

    // Detect Zenodo record for quick ingest
    detectZenodoIngestItem(obj) {
        try {
            if (!obj || typeof obj !== 'object') return null;
            const provider = (obj.provider || '').toLowerCase();
            const url = obj.url || '';
            const id = obj.id || obj.record_id || null;
            if ((!provider && !url) || !id) return null;
            const looksZenodo = provider === 'zenodo' || /zenodo\.org/i.test(String(url));
            if (!looksZenodo) return null;
            return { record_id: String(id), title: obj.title || undefined };
        } catch {
            return null;
        }
    }

    // Detect viXra record for quick ingest
    detectVixraIngestItem(obj) {
        try {
            if (!obj || typeof obj !== 'object') return null;
            const provider = (obj.provider || '').toLowerCase();
            const url = obj.url || '';
            const id = obj.id || null; // viXra ID
            if ((!provider && !url) || !id) return null;
            const looksVixra = provider === 'vixra' || /vixra\.org/i.test(String(url));
            if (!looksVixra) return null;
            return { vid: String(id), title: obj.title || undefined };
        } catch {
            return null;
        }
    }

    // Detect Figshare record for quick ingest
    detectFigshareIngestItem(obj) {
        try {
            if (!obj || typeof obj !== 'object') return null;
            const provider = (obj.provider || '').toLowerCase();
            const url = obj.url || '';
            const id = obj.id || null; // Figshare article ID
            if ((!provider && !url) || !id) return null;
            const looksFig = provider === 'figshare' || /figshare\.com/i.test(String(url));
            if (!looksFig) return null;
            return { article_id: String(id), title: obj.title || undefined };
        } catch {
            return null;
        }
    }

    // Detect HAL record for quick ingest
    detectHalIngestItem(obj) {
        try {
            if (!obj || typeof obj !== 'object') return null;
            const provider = (obj.provider || '').toLowerCase();
            const id = obj.id || null; // HAL docid
            const url = obj.url || '';
            if ((!provider && !url) || !id) return null;
            const looksHal = provider === 'hal' || /archives-ouvertes\.fr|hal\./i.test(String(url));
            if (!looksHal) return null;
            return { docid: String(id), title: obj.title || undefined };
        } catch {
            return null;
        }
    }

    // Detect OSF preprint for quick ingest
    detectOsfIngestItem(obj) {
        try {
            if (!obj || typeof obj !== 'object') return null;
            const provider = (obj.provider || '').toLowerCase();
            const url = obj.url || '';
            const id = obj.id || obj.osf_id || null; // OSF preprint id
            if ((!provider && !url) || !id) return null;
            const looksOsf = provider === 'osf' || /osf\.io\//i.test(String(url));
            if (!looksOsf) return null;
            return { osf_id: String(id), title: obj.title || undefined };
        } catch {
            return null;
        }
    }
}

// Initialize global instances
const Toast = new ToastManager();
const Loading = new LoadingIndicator();

// Batch helpers for search results
function addSearchItemToBatch(item) {
    try {
        const ta = document.getElementById('oaIngestBatch_payload');
        if (!ta) { Toast.warning('Open OA Ingest Batch panel to collect selections.'); return; }
        let arr = [];
        const current = (ta.value || '').trim();
        if (current.startsWith('[')) {
            try { arr = JSON.parse(current); if (!Array.isArray(arr)) arr = []; } catch { arr = []; }
        }
        if (!current) arr = [];
        if (!Array.isArray(arr)) arr = [];
        arr.push(item);
        ta.value = JSON.stringify(arr, null, 2);
        Toast.success('Added to batch');
    } catch (e) {
        console.error('addSearchItemToBatch failed', e);
        alert('Failed to add to batch: ' + (e?.message || e));
    }
}

function addSearchItemToBatchFromPayload(el) {
    try {
        const payloadStr = el?.dataset?.payload || '';
        if (!payloadStr) return;
        const item = JSON.parse(decodeURIComponent(payloadStr));
        addSearchItemToBatch(item);
    } catch (e) {
        console.error('addSearchItemToBatchFromPayload failed', e);
        alert('Failed to add to batch');
    }
}

// PMC batch helpers
function addPmcItemToBatch(item) {
    try {
        const ta = document.getElementById('pmcBatchIngest_payload');
        if (!ta) { Toast.warning('Open PMC Batch Ingest panel to collect selections.'); return; }
        let arr = [];
        const current = (ta.value || '').trim();
        if (current.startsWith('[')) {
            try { arr = JSON.parse(current); if (!Array.isArray(arr)) arr = []; } catch { arr = []; }
        }
        if (!current) arr = [];
        if (!Array.isArray(arr)) arr = [];
        // Normalize to minimal { pmcid, title?, author? }
        const pmcid = String(item.pmcid || item.PMCID || '').trim();
        if (!pmcid) { Toast.error('Invalid PMCID payload'); return; }
        arr.push({ pmcid, title: item.title || undefined, author: item.author || undefined, keywords: item.keywords || undefined });
        ta.value = JSON.stringify(arr, null, 2);
        Toast.success('Added to PMC batch');
    } catch (e) {
        console.error('addPmcItemToBatch failed', e);
        alert('Failed to add to PMC batch: ' + (e?.message || e));
    }
}

function addPmcItemToBatchFromPayload(el) {
    try {
        const payloadStr = el?.dataset?.payload || '';
        if (!payloadStr) return;
        const item = JSON.parse(decodeURIComponent(payloadStr));
        addPmcItemToBatch(item);
    } catch (e) {
        console.error('addPmcItemToBatchFromPayload failed', e);
        alert('Failed to add to PMC batch');
    }
}

// Quick ingest for Zenodo
async function ingestZenodoFromPayload(el) {
    try {
        const payloadStr = el?.dataset?.payload || '';
        if (!payloadStr) return;
        const item = JSON.parse(decodeURIComponent(payloadStr));
        const record_id = item.record_id;
        if (!record_id) { Toast.error('Missing Zenodo record_id'); return; }
        // Use defaults; advanced users can use the panel to customize
        const body = {
            perform_chunking: true,
            parser: 'pymupdf4llm',
            chunk_method: null,
            chunk_size: 500,
            chunk_overlap: 200,
            perform_analysis: true
        };
        const res = await apiClient.post('/api/v1/paper-search/zenodo/ingest', body, { query: { record_id } });
        Toast.success(`Zenodo ingested: media_id ${res?.media_id ?? ''}`);
    } catch (e) {
        console.error('ingestZenodoFromPayload failed', e);
        Toast.error('Zenodo ingest failed');
    }
}

// Quick ingest for viXra
async function ingestVixraFromPayload(el) {
    try {
        const payloadStr = el?.dataset?.payload || '';
        if (!payloadStr) return;
        const item = JSON.parse(decodeURIComponent(payloadStr));
        const vid = item.vid;
        if (!vid) { Toast.error('Missing viXra ID'); return; }
        const body = {
            perform_chunking: true,
            parser: 'pymupdf4llm',
            chunk_method: null,
            chunk_size: 500,
            chunk_overlap: 200,
            perform_analysis: true
        };
        const res = await apiClient.post('/api/v1/paper-search/vixra/ingest', body, { query: { vid } });
        Toast.success(`viXra ingested: media_id ${res?.media_id ?? ''}`);
    } catch (e) {
        console.error('ingestVixraFromPayload failed', e);
        Toast.error('viXra ingest failed');
    }
}

// Quick ingest for Figshare
async function ingestFigshareFromPayload(el) {
    try {
        const payloadStr = el?.dataset?.payload || '';
        if (!payloadStr) return;
        const item = JSON.parse(decodeURIComponent(payloadStr));
        const article_id = item.article_id;
        if (!article_id) { Toast.error('Missing Figshare article_id'); return; }
        const body = {
            perform_chunking: true,
            parser: 'pymupdf4llm',
            chunk_method: null,
            chunk_size: 500,
            chunk_overlap: 200,
            perform_analysis: true
        };
        const res = await apiClient.post('/api/v1/paper-search/figshare/ingest', body, { query: { article_id } });
        Toast.success(`Figshare ingested: media_id ${res?.media_id ?? ''}`);
    } catch (e) {
        console.error('ingestFigshareFromPayload failed', e);
        Toast.error('Figshare ingest failed');
    }
}

// Quick ingest for HAL
async function ingestHalFromPayload(el) {
    try {
        const payloadStr = el?.dataset?.payload || '';
        if (!payloadStr) return;
        const item = JSON.parse(decodeURIComponent(payloadStr));
        const docid = item.docid;
        if (!docid) { Toast.error('Missing HAL docid'); return; }
        const body = {
            perform_chunking: true,
            parser: 'pymupdf4llm',
            chunk_method: null,
            chunk_size: 500,
            chunk_overlap: 200,
            perform_analysis: true
        };
        const res = await apiClient.post('/api/v1/paper-search/hal/ingest', body, { query: { docid } });
        Toast.success(`HAL ingested: media_id ${res?.media_id ?? ''}`);
    } catch (e) {
        console.error('ingestHalFromPayload failed', e);
        Toast.error('HAL ingest failed');
    }
}

// Quick ingest for OSF
async function ingestOsfFromPayload(el) {
    try {
        const payloadStr = el?.dataset?.payload || '';
        if (!payloadStr) return;
        const item = JSON.parse(decodeURIComponent(payloadStr));
        const osf_id = item.osf_id;
        if (!osf_id) { Toast.error('Missing OSF ID'); return; }
        const body = {
            perform_chunking: true,
            parser: 'pymupdf4llm',
            chunk_method: null,
            chunk_size: 500,
            chunk_overlap: 200,
            perform_analysis: true
        };
        const res = await apiClient.post('/api/v1/paper-search/osf/ingest', body, { query: { osf_id } });
        Toast.success(`OSF ingested: media_id ${res?.media_id ?? ''}`);
    } catch (e) {
        console.error('ingestOsfFromPayload failed', e);
        Toast.error('OSF ingest failed');
    }
}

// expose globals
window.addSearchItemToBatch = addSearchItemToBatch;
window.addSearchItemToBatchFromPayload = addSearchItemToBatchFromPayload;
window.addPmcItemToBatch = addPmcItemToBatch;
window.addPmcItemToBatchFromPayload = addPmcItemToBatchFromPayload;
window.ingestZenodoFromPayload = ingestZenodoFromPayload;
window.ingestVixraFromPayload = ingestVixraFromPayload;
window.ingestFigshareFromPayload = ingestFigshareFromPayload;
window.ingestHalFromPayload = ingestHalFromPayload;
window.ingestOsfFromPayload = ingestOsfFromPayload;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ToastManager, LoadingIndicator, Modal, JSONViewer, Toast, Loading, addSearchItemToBatch, addSearchItemToBatchFromPayload, addPmcItemToBatch, addPmcItemToBatchFromPayload, ingestZenodoFromPayload, ingestVixraFromPayload, ingestFigshareFromPayload, ingestHalFromPayload, ingestOsfFromPayload };
}
