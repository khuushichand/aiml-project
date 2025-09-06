/**
 * TTS Content Loader
 * Dynamically loads the comprehensive TTS interface when the Audio > TTS tab is selected
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
            ttsTabButton.addEventListener('click', loadTTSContent);
        }
        
        // Also check if we're already on the TTS tab (e.g., from a direct link)
        if (window.location.hash === '#tabAudioTTS') {
            loadTTSContent();
        }
    }
    
    async function loadTTSContent() {
        const container = document.getElementById('tts-main-content');
        if (!container) {
            console.error('TTS content container not found');
            return;
        }
        
        // Check if content is already loaded
        if (container.dataset.loaded === 'true') {
            // Just initialize TTS if needed
            if (typeof TTS !== 'undefined' && typeof TTS.init === 'function') {
                TTS.init();
            }
            return;
        }
        
        try {
            // Load the TTS content HTML
            const response = await fetch('tabs/tts_content.html');
            if (!response.ok) {
                throw new Error(`Failed to load TTS content: ${response.status}`);
            }
            
            const html = await response.text();
            
            // Extract just the inner content (skip the outer wrapper that's already in audio_content.html)
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const ttsContent = doc.querySelector('#tts-content');
            
            if (ttsContent) {
                container.innerHTML = ttsContent.innerHTML;
                container.dataset.loaded = 'true';
                
                // Initialize TTS module if available
                if (typeof TTS !== 'undefined' && typeof TTS.init === 'function') {
                    TTS.init();
                }
            } else {
                console.error('TTS content not found in loaded HTML');
            }
        } catch (error) {
            console.error('Error loading TTS content:', error);
            container.innerHTML = `
                <div class="error-message">
                    <h3>Error Loading TTS Interface</h3>
                    <p>${error.message}</p>
                    <p>Please refresh the page and try again.</p>
                </div>
            `;
        }
    }
    
    // Export for manual triggering if needed
    window.loadTTSContent = loadTTSContent;
})();