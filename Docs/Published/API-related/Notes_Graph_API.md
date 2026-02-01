# Notes Graph API

Notes Graph provides a graph view of notes, tags, and sources. The current implementation returns stubbed graph responses for graph queries and supports manual link creation/removal.

Base path: `/api/v1/notes`

## Endpoints

- `GET /graph` - fetch a notes graph (stub response)
- `GET /{note_id}/neighbors` - fetch neighbors for a note (stub response)
- `POST /{note_id}/links` - create a manual link between notes
- `DELETE /links/{edge_id}` - delete a manual link

## Graph Query

`GET /api/v1/notes/graph`

Query params (NoteGraphRequest):
- `center_note_id`: focal note id (raw UUID or `note:<uuid>`)
- `radius`: 1 (default) or 2
- `edge_types`: CSV or repeated values (manual, wikilink, backlink, tag_membership, source_membership)
- `tag`: filter by tag id
- `source`: filter by source id
- `time_range.start`, `time_range.end`: ISO-8601 timestamps
- `time_range_field`: `created_at` or `updated_at`
- `max_nodes`, `max_edges`, `max_degree`: caps
- `format`: `default` or `cytoscape`
- `cursor`: paging cursor (see PRD)
- `allow_heavy`: allow heavy expansion when enabled

Response: `NoteGraphResponse`

Example response:
```
{
  "nodes": [
    {"id": "note:123", "type": "note", "label": "My Note", "degree": 2},
    {"id": "tag:ml", "type": "tag", "label": "ml"}
  ],
  "edges": [
    {"id": "e:1", "source": "note:123", "target": "tag:ml", "type": "tag_membership", "directed": false}
  ],
  "truncated": false,
  "truncated_by": [],
  "has_more": false,
  "cursor": null,
  "limits": {"max_nodes": 300, "max_edges": 1200, "max_degree": 40}
}
```

## Note Neighbors

`GET /api/v1/notes/{note_id}/neighbors`

- `note_id` accepts raw UUID or `note:<uuid>`.
- Uses the same query params as `/graph`.

## Create Manual Link

`POST /api/v1/notes/{note_id}/links`

Request: `NoteLinkCreate`

Example request:
```
{
  "to_note_id": "note:456",
  "directed": false,
  "weight": 1.0,
  "metadata": {"label": "related"}
}
```

Response (on success):
```
{
  "status": "created",
  "edge": {"id": "e:1", "source": "note:123", "target": "note:456"}
}
```

## Delete Manual Link

`DELETE /api/v1/notes/links/{edge_id}`

- `edge_id` accepts raw UUID or `e:<uuid>` / `edge:<uuid>`.

Response:
```
{"deleted": true, "edge_id": "e:1"}
```

## Core Objects

### GraphNode

```
{
  "id": "note:123",
  "type": "note",
  "label": "My Note",
  "created_at": "2025-01-01T12:00:00Z",
  "deleted": false,
  "degree": 2,
  "tag_count": 3,
  "primary_source_id": "source:yt:abcd"
}
```

### GraphEdge

```
{
  "id": "e:1",
  "source": "note:123",
  "target": "note:456",
  "type": "manual",
  "directed": false,
  "weight": 1.0,
  "label": "related"
}
```
