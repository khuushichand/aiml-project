// Lightweight renderer for Agentic Explain Panel (plan + spans + highlights)
// Consumes the metadata shape described by schemas/agentic_explain.schema.json

(function () {
  function $(html) {
    const t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }

  function renderMetrics(metrics) {
    const termCov = typeof metrics.term_coverage === 'number' ? Math.round(metrics.term_coverage * 100) + '%' : '-';
    const uniqDocs = metrics.unique_docs ?? '-';
    const redundancy = (typeof metrics.redundancy === 'number') ? Math.round(metrics.redundancy * 100) + '%' : '-';
    const el = $(
      `<div class="explain-metrics">
        <div class="metric-item"><strong>Coverage</strong><div>${termCov}</div></div>
        <div class="metric-item"><strong>Corroboration</strong><div>${uniqDocs} docs</div></div>
        <div class="metric-item"><strong>Redundancy</strong><div>${redundancy}</div></div>
      </div>`
    );
    el.style.display = 'flex';
    el.style.gap = '16px';
    return el;
  }

  function renderProvenanceList(prov) {
    const container = $(`<div class="explain-provenance"></div>`);
    container.style.marginTop = '8px';
    const list = document.createElement('ul');
    list.style.paddingLeft = '16px';
    (prov || []).slice(0, 50).forEach((p) => {
      const li = document.createElement('li');
      const title = (p.title || p.document_id || 'doc');
      const sec = p.section_title ? ` - ${p.section_title}` : '';
      li.textContent = `${title}${sec} [${p.start}-${p.end}]`;
      list.appendChild(li);
    });
    container.appendChild(list);
    return container;
  }

  function renderExplainPanel(metadata, mountEl) {
    try {
      if (!metadata || (metadata.strategy !== 'agentic' && metadata.provenance == null)) {
        mountEl.textContent = 'Explain data unavailable for this result.';
        return;
      }
      const root = document.createElement('div');
      root.className = 'agentic-explain-panel';
      root.style.border = '1px solid var(--color-border)';
      root.style.borderRadius = '8px';
      root.style.padding = '12px';
      root.style.background = 'var(--color-surface-alt)';

      // Header
      const hdr = document.createElement('div');
      hdr.innerHTML = '<strong>Explain</strong> - Agentic Plan & Spans';
      hdr.style.marginBottom = '8px';
      root.appendChild(hdr);

      if (metadata.agentic_metrics) {
        root.appendChild(renderMetrics(metadata.agentic_metrics));
      }
      if (Array.isArray(metadata.provenance)) {
        root.appendChild(renderProvenanceList(metadata.provenance));
      }

      // Emit highlight event for viewer integration
      try {
        const highlights = metadata.highlights || { enable: true, section_anchors: true, color: '#ffdd88' };
        if (highlights && highlights.enable) {
          window.dispatchEvent(new CustomEvent('agentic:highlight-spans', {
            detail: {
              provenance: metadata.provenance || [],
              color: highlights.color || '#ffdd88',
              sectionAnchors: !!highlights.section_anchors,
            }
          }));
        }
      } catch (e) { /* no-op */ }

      // Mount
      mountEl.innerHTML = '';
      mountEl.appendChild(root);
    } catch (e) {
      console.error('Failed to render agentic explain panel', e);
      mountEl.textContent = 'Failed to render agentic explain panel.';
    }
  }

  // Expose to global
  window.renderAgenticExplainPanel = renderExplainPanel;
})();
