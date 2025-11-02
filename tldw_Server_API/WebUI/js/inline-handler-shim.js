// Inline Handler Shim
// Replaces inline event handler attributes (onclick=, onchange=, etc.) with
// addEventListener-based handlers so CSP can disallow script-src-attr.
//
// Security note: This translates attribute code strings into Functions, which
// requires 'unsafe-eval' in CSP. We already allow 'unsafe-eval' for legacy UI.
// This is a transitional measure to reduce reliance on inline attributes.

(function () {
  'use strict';

  const ATTR_PREFIX = 'on';
  const HANDLER_ATTRS = new Set([
    'onclick', 'onchange', 'onsubmit', 'oninput', 'onkeydown', 'onkeyup',
    'onkeypress', 'onload', 'onerror', 'onmouseover', 'onmouseout', 'onfocus',
    'onblur', 'onmouseenter', 'onmouseleave', 'onmousedown', 'onmouseup',
    'onwheel', 'oncontextmenu', 'ondblclick', 'onpaste', 'oncopy', 'oncut',
    'ondrag', 'ondragstart', 'ondragend', 'ondragenter', 'ondragleave',
    'ondragover', 'ondrop', 'onpointerdown', 'onpointerup', 'onpointermove'
  ]);

  function rewireElement(el) {
    if (!(el && el.getAttribute)) return;
    // Iterate attributes snapshot because we may remove during iteration
    const attrs = el.attributes ? Array.from(el.attributes) : [];
    for (const attr of attrs) {
      const name = attr.name.toLowerCase();
      if (!name.startsWith(ATTR_PREFIX)) continue;
      // Limit to known handlers to avoid grabbing unrelated attributes
      if (!HANDLER_ATTRS.has(name)) continue;
      const code = attr.value || '';
      const evt = name.slice(2); // strip 'on'
      try {
        // Wrap attribute code into a function taking 'event'
        // Use Function constructor to preserve global references (window).
        const fn = new Function('event', code);
        el.addEventListener(evt, function (event) {
          try {
            return fn.call(el, event);
          } catch (e) {
            // eslint-disable-next-line no-console
            console.error('Inline handler shim error for', name, 'on', el, e);
          }
        }, false);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('Failed to convert inline handler', name, 'on', el, e);
      } finally {
        // Remove attribute to prevent blocked inline execution and duplicate firing
        try { el.removeAttribute(name); } catch (_e) {}
      }
    }
  }

  function rewireTree(root) {
    if (!root) return;
    if (root.nodeType === 1) { // Element
      rewireElement(root);
      const children = root.querySelectorAll('[onload], [onerror], [onclick], [onchange], [onsubmit], [oninput], [onkeydown], [onkeyup], [onkeypress], [onmouseover], [onmouseout], [onfocus], [onblur], [onmouseenter], [onmouseleave], [onmousedown], [onmouseup], [onwheel], [oncontextmenu], [ondblclick], [onpaste], [oncopy], [oncut], [ondrag], [ondragstart], [ondragend], [ondragenter], [ondragleave], [ondragover], [ondrop], [onpointerdown], [onpointerup], [onpointermove]');
      for (const el of children) rewireElement(el);
    }
  }

  function installObserver() {
    try {
      const mo = new MutationObserver((mutations) => {
        for (const m of mutations) {
          if (m.type === 'childList') {
            for (const node of m.addedNodes) {
              rewireTree(node);
            }
          } else if (m.type === 'attributes' && typeof m.target?.getAttribute === 'function') {
            const name = m.attributeName?.toLowerCase?.() || '';
            if (name && name.startsWith(ATTR_PREFIX)) rewireElement(m.target);
          }
        }
      });
      mo.observe(document.documentElement || document.body, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: Array.from(HANDLER_ATTRS),
      });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('Inline handler shim observer failed:', e);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      rewireTree(document);
      installObserver();
    });
  } else {
    rewireTree(document);
    installObserver();
  }
})();
