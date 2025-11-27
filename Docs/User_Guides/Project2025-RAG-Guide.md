1. Create (or overwrite) the project_2025_hierarchical template

  If you don’t already have it, use POST to create. If it already exists and you want to overwrite, use the PUT variant just below.

  API_KEY="YOUR_API_KEY_HERE"

  curl -X POST "http://127.0.0.1:8000/api/v1/chunking/templates" \
    -H "X-API-KEY: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "project_2025_hierarchical",
      "description": "Project 2025: hierarchical chunking by SECTION, numbered chapters, and ALL-CAPS bold subsections.",
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
          "method": "structure_aware",
          "config": {
            "max_size": 1000,
            "overlap": 0,
            "hierarchical": true,
            "hierarchical_template": {
              "boundaries": [
                {
                  "kind": "header_atx",
                  "pattern": "^\\*\\*SECTION\\s+\\d+\\s*:[^\\n]*\\*\\*\\s*$",
                  "flags": "im"
                },
                {
                  "kind": "header_atx",
                  "pattern": "^####\\s+\\*\\*\\d+\\*\\*\\s*$",
                  "flags": "m"
                },
                {
                  "kind": "bold_subsection",
                  "pattern": "^\\*\\*(?!SECTION\\s+\\d+:)([A-Z0-9][A-Z0-9&/\\- ,.\'()]*[A-Z0-9])\\*\\*\\s*$",
                  "flags": "m"
                }
              ]
            }
          }
        },
        "postprocessing": []
      }
    }'

  If you already have a template with that name and want to overwrite it:

  curl -X PUT "http://127.0.0.1:8000/api/v1/chunking/templates/project_2025_hierarchical" \
    -H "X-API-KEY: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "description": "Project 2025: hierarchical chunking by SECTION, numbered chapters, and ALL-CAPS bold subsections.",
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
          "method": "structure_aware",
          "config": {
            "max_size": 1000,
            "overlap": 0,
            "hierarchical": true,
            "hierarchical_template": {
              "boundaries": [
                {
                  "kind": "header_atx",
                  "pattern": "^\\*\\*SECTION\\s+\\d+\\s*:[^\\n]*\\*\\*\\s*$",
                  "flags": "im"
                },
                {
                  "kind": "header_atx",
                  "pattern": "^####\\s+\\*\\*\\d+\\*\\*\\s*$",
                  "flags": "m"
                },
                {
                  "kind": "bold_subsection",
                  "pattern": "^\\*\\*(?!SECTION\\s+\\d+:)([A-Z0-9][A-Z0-9&/\\- ,.\'()]*[A-Z0-9])\\*\\*\\s*$",
                  "flags": "m"
                }
              ]
            }
          }
        },
        "postprocessing": []
      }
    }'

  ———

  2. Workflow to validate processing/chunking

  Step 1 – Dry‑run chunking with /process-pdfs

  Use your Project 2025 PDF and the template, saving output to a JSON file:

  curl -X POST "http://127.0.0.1:8000/api/v1/media/process-pdfs" \
    -H "X-API-KEY: $API_KEY" \
    -F "perform_chunking=true" \
    -F "media_type=pdf" \
    -F "title=Project 2025: Mandate for Leadership" \
    -F "chunking_template_name=project_2025_hierarchical" \
    -F "files=@/path/to/2025_MandateForLeadership_FULL.pdf" \
    > Project2025_Chunked.json

  This will:

  - Extract markdown from the PDF.
  - Apply project_2025_hierarchical (structure‑aware, hierarchical).
  - Return results[0].chunks with text, ancestry_titles, section_path for each chunk.

  ———

  Step 2 – Sanity‑check chapter boundaries and hierarchy

  Use a small Python script to validate that:

  - No chunk crosses from one chapter into another (e.g., Commerce and Treasury in the same chunk).
  - Key chapter/subsection markers have sensible section_path.

  python - << 'PY'
  import json

  with open("Project2025_Chunked.json", "r", encoding="utf-8") as f:
      resp = json.load(f)

  chunks = resp["results"][0]["chunks"]

  # 1) Ensure no chunk contains both Commerce and Treasury chapter headings
  bad = []
  for i, ch in enumerate(chunks):
      t = ch["text"]
      if "DEPARTMENT OF** **COMMERCE" in t and "DEPARTMENT OF** **THE TREASURY" in t:
          bad.append(i)

  print("cross-chapter chunks (commerce+treasury):", bad)

  # 2) Confirm some chapter markers are present
  for chap in ["1", "8", "21", "30"]:
      marker = f"#### **{chap}**"
      seen = any(marker in ch["text"] for ch in chunks)
      print(f"chapter {chap} marker present:", seen)

  # 3) Inspect example section paths
  def first_with(needle):
      for i, ch in enumerate(chunks):
          if needle in ch["text"]:
              return i, ch
      return None, None

  idx_21, ch_21 = first_with("#### **21**")
  idx_commerce, ch_commerce = first_with("DEPARTMENT OF** **COMMERCE")
  idx_mbda, ch_mbda = first_with("MINORITY BUSINESS DEVELOPMENT AGENCY")

  print("\nChapter 21 marker chunk:", idx_21, "section_path:", ch_21["metadata"].get("section_path") if ch_21 else None)
  print("Commerce heading chunk:", idx_commerce, "section_path:", ch_commerce["metadata"].get("section_path") if ch_commerce else None)
  print("MBDA heading chunk:", idx_mbda, "section_path:", ch_mbda["metadata"].get("section_path") if ch_mbda else None)

  PY

  What “good” looks like:

  - cross-chapter chunks (commerce+treasury): []
  - chapter N marker present: True for at least the checked chapters.
  - section_path examples along the lines of:
      - Chapter number:
        T the citizenry … > **21**
      - Commerce chapter:
        T the citizenry … > **21** > **DEPARTMENT OF** **COMMERCE**
      - MBDA subsection:
        T > **MINORITY BUSINESS DEVELOPMENT AGENCY**

  ———

  Step 3 – Filter chunks by chapter/subsection for RAG

  Once validation passes, you can slice the same Project2025_Chunked.json into logical groups for prompts:

  python - << 'PY'
  import json

  with open("Project2025_Chunked.json", "r", encoding="utf-8") as f:
      resp = json.load(f)

  chunks = resp["results"][0]["chunks"]

  # All chunks from chapter 21
  chapter_21_chunks = [
      ch for ch in chunks
      if "**21**" in (ch.get("metadata", {}).get("section_path") or "")
  ]

  # Only the MINORITY BUSINESS DEVELOPMENT AGENCY subsection
  mbda_chunks = [
      ch for ch in chunks
      if (ch.get("metadata", {}).get("section_path") or "").endswith(
          "**MINORITY BUSINESS DEVELOPMENT AGENCY**"
      )
  ]

  print("Chapter 21 chunks:", len(chapter_21_chunks))
  print("MBDA chunks:", len(mbda_chunks))
  PY

  In your frontend / RAG layer, include section_path and ancestry_titles directly in the prompt and UI (breadcrumbs) so users and the model both know which chapter/subsection each chunk comes from.