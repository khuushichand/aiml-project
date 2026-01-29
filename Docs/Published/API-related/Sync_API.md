# Sync API

The Sync API exchanges change logs between a client and the server. Each change is represented as a sync log entry that includes the entity, operation, version, and payload.

Base path: `/api/v1/sync`

## Endpoints

- `POST /send` - send client changes to the server
- `GET /get` - fetch server changes for a client

## Send Changes

`POST /api/v1/sync/send`

Request: `ClientChangesPayload`

Example request:
```
{
  "client_id": "client_123",
  "last_processed_server_id": 1200,
  "changes": [
    {
      "change_id": 55,
      "entity": "Media",
      "entity_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "operation": "update",
      "timestamp": "2026-01-29T10:00:00Z",
      "client_id": "client_123",
      "version": 6,
      "payload": "{\"uuid\":\"f47ac10b-58cc-4372-a567-0e02b2c3d479\",\"title\":\"Updated Title\"}"
    }
  ]
}
```

Response:
```
{"status": "success"}
```

If no changes are sent:
```
{"status": "success", "message": "No changes received."}
```

## Get Changes

`GET /api/v1/sync/get?client_id=client_123&since_change_id=1200`

Response: `ServerChangesResponse`

Example response:
```
{
  "changes": [
    {
      "change_id": 12346,
      "entity": "Media",
      "entity_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "operation": "update",
      "timestamp": "2026-01-29T10:05:00Z",
      "client_id": "client_other_456",
      "version": 7,
      "payload": "{\"uuid\":\"f47ac10b-58cc-4372-a567-0e02b2c3d479\",\"title\":\"Server Title\"}"
    }
  ],
  "latest_change_id": 12350
}
```

## Core Objects

### SyncLogEntry

```
{
  "change_id": 12345,
  "entity": "Media",
  "entity_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "operation": "update",
  "timestamp": "2026-01-29T10:00:00Z",
  "server_timestamp": "2026-01-29T10:00:01Z",
  "client_id": "client_123",
  "version": 6,
  "payload": "{...}"
}
```

### ClientChangesPayload

```
{
  "client_id": "client_123",
  "changes": ["SyncLogEntry", "..."],
  "last_processed_server_id": 1200
}
```

### ServerChangesResponse

```
{
  "changes": ["SyncLogEntry", "..."],
  "latest_change_id": 12350
}
```
