// Global HTML sanitizer + inline handler migrator for CSP-safe DOM updates
// - Rewrites inline event handler attributes (onclick, onsubmit, ...) to
//   data-on*-b64 attributes so the browser never parses script-src-attr
// - Converts preserved data-on*-b64 attributes into addEventListener bindings
//   without ever inserting inline handlers into the live DOM

(function () {
  function sanitize(html) {
    try {
      // Drop any <script>...</script> blocks
      let out = String(html).replace(/<script\b[\s\S]*?>[\s\S]*?<\/script>/gi, '');
      // Replace on*="..." with data-on*-b64="<base64(code)>"
      out = out.replace(/\s(on[\w-]+)\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))/gi,
        (m, attrName, _full, dquoted, squoted, unquoted) => {
          const raw = (dquoted !== undefined) ? dquoted : (squoted !== undefined) ? squoted : (unquoted || '');
          let b64 = '';
          try { b64 = btoa(raw); } catch (_) { b64 = ''; }
          return ` data-${attrName}-b64="${b64}"`;
        }
      );
      return out;
    } catch (_) {
      return String(html);
    }
  }

  function migrateInlineHandlers(root) {
    const scope = root || document;
    const attrs = [
      'onclick','onchange','oninput','onkeydown','onkeyup','onsubmit','ondblclick','onfocus','onblur',
      'onmouseenter','onmouseleave','onmouseover','onmouseout','onmouseup','onmousedown','oncontextmenu',
      'ondrag','ondragstart','ondragend','ondragover','ondrop','onload','onerror'
    ];
    const attrToEvent = (attr) => attr.slice(2);
    const splitArgs = (s) => {
      const out = []; let buf=''; let q=null; let depth=0;
      for (let i=0;i<s.length;i++){
        const ch = s[i];
        if (q) { if (ch===q && s[i-1]!== '\\') { q=null; buf+=ch; continue; } buf+=ch; continue; }
        if (ch==='"' || ch==="'") { q=ch; buf+=ch; continue; }
        if (ch==='{' || ch==='[') { depth++; buf+=ch; continue; }
        if (ch==='}' || ch===']') { depth--; buf+=ch; continue; }
        if (ch===',' && depth===0) { out.push(buf.trim()); buf=''; continue; }
        buf+=ch;
      }
      if (buf.trim()) out.push(buf.trim());
      return out;
    };
    const stripQuotes = (s) => {
      if (!s) return s;
      if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) return s.slice(1,-1);
      return s;
    };

    const devMarkers = false;

    const bindFromCode = (el, evt, code) => {
      let bound = false;
      const endsWithReturnFalse = /;\s*return\s+false\s*;?\s*$/s.test(code);
      const startsWithReturn = /^\s*return\b/s.test(code);
      const confirmMatch = code.match(/confirm\((['\"])(.*?)\1\)/s);
      const confirmMessage = confirmMatch ? confirmMatch[2] : null;
      const resolveArgs = (rawParts, event) => rawParts.map((p) => {
        const t = String(p).trim();
        if (!t) return t;
        if (t === 'event') return event;
        if (t === 'this') return el;
        if (t.startsWith('{') || t.startsWith('[')) { try { return JSON.parse(t); } catch (_) { return t; } }
        return stripQuotes(t);
      });

      const mr = code.match(/^\s*(?:if\s*\(.*?\)\s*)?(?:return\s*)?makeRequest\((.*)\)\s*;?\s*(?:return\s+false\s*;?)?\s*$/s);
      if (mr) {
        const argStr = mr[1] || '';
        const rawParts = splitArgs(argStr);
        const listener = (event) => {
          try {
            if (confirmMessage && !window.confirm(confirmMessage)) return;
            const args = resolveArgs(rawParts, event);
            const ret = (window.makeRequest && typeof window.makeRequest === 'function') ? window.makeRequest.apply(el, args) : undefined;
            if (endsWithReturnFalse || ret === false || startsWithReturn) {
              if (ret === false || endsWithReturnFalse) { try { event.preventDefault(); event.stopPropagation(); } catch (_) {} }
            }
          } catch (e) { console.error('makeRequest handler failed', e); }
        };
        el.addEventListener(evt, listener);
        if (devMarkers) { try { el.classList.add('migrated-inline'); el.dataset.migratedInline = '1'; } catch (_) {} }
        bound = true;
      }

      if (!bound) {
        const m = code.match(/^\s*(?:return\s*)?([A-Za-z_$][\w$]*)\s*\((.*)\)\s*;?\s*(?:return\s+false\s*;?)?\s*$/s);
        if (m) {
          const fname = m[1];
          const argStr = m[2] || '';
          const rawParts = argStr ? splitArgs(argStr) : [];
          const listener = (event) => {
            try {
              const fn = window[fname];
              if (typeof fn === 'function') {
                const args = resolveArgs(rawParts, event);
                const ret = fn.apply(el, args);
                if (endsWithReturnFalse || startsWithReturn) {
                  if (ret === false || endsWithReturnFalse) { try { event.preventDefault(); event.stopPropagation(); } catch (_) {} }
                }
              }
            } catch (e) { console.error('Handler failed', e); }
          };
          el.addEventListener(evt, listener);
          if (devMarkers) { try { el.classList.add('migrated-inline'); el.dataset.migratedInline = '1'; } catch (_) {} }
          bound = true;
        }
      }

      if (!bound) {
        const rf = code.match(/^\s*return\s+false\s*;?\s*$/s);
        if (rf) {
          const listener = (event) => { try { event.preventDefault(); event.stopPropagation(); } catch (_) {} };
          el.addEventListener(evt, listener);
          if (devMarkers) { try { el.classList.add('migrated-inline'); el.dataset.migratedInline = '1'; } catch (_) {} }
          bound = true;
        }
      }
      return bound;
    };

    // 1) Bind preserved data-on*-b64
    const dataNodes = scope.querySelectorAll('*');
    dataNodes.forEach((el) => {
      if (!el || !el.attributes) return;
      const toRemove = [];
      for (const attr of Array.from(el.attributes)) {
        const name = attr.name || '';
        if (!name.startsWith('data-on') || !name.endsWith('-b64')) continue;
        const evt = name.slice('data-on'.length, -'-b64'.length).replace(/^[-_]+/, '');
        let code = '';
        try { code = atob(attr.value || ''); } catch(_) { code = ''; }
        if (!evt || !code) { toRemove.push(name); continue; }
        bindFromCode(el, evt, String(code).trim());
        toRemove.push(name);
      }
      toRemove.forEach((n) => { try { el.removeAttribute(n); } catch(_){} });
    });

    // 2) Bind leftover inline attributes (if any)
    attrs.forEach((attr) => {
      const nodes = scope.querySelectorAll(`[${attr}]`);
      nodes.forEach((el) => {
        const original = el.getAttribute(attr);
        if (!original) return;
        const code = original.trim();
        const evt = attrToEvent(attr);
        const bound = bindFromCode(el, evt, code);
        if (bound) { try { el.removeAttribute(attr); } catch(_){} }
      });
    });
  }

  window.WebUISanitizer = { sanitize, migrateInlineHandlers };
})();

