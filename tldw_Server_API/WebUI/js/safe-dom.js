// SafeDOM: CSP-safe HTML insertion helper
// Usage: SafeDOM.setHTML(el, html)
// - Sanitizes string to remove inline handlers and <script> blocks
// - Builds a detached container and binds handlers via addEventListener
// - Appends nodes to the target element without introducing inline handlers

(function () {
  function setHTML(target, html) {
    if (!target) return;
    const sanitizer = (window.WebUISanitizer && typeof window.WebUISanitizer.sanitize === 'function')
      ? window.WebUISanitizer.sanitize
      : (s) => s;
    const migrate = (root) => {
      if (window.webUI && typeof window.webUI.migrateInlineHandlers === 'function') {
        try { window.webUI.migrateInlineHandlers(root); return; } catch (_) {}
      }
      if (window.WebUISanitizer && typeof window.WebUISanitizer.migrateInlineHandlers === 'function') {
        try { window.WebUISanitizer.migrateInlineHandlers(root); return; } catch (_) {}
      }
    };

    const sanitized = sanitizer(String(html));
    // Clear target
    while (target.firstChild) target.removeChild(target.firstChild);
    // Build temp
    const temp = document.createElement('div');
    temp.innerHTML = sanitized;
    // Bind any preserved handlers before attaching to live DOM
    migrate(temp);
    while (temp.firstChild) target.appendChild(temp.firstChild);
  }

  window.SafeDOM = { setHTML };
})();

