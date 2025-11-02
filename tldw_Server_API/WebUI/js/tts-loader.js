/**
 * TTS Content Initializer
 * Initializes the TTS interface when the Audio > TTS tab is selected
 * Content is already loaded as part of audio_content.html
 */

(function() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTTSLoader);
    } else {
        initTTSLoader();
    }

    function initTTSLoader() {
        // Listen for tab clicks on the TTS sub-tab button
        const ttsTabButton = document.querySelector('[data-content-id="tabAudioTTS"]');
        if (ttsTabButton) {
            ttsTabButton.addEventListener('click', initializeTTS);
        }

        // Also check if we're already on the TTS tab (e.g., from a direct link)
        if (window.location.hash === '#tabAudioTTS') {
            initializeTTS();
        }
    }

    function initializeTTS() {
        // Initialize TTS module if available
        if (typeof TTS !== 'undefined' && typeof TTS.init === 'function') {
            console.log('Initializing TTS module');
            TTS.init();
        } else {
            console.log('TTS module not yet loaded, will initialize when ready');
        }
    }

    // Export for manual triggering if needed
    window.initializeTTS = initializeTTS;
})();
