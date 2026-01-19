# How-To: Templated Chunking for Incoming PDFs

Use this to preview PDF extraction, pick or create a template, dry-run chunking, and ingest with friendly chunks. Server default is `http://127.0.0.1:8000`.
- Single-user auth header: `-H "X-API-KEY: $API_KEY"`
- Multi-user/JWT auth header: `-H "Authorization: Bearer $JWT"`

## What you need
- A PDF (local file or URL)
- Auth header for your mode
- Template name (built-in or custom) or willingness to auto-match

## Step 0: Preflight extraction (no DB)
Inspect the plain text before chunking so you know what the template will see.
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-pdfs" \
  -H "X-API-KEY: $API_KEY" \
  -F "perform_chunking=false" \
  -F "media_type=pdf" \
  -F "title=Preview" \
  -F "files=@/path/to/report.pdf"
```
- Review the `content` field to spot parser issues, missing tables, or noisy headers.
- For scanned PDFs, add `-F "enable_ocr=true"`.
- To switch parser: `-F "pdf_parsing_engine=pymupdf4llm"` (default) or `docling`.
- If using a URL instead of upload:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/media/process-pdfs" \
    -H "X-API-KEY: $API_KEY" \
    -F "perform_chunking=false" \
    -F "media_type=pdf" \
    -F "title=Preview" \
    -F "urls=https://example.com/report.pdf"
  ```

## Step 1: Pick or suggest a template
- Built-ins that work well for PDFs: `academic_paper`, `book_chapters`, `legal_document`, `code_documentation`, `transcript_dialogue`.
- List templates:
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/v1/chunking/templates" \
    -H "X-API-KEY: $API_KEY"
  ```
- Ask the server to rank matches for your filename/title:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates/match?filename=report.pdf&title=Quarterly%20Results&media_type=pdf" \
    -H "X-API-KEY: $API_KEY"
  ```
  Use a top candidate or keep the name for auto-apply.
- Want to copy/inspect built-ins? See `tldw_Server_API/app/core/Chunking/template_library/`.
- If responses include `X-Template-DB-Capability: fallback`, the template store is in-memory for this process; switch to `MediaDatabase` to persist.

## Step 2: Create or adjust a PDF-friendly template (optional)
Example: light cleaning, sentence chunks, overlap, and merging tiny fragments.
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "pdf_report_friendly",
    "description": "Chunk PDF reports with light cleaning and overlap for readability",
    "tags": ["pdf", "report", "friendly"],
    "template": {
      "classifier": {
        "media_types": ["pdf", "document"],
        "filename_regex": ".*\\.(pdf|docx)$",
        "title_regex": "(report|results|summary)",
        "priority": 2
      },
      "preprocessing": [
        { "operation": "normalize_whitespace", "config": { "max_line_breaks": 2 } },
        { "operation": "remove_headers", "config": { "patterns": ["^Page \\d+ of \\d+$"] } }
      ],
      "chunking": {
        "method": "sentences",
        "config": { "max_size": 6, "overlap": 1 }
      },
      "postprocessing": [
        { "operation": "filter_empty", "config": { "min_length": 40 } },
        { "operation": "merge_small", "config": { "min_size": 900, "separator": "\\n\\n" } }
      ]
    }
  }'
```
Validate the chunking block before saving if desired:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates/validate" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"chunking": {"method": "sentences", "config": {"max_size": 6, "overlap": 1}}}'
```

## Step 3: Dry-run the template on a sample excerpt
Paste a short excerpt from the PDF to confirm chunk boundaries.
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates/apply" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "pdf_report_friendly",
    "text": "Executive Summary\\n\\nRevenue grew 12% year-over-year ... (paste a few paragraphs here)",
    "override_options": {
      "max_size": 8,
      "overlap": 2
    }
  }'
```
Adjust `max_size`, `overlap`, or `merge_small.min_size` if the output looks choppy.

## Step 4: Ingest the PDF with the template (DB write)
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/add" \
  -H "X-API-KEY: $API_KEY" \
  -F "media_type=pdf" \
  -F "title=Quarterly Results Q1" \
  -F "perform_chunking=true" \
  -F "chunking_template_name=pdf_report_friendly" \
  -F "perform_analysis=false" \
  -F "generate_embeddings=true" \
  -F "files=@/path/to/report.pdf"
```
- Prefer `media_type=pdf` (not just `document`) to hint the parser and template classifier.
- To let the server pick, use `-F "auto_apply_template=true"` and provide a descriptive `title` and filename.
- For scanned PDFs, add `-F "enable_ocr=true"`; to force a parser, add `-F "pdf_parsing_engine=pymupdf4llm"` or `docling`.
- Using a URL instead of upload:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/media/add" \
    -H "X-API-KEY: $API_KEY" \
    -F "media_type=pdf" \
    -F "title=Quarterly Results Q1" \
    -F "perform_chunking=true" \
    -F "chunking_template_name=pdf_report_friendly" \
    -F "urls=https://example.com/report.pdf"
  ```

## Step 5: Confirm results and iterate
- The `/media/add` response shows `status`, `db_id`, and `chunks`. Spot-check the first few for continuity.
- Retrieve later with content:
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/v1/media/<db_id>?include_content=true" \
    -H "X-API-KEY: $API_KEY"
  ```
- Iterate template settings (size, overlap, merge thresholds) and re-run Steps 3–4 until chunks read cleanly.

## Quick tips
- Use small overlap (`1–2` sentences) for narrative/transcript PDFs to keep context across chunks.
- Keep `min_length`/`min_size` low enough so captions and bullets survive.
- Provide good `title` and filename—auto-match relies on them.
- For more options, see `Docs/Chunking/Chunking_Templates.md` and `Docs/User_Guides/Chunking_Templates_User_Guide.md`.

## Troubleshooting (fast answers)
- Template not found: check spelling or list with `/chunking/templates`.
- Empty/tiny chunks: lower `postprocessing.filter_empty.min_length` or `merge_small.min_size`.
- Template not persisting: check `X-Template-DB-Capability` header; if `fallback`, wire `MediaDatabase`.
- Bad text extraction: enable OCR, try `pdf_parsing_engine=docling`, or pre-clean the PDF.
- LLM-heavy methods (e.g., `rolling_summarize`): ensure server config has a provider+model+API key.

## Sample-driven template creation (e.g., 5 PDFs)
Use this loop to learn or tune templates from real documents and keep examples for demos.

1) Preflight and capture sample text (per PDF)
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-pdfs" \
  -H "X-API-KEY: $API_KEY" \
  -F "perform_chunking=false" \
  -F "media_type=pdf" \
  -F "title=Preview" \
  -F "files=@/path/to/PDF1.pdf" \
  -o /tmp/pdf1-preview.json
```
Extract a representative excerpt (e.g., first 1–2 sections) from the JSON `content` field and save to `/tmp/pdf1-snippet.txt`. Repeat for PDFs 2–5.

2) Learn a template from each sample
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates/learn" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"pdf1_learned\",
    \"description\": \"Learned from PDF1 sample\",
    \"example_text\": \"$(cat /tmp/pdf1-snippet.txt)\",
    \"save\": true,
    \"classifier\": { \"media_types\": [\"pdf\"], \"title_regex\": \"(pdf1|report1)\" }
  }"
```
Replace names/regex per PDF (e.g., `pdf2_learned`, `pdf3_learned`, etc.). The learner infers hierarchical boundaries and sets `hierarchical_template.boundaries` for you.

3) Validate and dry-run each learned template
```bash
# Validate config only
curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates/validate" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"chunking": {"method": "sentences"}}'

# Dry-run on a fresh excerpt from the same PDF
curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates/apply" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"template_name\": \"pdf1_learned\",
    \"text\": \"$(cat /tmp/pdf1-snippet.txt)\",
    \"override_options\": { \"max_size\": 8 }
  }"
```
Adjust overlaps or merge thresholds if chunks look choppy.

4) Show demo-ready ingestion for each PDF
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/add" \
  -H "X-API-KEY: $API_KEY" \
  -F "media_type=pdf" \
  -F "title=PDF1 Demo" \
  -F "perform_chunking=true" \
  -F "chunking_template_name=pdf1_learned" \
  -F "files=@/path/to/PDF1.pdf"
```
Repeat for PDFs 2–5 with their learned template names.

5) (Optional) Auto-apply by classifier instead of explicit name
Give each learned template a distinct `classifier` block (e.g., filename/title regex). Then ingest with:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/add" \
  -H "X-API-KEY: $API_KEY" \
  -F "media_type=pdf" \
  -F "title=PDF1 Demo" \
  -F "perform_chunking=true" \
  -F "auto_apply_template=true" \
  -F "files=@/path/to/PDF1.pdf"
```
Verify the applied template in the response metadata; adjust classifier regex if the wrong one triggers.




### Sample Templates

#### Project 2025: hierarchical sections, chapters, and bold subsections

- Project 2025 PDF: https://static.heritage.org/project2025/2025_MandateForLeadership_FULL.pdf
- This template:
  - Normalizes whitespace and strips page headers/roman numeral page markers.
  - Uses word-based chunks with a high ceiling (~3,500 words) to keep chapter-level context.
  - Treats `**SECTION N: ...**` as top-level sections.
  - Treats chapter markers of the form `#### **N**` as boundaries without making them headers (they live in the text).
  - Treats bold-only lines (e.g., `**MINORITY BUSINESS DEVELOPMENT AGENCY**`) as subsection headers.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "project_2025_hierarchical",
    "description": "Project 2025: hierarchical chunking by SECTION, numbered chapters, and bold subsections with ~3500-word chunks.",
    "tags": ["pdf","report","policy","project2025"],
    "template": {
      "classifier": {
        "media_types": ["pdf","document"],
        "title_regex": "(Project 2025|Mandate for Leadership|Presidential Transition)",
        "priority": 3
      },
      "preprocessing": [
        {
          "operation": "normalize_whitespace",
          "config": { "max_line_breaks": 2 }
        },
        {
          "operation": "remove_headers",
          "config": {
            "patterns": [
              "^—\\s*[xivlcdm]+\\s*—$",
              "^Page \\d+ of \\d+$"
            ]
          }
        },
        {
          "operation": "clean_markdown",
          "config": {
            "remove_links": true,
            "remove_images": true,
            "remove_formatting": false
          }
        }
      ],
      "chunking": {
        "method": "words",
        "config": {
          "max_size": 3500,
          "overlap": 20,
          "hierarchical": true,
          "hierarchical_template": {
            "boundaries": [
              {
                "kind": "header_atx",
                "pattern": "^\\*\\*SECTION\\s+\\d+\\s*:[^\\n]*\\*\\*\\s*$",
                "flags": "im"
              },
              {
                "kind": "chapter_number_line",
                "pattern": "^####\\s+\\*\\*\\d+\\*\\*\\s*$",
                "flags": "m"
              },
              {
                "kind": "header_atx",
                "pattern": "^\\*\\*(?!SECTION\\s+\\d+:)[^*\\n]+\\*\\*\\s*$",
                "flags": "m"
              }
            ]
          }
        }
      },
      "postprocessing": []
    }
  }'
```

#### Using the Project 2025 template with /process-pdfs (no DB)

You can dry-run extraction and hierarchical chunking without writing to the DB:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-pdfs" \
  -H "X-API-KEY: $API_KEY" \
  -F "perform_chunking=true" \
  -F "media_type=pdf" \
  -F "title=Project 2025 Preview" \
  -F "chunking_template_name=project_2025_hierarchical" \
  -F "files=@/path/to/2025_MandateForLeadership_FULL.pdf"
```

- The server will:
  - Extract markdown from the PDF.
  - Build chunking options from the form, then apply `project_2025_hierarchical`.
  - Re-chunk the final `content` using the template and return `results[*].chunks` with ancestry metadata (e.g., `ancestry_titles`, `section_path`).

If you prefer not to name the template explicitly, you can enable auto-selection (when multiple templates have classifiers):

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-pdfs" \
  -H "X-API-KEY: $API_KEY" \
  -F "perform_chunking=true" \
  -F "media_type=pdf" \
  -F "title=Project 2025: Mandate for Leadership" \
  -F "auto_apply_template=true" \
  -F "files=@/path/to/2025_MandateForLeadership_FULL.pdf"
```

#### Ingesting Project 2025 with the template via /media/add (DB write + embeddings)

This is the recommended path for RAG ingestion:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/add" \
  -H "X-API-KEY: $API_KEY" \
  -F "media_type=pdf" \
  -F "title=Project 2025: Mandate for Leadership" \
  -F "perform_chunking=true" \
  -F "chunking_template_name=project_2025_hierarchical" \
  -F "perform_analysis=false" \
  -F "generate_embeddings=true" \
  -F "files=@/path/to/2025_MandateForLeadership_FULL.pdf"
```

- `/media/add` will:
  - Apply the same template logic to build hierarchical chunks.
  - Persist content + chunk metadata (`ancestry_titles`, `section_path`) into the Media DB.
  - Optionally generate embeddings over those chunks for RAG.

To let the classifier choose the template instead of setting `chunking_template_name`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/add" \
  -H "X-API-KEY: $API_KEY" \
  -F "media_type=pdf" \
  -F "title=Project 2025: Mandate for Leadership" \
  -F "perform_chunking=true" \
  -F "auto_apply_template=true" \
  -F "perform_analysis=false" \
  -F "generate_embeddings=true" \
  -F "files=@/path/to/2025_MandateForLeadership_FULL.pdf"
```

For both `/process-pdfs` and `/media/add`, you can inspect the resulting `chunks` to verify:
- No chunk crosses chapter boundaries (chunks are emitted inside sections/chapters as defined by the template).
- Each chunk carries hierarchical metadata that can be used downstream for navigation, display, and RAG context.

##### Example: filtering chunks by chapter or subsection

Once you have the JSON response from `/process-pdfs` (or the stored chunks from `/media/add`), you can use the `section_path` / `ancestry_titles` metadata to select exactly the parts of the book you want for a RAG prompt.

Python example (client-side) using `/process-pdfs` output:

```python
import json

with open("Project2025_Chunked.json", "r", encoding="utf-8") as f:
    resp = json.load(f)

chunks = resp["results"][0]["chunks"]

# 1) All chunks from chapter 21 (DEPARTMENT OF COMMERCE)
chapter_21_chunks = [
    ch for ch in chunks
    if "**21**" in (ch.get("metadata", {}).get("section_path") or "")
]

# 2) Only the MINORITY BUSINESS DEVELOPMENT AGENCY subsection
mbda_chunks = [
    ch for ch in chunks
    if (ch.get("metadata", {}).get("section_path") or "").endswith(
        "**MINORITY BUSINESS DEVELOPMENT AGENCY**"
    )
]

print("Chapter 21 chunks:", len(chapter_21_chunks))
print("MBDA chunks:", len(mbda_chunks))
```

When building a RAG prompt, you can surface this hierarchy so the model knows exactly where the text comes from, for example:

```text
You are answering questions about the Project 2025 book.

Context section:
- Section path: {{chunk.metadata.section_path}}
- Titles: {{", ".join(chunk.metadata.ancestry_titles or [])}}
- Text:
{{chunk.text}}

Use the section path and titles to keep your answer grounded in the right chapter and subsection.
```

In your frontend, you can show the `section_path` as a breadcrumb (e.g., `SECTION 4: THE ECONOMY > 21 > DEPARTMENT OF COMMERCE > MINORITY BUSINESS DEVELOPMENT AGENCY`) whenever you render a chunk, which makes it easy for users to understand “where in the book” a given answer is coming from.
