# EPUB Reader Guide

This guide covers the EPUB reading and analysis features available in tldw_server.

## Overview

As of v0.1.18, tldw_server provides comprehensive EPUB support, allowing you to:

- Upload and ingest EPUB files into your media library
- Read EPUB content with table of contents navigation
- Search within documents
- Create and manage bookmarks
- Integrate with AI chat for content analysis and discussion

## Supported Formats

| Format | Version | Notes |
|--------|---------|-------|
| EPUB 2.0 | Full support | Standard ebook format |
| EPUB 3.0 | Full support | Enhanced media features |

**Note:** DRM-protected EPUBs are not supported. You must have unrestricted access to the file content.

## Getting Started

### Uploading EPUB Files

**Via API:**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/media/process \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "file:///path/to/book.epub",
    "keywords": ["ebook", "fiction"]
  }'
```

**Via WebUI:**
1. Navigate to Media → Ingest
2. Select "Upload File" or drag and drop your EPUB
3. Add optional keywords and metadata
4. Click "Process"

### Accessing the Document Workspace

Once ingested, EPUB content is available in the Document Workspace:

1. Go to Documents in the WebUI
2. Find your EPUB in the library
3. Click to open the reader view

## Features

### Table of Contents Navigation

The reader displays the EPUB's table of contents in a sidebar, allowing you to:

- View the document structure at a glance
- Jump directly to any chapter or section
- Track your current position in the book

### Full-Text Search

Search within the document:

1. Press `Ctrl+F` (or `Cmd+F` on macOS)
2. Enter your search query
3. Navigate between matches with arrow buttons

### Bookmarks and Highlights

Create bookmarks to save your place:

- Click the bookmark icon on any page
- View all bookmarks in the Bookmarks panel
- Click a bookmark to return to that location

### AI Integration

Discuss EPUB content with the AI assistant:

1. Select a passage of text
2. Right-click and choose "Discuss with AI"
3. Ask questions about the selected content or the entire document

Example prompts:
- "Summarize this chapter"
- "Explain the main argument in this section"
- "What are the key takeaways from this book?"

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `←` / `→` | Previous / Next page |
| `Ctrl+F` / `Cmd+F` | Open search |
| `Escape` | Close search / dialogs |
| `Home` | Go to beginning |
| `End` | Go to end |
| `B` | Add bookmark at current position |
| `T` | Toggle table of contents |

## Configuration

### Processing Options

When ingesting EPUBs, you can configure:

```yaml
# In config.txt or via API
[Ebook-Processing]
extract_images: true       # Extract embedded images
chunk_size: 1000           # Characters per chunk for RAG
preserve_formatting: true  # Keep italics, bold, etc.
```

### Storage Location

EPUB content is stored in the Media Database:
- Full text extracted and chunked for search
- Metadata (title, author, publisher) indexed
- Cover images extracted when available

## API Reference

### Get EPUB Content

```bash
GET /api/v1/media/{media_id}/content
```

### Search Within Document

```bash
GET /api/v1/media/{media_id}/search?query=term
```

### Create Bookmark

```bash
POST /api/v1/media/{media_id}/bookmarks
Content-Type: application/json
{
  "position": "chapter-3-paragraph-5",
  "note": "Important passage about..."
}
```

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| EPUB won't open | Verify file is not DRM-protected |
| Missing images | Check `extract_images` is enabled |
| Table of contents empty | EPUB may lack NCX/nav structure |
| Search not finding content | Re-process with updated chunking settings |
| Formatting looks wrong | Complex CSS layouts may render differently |

### Known Limitations

- **DRM Protection**: Protected EPUBs cannot be processed
- **Complex Layouts**: Fixed-layout EPUBs may not display optimally
- **Interactive Content**: JavaScript-based interactive elements are not supported
- **Audio/Video**: Embedded media files are extracted but not playable in the reader

## See Also

- [Media Ingestion Guide](../Server/Web_Scraping_Ingestion_Guide.md)
- [Ingestion Pipeline - Ebooks](../../Code_Documentation/Ingestion_Pipeline_Ebooks.md)
- [RAG Production Configuration](../Server/RAG_Production_Configuration_Guide.md)
