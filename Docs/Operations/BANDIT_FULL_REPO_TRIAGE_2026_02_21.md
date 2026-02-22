# Bandit Full Repo Triage (2026-02-21)

## Scope
- Command run:
  - `python -m bandit -r tldw_Server_API mock_openai_server Helper_Scripts -f json -o /tmp/bandit_full_repo_2026_02_21.json`
- Raw report:
  - `/tmp/bandit_full_repo_2026_02_21.json`

## Headline Numbers
- Full scan findings: `43,734`
- Full scan severity:
  - High: `59`
  - Medium: `922`
  - Low: `42,753`
- Dominant class (full repo): `B101 assert` (`40,477`) mostly from tests.

## Production-Focused Slice
Filtered to runtime backend code only:
- Path filter: `tldw_Server_API/app/**` excluding `**/tests/**`
- Production findings: `1,475`
- Production severity:
  - High: `52`
  - Medium: `773`
  - Low: `650`

Top production test IDs:
- `B608` (dynamic SQL construction): `694`
- `B110` (try/except/pass): `202`
- `B311` (non-crypto random): `93`
- `B603` (subprocess call): `89`
- `B324` (sha1/md5): `50`
- `B615` (HF downloads not revision pinned): `43`
- `B314` (xml.etree usage): `16`

## Prioritized Cleanup Backlog

### P0: Fix First (real risk, low ambiguity)
1. `B202` unsafe tar extraction
   - File: `tldw_Server_API/app/core/Sandbox/snapshots.py:199`
   - Current code validates path prefixes but still calls `tar.extractall(path)` directly.
   - Risk: archive link/symlink edge cases.
   - Action:
     - Use a strict member filter and skip links/special files before extraction.
     - Keep current traversal checks, add type checks (`islnk`, `issym`, device nodes).

2. `B301` legacy pickle deserialization
   - Files:
     - `tldw_Server_API/app/core/Scheduler/services/payload_service.py:163`
     - `tldw_Server_API/app/core/Web_Scraping/enhanced_web_scraping.py:481`
   - Risk: unsafe deserialize if legacy mode or legacy file is attacker-controlled.
   - Action:
     - Keep compatibility behind feature flags only.
     - Add signed payload validation (HMAC) before `pickle.loads`.
     - Add migration path + telemetry to remove pickle mode.

3. `B310` unbounded `urlopen` scheme surface
   - File: `tldw_Server_API/app/core/Workflows/adapters/integration/podcast_rss.py:207`
   - Risk: if `source_feed_url` is user-controlled, non-http(s) schemes may be reachable.
   - Action:
     - Explicitly allowlist `http`/`https` before `urlopen`.
     - Reject `file://`, `ftp://`, and custom schemes.

### P1: Security Hardening (high-value, medium effort)
4. `B615` Hugging Face downloads without revision pinning (`43`)
   - Key files:
     - `tldw_Server_API/app/core/Setup/install_manager.py`
     - `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Qwen3ASR.py`
     - `tldw_Server_API/app/core/Embeddings/Embeddings_Server/Embeddings_Create.py`
   - Risk: supply-chain drift/takeover from mutable tags.
   - Action:
     - Add `revision` (commit SHA/tag) requirement for all remote model loads.
     - Config schema: `model_id`, `revision`, `allow_unpinned=false` default.

5. `B314` XML parsing with stdlib `xml.etree` (`16`)
   - Key files:
     - `tldw_Server_API/app/core/Chunking/strategies/json_xml.py`
     - `tldw_Server_API/app/services/xml_processing_service.py`
     - `tldw_Server_API/app/core/Watchlists/*`
   - Risk: XML parser abuse / resource amplification.
   - Action:
     - Migrate untrusted-input paths to `defusedxml`.
     - Centralize parser helpers and ban direct `xml.etree` parsing on external input.

6. `B103` permissive permissions (`0o777`) in sandbox workspace
   - File: `tldw_Server_API/app/core/Sandbox/orchestrator.py:519`
   - Risk: broader local write/read than required.
   - Action:
     - Narrow mode to least privilege (e.g., `0o750`) where possible.
     - If `0o777` is required for container UID mapping, guard with explicit config and document rationale.

### P2: Hygiene + False-Positive Burn Down
7. `B324` md5/sha1 usage (`50`)
   - Predominantly cache keys, IDs, dedupe fingerprints (non-crypto intent).
   - Action:
     - Standardize `usedforsecurity=False` where supported.
     - Add explicit comments and targeted `# nosec B324` only on fallback lines.

8. `B608` dynamic SQL (`694`)
   - Most are low-confidence and appear to use parameterized values with dynamic table/column fragments.
   - Action:
     - Phase A: review medium-confidence subset (`229`) first.
     - Phase B: introduce helper API for safe identifier whitelisting and clause construction.
     - Phase C: add targeted suppressions once each callsite is proven constrained.

9. `B110` try/except/pass (`202`)
   - Action:
     - Replace silent pass with debug logging or narrow exception handling.
     - Keep intentional swallow only in cleanup/shutdown paths with comments.

## Recommended Execution Order
1. P0 (`B202`, `B301`, `B310`)
2. P1 (`B615`, `B314`, `B103`)
3. P2 (`B324`, `B608` medium-confidence subset, `B110`)

## Notes
- The full-repo count is heavily inflated by tests (`B101` assertions).
- For operational risk, the production slice is the relevant baseline (`1,475` findings).
