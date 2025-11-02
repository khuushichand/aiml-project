# Admin RBAC API

This page summarizes the primary Admin RBAC endpoints with OpenAPI-style snippets and brief examples. Authentication uses either `X-API-KEY` (single-user mode) or `Authorization: Bearer <JWT>` (multi-user).

## Roles

GET /api/v1/admin/roles

```yaml
get:
  summary: List roles
  tags: [admin]
  responses:
    '200':
      description: Array of roles
```

POST /api/v1/admin/roles

```yaml
post:
  summary: Create role
  tags: [admin]
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            name: { type: string }
            description: { type: string }
  responses:
    '200': { description: Created role }
```

DELETE /api/v1/admin/roles/{role_id}

```yaml
delete:
  summary: Delete non-system role
  tags: [admin]
  parameters:
    - name: role_id
      in: path
      required: true
      schema: { type: integer }
  responses:
    '200': { description: Deleted }
```

## Permissions

GET /api/v1/admin/permissions

```yaml
get:
  summary: List permissions (optional filters: category, search)
  tags: [admin]
  responses:
    '200': { description: Array of permissions }
```

POST /api/v1/admin/permissions

```yaml
post:
  summary: Create permission
  tags: [admin]
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            name: { type: string }
            description: { type: string }
            category: { type: string }
  responses:
    '200': { description: Created permission }
```

GET /api/v1/admin/permissions/categories

```yaml
get:
  summary: List distinct permission categories
  tags: [admin]
```

## Role ↔ Permission Grants

GET /api/v1/admin/roles/{role_id}/permissions

```yaml
get:
  summary: List permissions granted to a role
  tags: [admin]
  parameters:
    - name: role_id
      in: path
      required: true
      schema: { type: integer }
```

GET /api/v1/admin/roles/matrix

```yaml
get:
  summary: Role/permission matrix (list view)
  tags: [admin]
  parameters:
    - name: category
      in: query
      required: false
      schema: { type: string }
    - name: search
      in: query
      required: false
      schema: { type: string }
```

GET /api/v1/admin/roles/matrix-boolean

```yaml
get:
  summary: Role/permission boolean matrix
  tags: [admin]
  parameters:
    - name: category
      in: query
      schema: { type: string }
    - name: search
      in: query
      schema: { type: string }
    - name: role_search
      in: query
      schema: { type: string }
    - name: role_names
      in: query
      schema:
        type: array
        items: { type: string }
```

## Tool Permissions (MCP Integration)

GET /api/v1/admin/permissions/tools

```yaml
get:
  summary: List tool permissions (tools.execute:*)
  tags: [admin]
```

POST /api/v1/admin/permissions/tools

```yaml
post:
  summary: Create tool permission (exact or wildcard)
  tags: [admin]
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            tool_name: { type: string }
            description: { type: string }
```

DELETE /api/v1/admin/permissions/tools/{perm_name}

```yaml
delete:
  summary: Delete tool permission by name (e.g., tools.execute:foo)
  tags: [admin]
  parameters:
    - name: perm_name
      in: path
      required: true
      schema: { type: string }
```

POST /api/v1/admin/roles/{role_id}/permissions/tools

```yaml
post:
  summary: Grant a tool permission to role (creates if missing)
  tags: [admin]
  parameters:
    - name: role_id
      in: path
      required: true
      schema: { type: integer }
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            tool_name: { type: string, description: "'*' for wildcard" }
```

DELETE /api/v1/admin/roles/{role_id}/permissions/tools/{tool_name}

```yaml
delete:
  summary: Revoke a tool permission from a role
  tags: [admin]
  parameters:
    - name: role_id
      in: path
      required: true
      schema: { type: integer }
    - name: tool_name
      in: path
      required: true
      schema: { type: string }
```

POST /api/v1/admin/roles/{role_id}/permissions/tools/batch

```yaml
post:
  summary: Batch grant tool permissions to a role
  tags: [admin]
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            tool_names:
              type: array
              items: { type: string }
```

POST /api/v1/admin/roles/{role_id}/permissions/tools/batch/revoke

```yaml
post:
  summary: Batch revoke tool permissions from a role
  tags: [admin]
  requestBody:
    content:
      application/json:
        schema:
          type: object
          properties:
            tool_names:
              type: array
              items: { type: string }
```

## Effective Permissions (New)

GET /api/v1/admin/roles/{role_id}/permissions/effective

```yaml
get:
  summary: Get role effective permissions (merged normal + tool)
  tags: [admin]
  parameters:
    - name: role_id
      in: path
      required: true
      schema: { type: integer }
  responses:
    '200':
      description: Effective permissions for the role
      content:
        application/json:
          schema:
            type: object
            properties:
              role_id: { type: integer }
              role_name: { type: string }
              permissions:
                type: array
                items: { type: string }
              tool_permissions:
                type: array
                items: { type: string }
              all_permissions:
                type: array
                items: { type: string }
```

## cURL Examples

```bash
# List roles
curl -H "X-API-KEY: $SINGLE_USER_API_KEY" http://127.0.0.1:8000/api/v1/admin/roles | jq

# Create role
curl -X POST -H "X-API-KEY: $SINGLE_USER_API_KEY" \
     -H 'Content-Type: application/json' \
     -d '{"name":"analyst","description":"Analyst role"}' \
     http://127.0.0.1:8000/api/v1/admin/roles | jq

# Grant tool permission to role
curl -X POST -H "X-API-KEY: $SINGLE_USER_API_KEY" \
     -H 'Content-Type: application/json' \
     -d '{"tool_name":"tools.execute:foo"}' \
     http://127.0.0.1:8000/api/v1/admin/roles/2/permissions/tools | jq

# Effective permissions
curl -H "X-API-KEY: $SINGLE_USER_API_KEY" \
     http://127.0.0.1:8000/api/v1/admin/roles/2/permissions/effective | jq
```
