This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/pages/api-reference/create-next-app).

## Getting Started

1) Configure environment variables (copy `.env.local.example` to `.env.local` and edit as needed):

```
cp .env.local.example .env.local
```

Key variables:

- `NEXT_PUBLIC_API_URL`: Backend URL (default: `http://127.0.0.1:8000`)
- `NEXT_PUBLIC_API_BASE_URL`: Optional. Absolute base URL for static assets and WebUI links. If set, this takes precedence over deriving the base from `NEXT_PUBLIC_API_URL`. Useful when the API is mounted under `/api/vN` behind a reverse proxy.
- `NEXT_PUBLIC_API_VERSION`: API version (default: `v1`)
- `NEXT_PUBLIC_X_API_KEY`: Optional. Single-user mode API key (sent as `X-API-KEY`).
- `NEXT_PUBLIC_API_BEARER`: Optional. Bearer token for chat module when server sets `API_BEARER`.

2) Run the development server (use port 8080 to match server CORS defaults):

```bash
npm run dev -- -p 8080
# or
yarn dev -p 8080
```

Open [http://localhost:8080](http://localhost:8080) with your browser.

 Unified streaming (dev)
 - To exercise the unified SSE/WS streaming in the backend, start the API with the dev overlay:
   `docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.dev.yml up -d --build`
  and set `NEXT_PUBLIC_API_URL` to `http://127.0.0.1:8000`. If you serve assets from a different origin or path than the API, set `NEXT_PUBLIC_API_BASE_URL` to the origin hosting web assets (e.g., `https://your-domain.example`).

You can start editing the page by modifying `pages/index.tsx`. The page auto-updates as you edit the file.

[API routes](https://nextjs.org/docs/pages/building-your-application/routing/api-routes) can be accessed on [http://localhost:3000/api/hello](http://localhost:3000/api/hello). This endpoint can be edited in `pages/api/hello.ts`.

The `pages/api` directory is mapped to `/api/*`. Files in this directory are treated as [API routes](https://nextjs.org/docs/pages/building-your-application/routing/api-routes) instead of React pages.

This project uses [`next/font`](https://nextjs.org/docs/pages/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Smoke Test

Run a quick connectivity check against the API:

```bash
cd tldw-frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 \
NEXT_PUBLIC_API_VERSION=v1 \
NEXT_PUBLIC_X_API_KEY=your_api_key \
npm run smoke
```

The script exercises providers, chat, RAG, audio voices, and connectors (optional). A 404 on connectors is expected if that module isn’t enabled on your server.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn-pages-router) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/pages/building-your-application/deploying) for more details.
