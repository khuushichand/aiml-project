# WebUI Schemas

This folder contains JSON Schemas used by the Web UI to describe structured payloads returned by the API.

## Agentic Explain Panel

- Schema: `agentic_explain.schema.json`
- Purpose: render the “Explain” panel for agentic RAG, combining:
  - Mini “plan” metrics (coverage, corroboration, redundancy)
  - Provenance spans (doc_id, offsets, section title)
  - UI hints for span highlighting and section anchors

### Example (matches `quick_start.agentic_explain` flow)

```
{
  "strategy": "agentic",
  "agentic_metrics": {
    "term_coverage": 0.82,
    "unique_docs": 3,
    "redundancy": 0.12
  },
  "provenance": [
    {
      "document_id": "m1",
      "title": "ResNet",
      "start": 120,
      "end": 350,
      "section_title": "Results",
      "snippet_preview": "Residual connections help gradient flow..."
    }
  ],
  "highlights": {
    "enable": true,
    "section_anchors": true,
    "color": "#ffdd88"
  }
}
```

### Rendering Hook

- A lightweight renderer is provided at `js/components_explain.js` exposing a global function:

```
window.renderAgenticExplainPanel(metadata, mountEl)
```

- It appends a small panel with plan metrics and a list of spans, and dispatches a browser event for downstream viewers:

```
window.addEventListener('agentic:highlight-spans', (e) => {
  const { provenance, color, sectionAnchors } = (e.detail || {});
  // Integrate with your viewer: highlight ranges and scroll to anchors
});
```

To integrate, call the renderer when an agentic response arrives (e.g., in the RAG tab after a search), passing `result.metadata` and a DOM element container.
