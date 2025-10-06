(function () {
  const isSetupPage = window.location.pathname.startsWith('/setup');

  fetch('/api/v1/setup/status', { cache: 'no-store' })
    .then((response) => response.ok ? response.json() : null)
    .then((status) => {
      if (!status || !status.enabled) {
        return;
      }

      if (status.needs_setup && !isSetupPage) {
        window.location.replace('/setup');
      }

      if (!status.needs_setup && isSetupPage) {
        window.location.replace('/webui/');
      }
    })
    .catch(() => {
      // Ignore network errors here; setup.js will surface actionable messages.
    });
})();
