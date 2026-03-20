# CDN and Static Asset Configuration

Guidelines for serving tldw_server static assets through a CDN and configuring cache behaviour.

## Cache-Control Headers

### Immutable Hashed Assets

Assets whose filenames include a content hash (e.g. `main.a1b2c3d4.js`) can be cached indefinitely:

```
Cache-Control: public, max-age=31536000, immutable
```

### HTML and API Responses

HTML entry points and API responses should always be revalidated:

```
Cache-Control: no-cache, must-revalidate
```

### Media Uploads

User-uploaded media (audio, video, images) should use moderate caching with revalidation:

```
Cache-Control: public, max-age=86400, must-revalidate
```

## CDN Setup

### Cloudflare

1. Point your domain's DNS to Cloudflare (proxy mode, orange cloud).
2. Under **Caching > Configuration**, set the browser cache TTL to "Respect Existing Headers".
3. Create a **Page Rule** for `/assets/*` with "Cache Level: Cache Everything" and "Edge Cache TTL: 1 month".
4. Create a **Page Rule** for `/api/*` with "Cache Level: Bypass" to ensure API calls are never cached.

### AWS CloudFront

1. Create a CloudFront distribution with the tldw_server origin (e.g. `https://tldw.example.com`).
2. Configure two cache behaviours:

   | Path Pattern | Cache Policy              | TTL     |
   |-------------|---------------------------|---------|
   | `/assets/*` | CachingOptimized          | 1 year  |
   | `Default`   | CachingDisabled           | 0       |

3. Set the **Origin Request Policy** to "AllViewer" so auth headers pass through for API calls.
4. Enable **Compress Objects Automatically** (gzip + Brotli).

## Cache Busting with Content Hashes

The Next.js frontend automatically includes content hashes in built asset filenames. No manual cache busting is needed for the WebUI.

For custom static files served by FastAPI, use a query-string or filename hash:

```python
from hashlib import md5
from pathlib import Path

def asset_url(path: str) -> str:
    content_hash = md5(Path(path).read_bytes()).hexdigest()[:8]
    return f"/static/{path}?v={content_hash}"
```

## CORS Configuration for CDN-Served Assets

When serving assets from a CDN domain different from the API origin, configure CORS in `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tldw.example.com",
        "https://cdn.example.com",
    ],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=86400,
)
```

Ensure your CDN forwards the `Origin` header to the origin server so FastAPI can evaluate the CORS policy correctly.

## Recommended Headers Summary

| Asset Type          | Cache-Control                          | CDN Edge TTL |
|--------------------|----------------------------------------|-------------|
| Hashed JS/CSS      | `public, max-age=31536000, immutable`  | 1 year      |
| HTML entry points  | `no-cache, must-revalidate`            | 0           |
| User media         | `public, max-age=86400, must-revalidate` | 1 day     |
| API responses      | Bypass                                 | 0           |
