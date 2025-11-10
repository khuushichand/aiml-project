// webscraping.js
// Externalized bindings for Web Scraping tabs to remove inline handlers

(function () {
  function bind(id, fn) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('click', fn);
  }

  function confirmWrap(message, fn) {
    return (e) => { try { if (!window.confirm(message)) return; fn(e); } catch (_) {} };
  }

  function initWebScrapingBindings() {
    // Friendly ingest
    bind('friendlyIngest_submit', () => {
      if (typeof window.submitWebScrapingIngestFriendly === 'function') {
        window.submitWebScrapingIngestFriendly(false);
      }
    });
    bind('friendlyIngest_show_curl', () => {
      if (typeof window.submitWebScrapingIngestFriendly === 'function') {
        window.submitWebScrapingIngestFriendly(true);
      }
    });

    // Raw JSON ingest
    bind('btnWSIngestSubmit', () => window.makeRequest && window.makeRequest('webScrapingIngest', 'POST', '/api/v1/media/ingest-web-content', 'json'));
    // Legacy process
    bind('btnWSLegacySubmit', () => window.makeRequest && window.makeRequest('webScrapingProcessLegacy', 'POST', '/api/v1/media/process-web-scraping', 'json'));
    // Service status
    bind('btnWSStatus', () => window.makeRequest && window.makeRequest('webScrapingStatus', 'GET', '/api/v1/web-scraping/status', 'none'));
    // Job get/delete/progress
    bind('btnWSJobGet', () => window.makeRequest && window.makeRequest('webScrapingJobGet', 'GET', '/api/v1/web-scraping/job/{job_id}', 'none'));
    bind('btnWSJobDelete', confirmWrap('Cancel this job?', () => window.makeRequest && window.makeRequest('webScrapingJobDelete', 'DELETE', '/api/v1/web-scraping/job/{job_id}', 'none')));
    bind('btnWSProgress', () => window.makeRequest && window.makeRequest('webScrapingProgress', 'GET', '/api/v1/web-scraping/progress/{task_id}', 'none'));
    // Service init/shutdown
    bind('btnWSInit', () => window.makeRequest && window.makeRequest('webScrapingInit', 'POST', '/api/v1/web-scraping/service/initialize', 'none'));
    bind('btnWSShutdown', confirmWrap('Shutdown web scraping service?', () => window.makeRequest && window.makeRequest('webScrapingShutdown', 'POST', '/api/v1/web-scraping/service/shutdown', 'none')));
    // Cookies
    bind('btnWSCookiesGet', () => window.makeRequest && window.makeRequest('webScrapingCookiesGet', 'GET', '/api/v1/web-scraping/cookies/{domain}', 'none'));
    bind('btnWSCookiesSet', () => window.makeRequest && window.makeRequest('webScrapingCookiesSet', 'POST', '/api/v1/web-scraping/cookies/{domain}', 'json'));
    // Duplicates
    bind('btnWSDuplicates', () => window.makeRequest && window.makeRequest('webScrapingDuplicates', 'GET', '/api/v1/web-scraping/duplicates/check', 'query'));
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initWebScrapingBindings);
    else initWebScrapingBindings();
  }
})();
