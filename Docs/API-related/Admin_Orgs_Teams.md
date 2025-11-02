# Admin: Organizations and Teams API

Base path: `/api/v1/admin`

All endpoints require admin authorization.

## Create Organization

POST `/api/v1/admin/orgs`

Request (application/json):
```json
{ "name": "Acme Corp", "slug": "acme" }
```

Response 200:
```json
{ "id": 1, "name": "Acme Corp", "slug": "acme", "owner_user_id": null, "is_active": true }
```

cURL:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/orgs \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp"}'
```

## List Organizations

GET `/api/v1/admin/orgs?limit=100&offset=0`

Response 200:
```json
[
  { "id": 1, "name": "Acme Corp", "slug": null, "owner_user_id": null, "is_active": true }
]
```

## Create Team (in Organization)

POST `/api/v1/admin/orgs/{org_id}/teams`

Request (application/json):
```json
{ "name": "Research", "slug": "research" }
```

Response 200:
```json
{ "id": 10, "org_id": 1, "name": "Research", "slug": "research", "is_active": true }
```

cURL:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/orgs/1/teams \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Research"}'
```

## List Teams (by Organization)

GET `/api/v1/admin/orgs/{org_id}/teams?limit=100&offset=0`

Response 200:
```json
[
  { "id": 10, "org_id": 1, "name": "Research", "slug": null, "description": null, "is_active": true }
]
```

## Add Team Member

POST `/api/v1/admin/teams/{team_id}/members`

Request (application/json):
```json
{ "user_id": 123, "role": "member" }
```

Response 200:
```json
{ "team_id": 10, "user_id": 123, "role": "member", "org_id": 1 }
```

## List Team Members

GET `/api/v1/admin/teams/{team_id}/members`

Response 200:
```json
[
  { "team_id": 10, "user_id": 123, "role": "member", "org_id": 1 }
]
```

---

See also: Virtual Keys API for budgeted/scoped keys you can associate with org/team contexts.
