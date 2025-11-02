# MCP Unified - Documentation Ingestion Playbook

> Use this guide to pull a codebase’s documentation into the TLDW knowledge stores and expose it to your MCP-aware coding tools.

## Prerequisites

- TLDW server running with MCP Unified enabled (see `Docs/MCP/Unified/README.md`)
- Auth credentials (single-user API key or JWT) with permission to ingest media
- `media`, `knowledge`, and `notes` modules enabled in `tldw_Server_API/Config_Files/mcp_modules.yaml` (they are on by default)
- Documentation files in a supported format (`.md`, `.txt`, `.html`, `.pdf`, `.docx`, `.xml`, etc.)
- Optional: OpenAI-compatible provider keys if you plan to auto-summarize or generate embeddings during ingest

## 1. Prepare the Documentation Set

- Gather the docs you want indexed (project `README`, `docs/`, ADRs, API references, etc.).
- Normalize formats where possible (Markdown or HTML are fastest to process).
- Keep file paths meaningful-folder names become useful tags when you ingest.
- Large repos: stage a manifest first so you can retry failed uploads easily:

```bash
git ls-files 'docs/**/*' '*.md' README.md > doc_manifest.txt
```

## 2. Ingest Docs into the Media Database

Use the general media ingestion endpoint (`POST /api/v1/media/add`) with `media_type=document`. Each request can upload one or many files; the server handles chunking, OCR (if enabled), and metadata.

### Single-file example

```bash
BASE_URL="http://127.0.0.1:8000"
TOKEN="YOUR_JWT_OR_API_KEY"

curl -s -X POST "$BASE_URL/api/v1/media/add" \
  -H "Authorization: Bearer $TOKEN" \
  -F "media_type=document" \
  -F "title=Architecture Overview" \
  -F "keywords=docs,architecture" \
  -F "perform_analysis=false" \
  -F "generate_embeddings=true" \
  -F "files=@Docs/Architecture.md;type=text/markdown"
```

**Key form parameters**

- `media_type=document` - tells the pipeline to use the document parser.
- `keywords` - optional tags (`comma,separated`) that improve filtering later.
- `perform_analysis` - disable for a quick load; enable if you want automatic summaries.
- `generate_embeddings` - set to `true` if you rely on vector search or RAG pipelines.
- `files` - repeat this field for each file you want in the same request.
- `urls` - instead of `files`, you can point at raw GitHub URLs or docs hosting (must resolve to a supported extension or content-type).

### Bulk ingestion helper

For large doc trees, loop through your manifest so each file returns its own status:

```bash
BASE_URL="http://127.0.0.1:8000"
TOKEN="YOUR_JWT_OR_API_KEY"

while IFS= read -r file; do
  [ -f "$file" ] || continue
  curl -s -X POST "$BASE_URL/api/v1/media/add" \
    -H "Authorization: Bearer $TOKEN" \
    -F "media_type=document" \
    -F "title=$(basename "$file")" \
    -F "keywords=$(basename "$(dirname "$file")"),documentation" \
    -F "perform_analysis=false" \
    -F "generate_embeddings=true" \
    -F "files=@$file;type=text/markdown" \
    | jq '.status // .message'
done < doc_manifest.txt
```

Tips:
- Use directory names or git topics as keywords to keep queries scoped.
- If you require OCR (scanned PDFs), add `enable_ocr=true&ocr_mode=always`.
- Reruns with `overwrite_existing=true` replace earlier versions.

## 3. Verify the Content Landed

Before wiring your MCP client, sanity-check the database.

```bash
curl -s -X POST "$BASE_URL/api/v1/media/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "vector store", "media_types": ["document"], "results_per_page": 5}' \
  | jq '.results[] | {id, title}'
```

Or, via MCP directly:

```bash
curl -s -X POST "$BASE_URL/api/v1/mcp/tools/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "tool": "media.search",
        "arguments": {"query": "embedding pipeline", "limit": 3}
      }'
```

The response lists IDs (`id`) you will reference later with `knowledge.get` or `media.get`.

## 4. Confirm MCP Modules Are Live

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/mcp/modules" | jq '.modules[].id'
```

You should see at least `media`, `knowledge`, and `notes`. If a module is missing, update `Config_Files/mcp_modules.yaml` and restart the server so MCP Unified can register it.

## 5. Query Documentation from an MCP Client

Your agent can call MCP tools via HTTP (`/api/v1/mcp/tools/execute`) or WebSocket (`/api/v1/mcp/ws`). The aggregator module (`knowledge`) is the easiest entry point.

### Example: find relevant docs

```json
POST /api/v1/mcp/tools/execute
{
  "tool": "knowledge.search",
  "arguments": {
    "query": "chunking strategy",
    "limit": 5,
    "sources": ["media"],
    "snippet_length": 280
  }
}
```

Response highlights:
- `results[].id` - source-specific identifier (e.g., media ID)
- `results[].uri` - `media://{id}` for quick follow-up calls
- `results[].snippet` - preview text you can show in the client

### Retrieve full content

```json
POST /api/v1/mcp/tools/execute
{
  "tool": "knowledge.get",
  "arguments": {
    "source": "media",
    "id": 1234,
    "retrieval": {"mode": "full"}
  }
}
```

For fine-grained control (versions, transcripts, metadata), call `media.get` directly with the same `id`.

## 6. Wire Up an Agentic Coding Tool

Most MCP clients need the server URL, auth token, and (optionally) a default module. Example using Python + `httpx` for HTTP calls:

```python
import httpx

BASE_URL = "http://127.0.0.1:8000"
TOKEN = "YOUR_JWT_OR_API_KEY"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

def call_tool(tool, arguments):
    payload = {"tool": tool, "arguments": arguments}
    resp = httpx.post(f"{BASE_URL}/api/v1/mcp/tools/execute",
                      headers=HEADERS, json=payload, timeout=30.0)
    resp.raise_for_status()
    return resp.json()

def search_docs(query, limit=5):
    return call_tool("knowledge.search",
                     {"query": query, "limit": limit, "sources": ["media"]})

results = search_docs("vector compactor safeguards")
first_id = results["results"][0]["id"]
full_doc = call_tool("media.get", {"media_id": first_id,
                                   "retrieval": {"mode": "full"}})
```

WebSocket clients follow the JSON-RPC flow:
1. Connect to `/api/v1/mcp/ws?client_id=your-tool`.
2. Send an `initialize` request.
3. Issue `{"method": "tools/call", "params": {"name": "knowledge.search", "arguments": {...}}}` messages.
4. Cache `results[].uri` in your tool for later `knowledge.get`.

## 7. Ongoing Maintenance

- Re-run the ingestion loop after doc updates. Use `overwrite_existing=true` or bump keywords to generate new versions.
- Schedule periodic `media.search` spot checks to verify new files are discoverable.
- Enable embeddings for richer hybrid retrieval (`generate_embeddings=true`). The RAG services and MCP tools will automatically use them when available.
- Consider tagging documents with the git SHA (`keywords=docs,v1.4.2`) so you can scope queries to a release.
- If you expect concurrent ingest jobs, monitor `/api/v1/mcp/tools/execute` with `tool=media.get_media_metadata` to verify job completion.

You now have a repeatable pipeline: drop updated docs in, re-run the ingest script, and let your MCP client surface relevant pages on demand. If you automate this in CI, commit the manifest and ingestion script alongside the codebase so teammates can rebuild the knowledge base quickly.
