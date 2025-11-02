# TLDW Server WebUI

A browser-based interface for testing and interacting with the TLDW Server API. This tool serves as an internal API documentation and testing platform, similar to Swagger or Postman, designed for single-user maintenance and development use.

## Quick Start

### Prerequisites
- TLDW Server API running (default: `http://localhost:8000`)
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Python 3.x (for serving the WebUI)

### Starting the WebUI

1. **Start the API Server** (in one terminal):
   ```bash
   cd /path/to/tldw_server
   # Set your API key (if using single-user mode)
   export SINGLE_USER_API_KEY="your-secret-api-key"
   python -m uvicorn tldw_Server_API.app.main:app --reload
   ```
   The API will be available at http://localhost:8000

2. **Start the WebUI** (in another terminal):

   **Option A: With Auto-Configuration (Recommended)**
   ```bash
   cd tldw_Server_API/WebUI
   # The script will auto-detect SINGLE_USER_API_KEY from environment
   ./Start-WebUI.sh
   ```

   **Option B: Manual Configuration**
   ```bash
   cd tldw_Server_API/WebUI
   python3 -m http.server 8080
   # You'll need to enter the API key manually in the UI
   ```

   **Option C: With Custom API URL**
   ```bash
   cd tldw_Server_API/WebUI
   export API_URL="http://your-server:8000"
   export SINGLE_USER_API_KEY="your-api-key"
   ./Start-WebUI.sh
   ```

3. **Open your browser** and navigate to:
   ```
   http://localhost:8080
   ```

⚠️ **Important**: Do NOT open `index.html` directly in your browser (file:// protocol) as this will cause CORS errors. Always use an HTTP server.

## Overview

The WebUI is a comprehensive testing interface for the TLDW Server API, providing:
- **Interactive API Testing**: Send requests and view responses for all API endpoints
- **Documentation**: See available endpoints with example payloads
- **Maintenance Tools**: Database operations, cleanup, backup/restore
- **Development Aid**: cURL command generation, request history, JSON viewer

### Use Case
This tool is designed for:
- Single-user operation on private networks
- API functionality verification
- Development and debugging
- System maintenance tasks
- Internal documentation reference

## Features

### Core Functionality
- **17 API Sections**: Complete coverage of all API endpoints
- **Request Builder**: Form-based inputs with validation
- **Response Viewer**: Syntax-highlighted JSON with collapsible sections
- **Request History**: Track and replay previous API calls
- **cURL Generation**: Export requests as cURL commands
- **Theme Support**: Dark/light mode with persistent preference

### API Sections Available
- **General**: Global settings and debug tools
- **Media**: Media management, versioning, and processing
- **Chat**: OpenAI-compatible chat completions
- **RAG**: Search and retrieval-augmented generation
- **Prompts**: Prompt library management
- **Notes**: Note-taking and knowledge management
- **Evaluations**: Model evaluation tools
  - OCR Evaluations:
    - `POST /api/v1/evaluations/ocr` accepts JSON with items `{ id, extracted_text, ground_truth_text }`, optional `metrics`, `ocr_options`, and `thresholds` (max_cer, max_wer, min_coverage, min_page_coverage)
    - `POST /api/v1/evaluations/ocr-pdf` accepts PDF uploads (`files`) and optional `ground_truths`, with OCR settings and `thresholds_json`
    - Results include averages and per-document metrics; per-page metrics appear when page-level ground truths are provided
- **Embeddings**: Vector embedding generation
  - Create Embeddings model selector now populates dynamically from `GET /api/v1/embeddings/models` and respects allowed/default flags.
- **Paper Search**: arXiv, BioRxiv/MedRxiv, and Semantic Scholar
- **Audio**: Text-to-speech functionality
- **Admin**: User management and system administration
- **Sync**: Synchronization operations
- **Health**: System health monitoring and diagnostics
- **MCP**: Model Context Protocol tools
- **Llama.cpp**: Local LLM server management
- **Web Scraping**: Web content ingestion service
- **Maintenance**: Database maintenance and batch operations

### Chat Persistence (Ephemeral by default)

- The Chat Completions tab includes a checkbox “Save to DB (persist conversation)”.
- When unchecked (default), chats are ephemeral and not saved in the database.
- When checked, the UI sends `save_to_db: true` and the server persists conversation/messages.
- The default state of this checkbox is driven by the server configuration exposed via `/webui/config.json`:
  - Environment: `CHAT_SAVE_DEFAULT=true`
  - Config file: `[Chat-Module] chat_save_default = True`
  - Otherwise, the fallback legacy default is `[Auto-Save] save_character_chats`.

### Related Documentation
- Chat API: `Docs/API-related/Chat_API_Documentation.md`
- Character Chat API: `Docs/CHARACTER_CHAT_API_DOCUMENTATION.md`

### Audio Endpoints
- `POST /api/v1/audio/speech` - Text-to-Speech (streaming and non-streaming)
- `GET  /api/v1/audio/voices/catalog` - List available TTS voices (supports `?provider=openai|elevenlabs`)

#### Recording Settings (TTS & Audio Tabs)
- The TTS tab (per provider) and the Audio → TTS / File Transcription panels include a collapsible “Recording Settings” section.
- Use “Max sec” to set a soft cap for microphone recordings; a countdown shows remaining seconds during capture.
- On the TTS tab, caps persist per provider; in Audio → TTS and File Transcription, caps persist per panel.
- If a recording is present, it overrides the file input and shows a “Using recorded sample” badge. Click “Clear” to restore file selection.
- Recommended reference clips: 3-15 seconds, mono, minimal background noise.

### OCR Providers

- The WebUI includes OCR evaluation forms under the Evaluations section (tabs: “OCR Evaluation” and “OCR PDF”).
- You can choose the OCR backend via the form field `OCR Backend`:
  - `tesseract` (default if installed), `dots` (dots.ocr), or `points` (POINTS-Reader).
- Optional fields in the form map to API options:
  - `Enable OCR`, `OCR Mode` (`fallback` or `always`), `OCR DPI`.
- Provider setup guides:
  - See `Docs/OCR/OCR_Providers.md` for side-by-side setup of dots.ocr and POINTS.
  - See `Docs/OCR/POINTS-Reader.md` for detailed POINTS configuration (Transformers vs SGLang, env vars, prompts).

Health and discovery
- The API exposes `GET /api/v1/ocr/backends` to list currently detected OCR backends and basic health (e.g., SGLang/vLLM reachability). Use this to verify configuration from the WebUI: open the “Config Info” or “Network” tab and issue a GET request.
- For POINTS (local Transformers) you can preload the model via `POST /api/v1/ocr/points/preload` to surface errors early.

### Recent Improvements

**v1.2.0 - Auto-Configuration Update**
- ✅ Added automatic API key detection from environment variables
- ✅ WebUI auto-populates credentials when running alongside server
- ✅ Configuration file support (webui-config.json)
- ✅ Visual indicators for auto-configured settings
- ✅ Simplified startup for local installations

**v1.1.0 - Stability Fixes**
- ✅ Fixed component initialization errors
- ✅ Removed debug/test files from production
- ✅ Cleaned up duplicate HTML structure in tab files
- ✅ Enhanced connection status indicator with response times
- ✅ Added fallback error handling for missing components
- ✅ Improved error messages and user feedback

## File Structure

```
WebUI/
├── index.html                 # Main application entry point
├── api-endpoints-config.json  # API endpoint documentation
├── webui-config.json         # Auto-generated configuration (gitignored)
├── Start-WebUI.sh            # Start script with auto-configuration
├── test-ui.sh                # Testing and verification script
├── css/
│   └── styles.css            # Application styles with theme support
├── js/
│   ├── api-client.js         # API communication layer
│   ├── chat-ui.js            # Chat interface functionality
│   ├── components.js         # Reusable UI components (Toast, Modal, etc.)
│   ├── endpoint-helper.js    # Endpoint configuration helper
│   ├── main.js              # Main application logic
│   └── utils.js             # Utility functions with security features
└── tabs/                     # Tab content HTML fragments
    ├── admin_content.html
    ├── audio_content.html
    ├── chat_content.html
    ├── embeddings_content.html
    ├── evaluations_content.html
    ├── general_content.html
    ├── health_content.html
    ├── llamacpp_content.html
    ├── maintenance_content.html
    ├── mcp_content.html
    ├── media_content.html
    ├── notes_content.html
    ├── prompts_content.html
    ├── rag_content.html
    ├── research_content.html
    ├── sync_content.html
    └── webscraping_content.html
```

## UI Feature Details

### Chat Dictionaries UI
- Location: Chat → Dictionaries
- Capabilities:
  - Create/activate/deactivate/delete dictionaries
  - Add entries (pattern, replacement, type literal/regex, probability 0.0-1.0, enabled, case sensitivity, group, max replacements)
  - Inline edit entries and toggle enabled state
  - Filter entries by pattern and type
  - Process sample text through a dictionary with optional token budget and group filter
  - Import dictionaries from markdown content and export the current dictionary to markdown
- Related API docs: `Docs/API-related/Chatbook_Features_API_Documentation.md` → Chat Dictionary API

### Providers UI
- Location: Providers tab (or Settings → Providers) in the WebUI
- Capabilities:
  - List configured providers and available models with metadata
  - Inspect provider health (status, circuit breaker, recent performance)
  - View request queue status (size, workers) and rate limiter settings
  - Copy `<provider>/<model>` names for use in Chat and RAG requests
- Backed by Providers API endpoints:
  - `GET /api/v1/llm/health`
  - `GET /api/v1/llm/providers`
  - `GET /api/v1/llm/providers/{provider}`
  - `GET /api/v1/llm/models`
  - `GET /api/v1/llm/models/metadata`
- Docs: `Docs/API-related/Providers_API_Documentation.md`

### RAG Guardrails Tip (Request Payload Helper)

When testing the RAG endpoint from the WebUI, you can add the following guardrails in the JSON request builder on the RAG tab:

```json
{
  "query": "What was WidgetCo revenue in 2024?",
  "enable_generation": true,
  "enable_injection_filter": true,
  "require_hard_citations": true,
  "enable_numeric_fidelity": true,
  "numeric_fidelity_behavior": "retry"  // continue | ask | decline | retry
}
```

Notes:
- The response will include `metadata.hard_citations` (per-sentence citations with `doc_id` and `start/end` offsets) and `metadata.numeric_fidelity` (present/missing/source_numbers).
- In production mode (`tldw_production=true`) or when `RAG_GUARDRAILS_STRICT=true`, the server defaults to enabling numeric fidelity and hard citations; you can still tighten behavior per request.

### RAG Streaming Tip: Contexts and "Why These Sources"

The streaming endpoint `POST /api/v1/rag/search/stream` now emits early context information, followed by reasoning and incremental answer chunks. Events are NDJSON lines:

```
{"type":"contexts","contexts":[{"id":"...","title":"...","score":0.73,"url":"...","source":"media_db"}, ...],"why":{"topicality":0.82,"diversity":null,"freshness":null}}
{"type":"reasoning","plan":["Gather top-k contexts","Rerank using strategy=...","Ground claims","Synthesize final answer"]}
{"type":"delta","text":"...partial token(s)..."}
{"type":"claims_overlay","spans":[...],"claims":[...]}  // optional overlays when enabled
{"type":"final_claims", ...}                          // final overlay summary
```

- The non-streaming search (`/api/v1/rag/search`) response includes `metadata.why_these_sources` with:
  - `diversity` (unique host/source ratio), `freshness` (recentness portion), `topicality` (normalized score), and `top_contexts` list.
- In the WebUI RAG tab, you can watch the Response area for the initial `contexts` line to quickly preview which documents are being considered and a lightweight `why` summary.

## Configuration

### Auto-Configuration (New in v1.2.0)
The WebUI now supports automatic configuration when running alongside a TLDW server installation:

1. **Environment Variables**: Set these before starting the WebUI:
   - `SINGLE_USER_API_KEY`: Your API authentication token
   - `API_URL`: Custom API server URL (optional, defaults to http://localhost:8000)

2. **Auto-Detection**: When using `Start-WebUI.sh`, the script will:
   - Check for `SINGLE_USER_API_KEY` in environment
   - Generate a `webui-config.json` file automatically
   - Pre-populate the API key in the UI
   - Show "✓ Auto-configured" indicator in the UI

3. **Configuration File**: The `webui-config.json` file:
   - Created automatically from environment variables
   - Loaded by the WebUI on startup
   - Excluded from version control (.gitignore)
   - Can be edited manually if needed

### Manual Configuration
If not using auto-configuration:
1. Open the WebUI in your browser
2. Navigate to the **General** tab (opens by default)
3. Configure your API settings:
   - **API Base URL**: Default is `http://localhost:8000`
   - **API Token**: Enter your authentication token
4. Click **Test Connection** to verify API connectivity

### Connection Status Indicators
- 🟢 **Green**: Connected and responsive
- 🟠 **Orange**: Connected but slow (>1000ms response time)
- 🔴 **Red**: Disconnected or error
- Hover over the status for detailed information

## Troubleshooting

### Common Issues

**"CORS error" in console**
- You're opening the file directly. Use the HTTP server method (see Quick Start)

**"Connection refused" or "API Unreachable"**
- Ensure the API server is running
- Check the API URL in Global Settings
- Verify: http://localhost:8000/docs shows the FastAPI documentation

**"404 Not Found" errors**
- Check you're using the correct ports:
  - API: http://localhost:8000
  - WebUI: http://localhost:8080 (or your chosen port)

**Tabs not loading**
- Clear browser cache: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
- Check browser console (F12) for JavaScript errors
- Verify all JS files are loading in Network tab

**"Auth Failed" status**
- Check your API token in Global Settings
- Ensure the token matches your API configuration

### Browser Console
Press F12 to open Developer Tools and check:
- **Console tab**: JavaScript errors or warnings
- **Network tab**: Failed requests or slow responses
- **Application tab**: Local storage and session data

## Security Notes

For single-user internal use, the current security measures are adequate:
- No hardcoded API tokens
- XSS protection through HTML escaping
- Safe DOM manipulation utilities
- Input validation on forms

For multi-user or public deployment, additional security measures would be needed (authentication flow, CSRF protection, etc.).

## Development

### Running Tests
```bash
cd tldw_Server_API/WebUI
./test-ui.sh
```
This script verifies:
- All required files exist
- Tab HTML files are properly formatted
- No debug files remain in production

### Making Changes
When modifying the WebUI:
1. Test against the current API implementation
2. Update `api-endpoints-config.json` for API changes
3. Use the safe utility functions in `utils.js` for DOM manipulation
4. Ensure no sensitive information is hardcoded
5. Run the test script to verify structure

### API Compatibility
The WebUI is designed to work with the TLDW Server API v0.1.0+. Check `/api/v1/docs` for the current API specification.

## Tips for Effective Use

1. **Save Common Requests**: Use browser bookmarks to save specific tab states
2. **Export Requests**: Use the cURL generation to save complex requests
3. **Monitor Performance**: Watch the connection status for API response times
4. **Use Request History**: Access previous requests with Ctrl+Shift+H
5. **Keyboard Shortcuts**:
   - `Ctrl/Cmd + K`: Search endpoints
   - `Ctrl/Cmd + Shift + D`: Toggle dark mode
   - `Ctrl/Cmd + Shift + H`: Show request history
   - `Escape`: Close modals

## Support

For issues or questions:
1. Check the browser console for errors
2. Verify the API is running and accessible
3. Review the troubleshooting section above
4. Check the main TLDW Server documentation

## License

This module is part of the TLDW Server project and follows the same licensing terms (GPLv3).

---

*Version 1.2.0 - Auto-configuration support for local installations*
#### RAG Post-Verification (Adaptive)

The RAG tab supports the unified pipeline. To validate answers against evidence and optionally run a bounded repair pass, include these fields in your request JSON (Advanced section → Custom payload), or in your client code:

```
{
  "query": "What is CRISPR?",
  "sources": ["media_db"],
  "enable_generation": true,
  "enable_post_verification": true,
  "adaptive_max_retries": 1,
  "adaptive_unsupported_threshold": 0.15,
  "adaptive_max_claims": 20,
  "low_confidence_behavior": "ask"
}
```

Environment toggles:
- `RAG_ADAPTIVE_ADVANCED_REWRITES` (default `true`) - uses HyDE + multi-strategy rewrites + diversity during the adaptive pass; set `false` to use a simpler single-query retrieval.
- `RAG_ADAPTIVE_TIME_BUDGET_SEC` - optional hard cap (seconds) for the post-verification phase.

When generation is enabled, the response attaches `metadata.post_verification` with `unsupported_ratio`, `total_claims`, `unsupported_count`, `fixed`, and `reason`.

#### RAG Two-Tier Reranking (Overrides)

To enable cost-aware reranking with cross-encoder shortlist → LLM rerank and optional per-request gating overrides, use the RAG tab’s Advanced → Custom payload with the following fields:

```
{
  "query": "Summarize the CUDA memory model",
  "sources": ["media_db"],
  "enable_generation": true,
  "enable_reranking": true,
  "reranking_strategy": "two_tier",
  // Optional request-level gating overrides (fall back to env defaults if omitted)
  "rerank_min_relevance_prob": 0.5,
  "rerank_sentinel_margin": 0.15,
  // Optional corpus namespace for per-corpus synonyms
  "corpus": "my_corpus"
}
```

Notes:
- If the calibrated relevance probability of the top document is below `rerank_min_relevance_prob`, or too close to the sentinel probability (margin < `rerank_sentinel_margin`), the server gates answer generation and returns `metadata.generation_gate` along with `metadata.reranking_calibration`.
- Dashboard panel “Generation Gated (5m)” shows recent gating activity. Metric name: `rag_generation_gated_total`.

#### Corpus Synonyms (Alias of index_namespace)

Place a JSON file with term → aliases under `Config_Files/Synonyms/<corpus>.json` (server side), for example:

```
{
  "cuda": ["compute unified device architecture"],
  "gpu": ["graphics processing unit"]
}
```

Then include `"corpus": "<corpus>"` (or `"index_namespace"`) in your RAG request payload to enrich query rewrites with these aliases.

### Feedback & Learning Tip
To enable the learning loop and per-user personalization while testing from the WebUI, add the following fields to your RAG payload (Advanced → Custom payload):

```
{
  "collect_feedback": true,
  "apply_feedback_boost": true,
  "feedback_user_id": "alice"
}
```

The WebUI also emits lightweight implicit feedback (click/expand/copy) for the documents in the response list. These signals are stored per-user under `Databases/user_databases/<user_id>/` to learn simple priors and pairwise preferences for learning-to-rank. No sensitive content is sent back to the server beyond the document id and event type.
