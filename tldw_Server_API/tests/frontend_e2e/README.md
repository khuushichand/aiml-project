Frontend WebUI E2E (Playwright)

Run the suite:
- `python -m pytest tldw_Server_API/tests/frontend_e2e -v`

Defaults:
- The tests start the FastAPI server automatically (single_user mode).
- The tests start the Next.js frontend automatically with `npm run dev -- -p <port>`.
- The sample ingest file is `tldw_Server_API/tests/assets/e2e_sample.txt`.

Env overrides:
- `SINGLE_USER_API_KEY=...` (API key for single_user auth; must be >=16 chars)
- `TEST_MODE=false` (disable server test mode shortcuts)
- `TLDW_FRONTEND_URL=http://127.0.0.1:8080` (use an existing frontend server)
- `TLDW_FRONTEND_CMD="npm run dev -- -p 8080"` (custom frontend start command)
- `PLAYWRIGHT_HEADLESS=0` (run headed)
