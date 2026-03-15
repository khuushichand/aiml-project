# API Versioning Strategy

## Current Versioning

All API endpoints are served under the `/api/v1/` prefix. This path-based versioning provides clear, explicit version identification in every request.

```
https://tldw.example.com/api/v1/chat/completions
https://tldw.example.com/api/v1/media/search
```

## Versioning Rules

### What Constitutes a Breaking Change

The following changes require a major version bump (e.g., v1 to v2):

- **Removing** an endpoint or field from a response
- **Renaming** an endpoint path or response field
- **Changing the type** of an existing response field (e.g., string to integer)
- **Changing required/optional status** of a request field (optional to required)
- **Changing authentication requirements** for an endpoint
- **Changing error response format** or status codes for existing error conditions

### Non-Breaking Changes (No Version Bump)

- Adding new endpoints
- Adding new optional fields to request bodies
- Adding new fields to response bodies
- Adding new query parameters (optional)
- Adding new enum values to existing fields
- Relaxing validation (e.g., increasing max length)

## Deprecation Policy

### Timeline

1. **Announcement** (Day 0): The deprecation is documented in the changelog, API docs, and response headers.
2. **Warning Period** (6 months): The deprecated endpoint/field continues to work but returns a `Deprecation` header and optionally a `Sunset` header:
   ```
   Deprecation: true
   Sunset: Sat, 01 Jan 2028 00:00:00 GMT
   ```
3. **Removal** (after 6 months): The endpoint/field is removed in the next major version.

### Deprecation Headers

Deprecated endpoints include standard headers:

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: 2028-01-01T00:00:00Z
Link: <https://docs.tldw.example.com/migration/v2>; rel="successor-version"
```

## Version Coexistence

When v2 is introduced:

- `/api/v1/` endpoints continue to operate during the deprecation period.
- `/api/v2/` endpoints are available immediately.
- Both versions share the same database and authentication system.
- Internal business logic is version-agnostic; versioning is handled at the endpoint/schema layer.

## Migration Guide Format

Each major version bump includes a migration guide in `Docs/API/migrations/`:

```
Docs/API/migrations/
  v1-to-v2.md
```

A migration guide contains:

1. **Summary** of changes
2. **Endpoint mapping** table (old path to new path)
3. **Field changes** table (old field to new field, with type changes)
4. **Code examples** showing before/after for common operations
5. **Timeline** with key dates (deprecation start, sunset)

## Changelog Format

The project changelog (`CHANGELOG.md` at repo root, when created) follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions:

```markdown
## [Unreleased]

### Added
- New endpoint: `POST /api/v1/foo/bar`

### Changed
- `GET /api/v1/baz` now returns `total_count` field in response

### Deprecated
- `GET /api/v1/old-endpoint` -- use `GET /api/v1/new-endpoint` instead (sunset: 2028-01-01)

### Removed
- `GET /api/v1/removed-endpoint` (deprecated since v0.9)

### Fixed
- Fixed 500 error on `POST /api/v1/media/process` with empty URL list
```

## Client Guidance

- Always specify the version prefix in your base URL.
- Subscribe to the project changelog for deprecation notices.
- Test against the `/docs` (Swagger UI) endpoint after upgrades.
- Use the `Deprecation` and `Sunset` response headers for automated migration tracking.
