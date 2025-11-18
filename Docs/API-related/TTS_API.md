# TTS API


1. Client pattern (Python)

  Non‑streaming usage (stream: false), handling JSON errors vs audio:
```python
  import os, json, requests

  BASE_URL = os.getenv("TLDW_BASE_URL", "http://127.0.0.1:8000")
  API_KEY = os.environ["SINGLE_USER_API_KEY"]
  url = f"{BASE_URL}/api/v1/audio/speech"

  payload = {
      "model": "kokoro",
      "input": "Hello from client",
      "voice": "af_heart",
      "response_format": "mp3",
      "stream": False,
  }

  resp = requests.post(url, headers={"X-API-KEY": API_KEY}, json=payload)

  if resp.status_code != 200:
      # Structured error path
      try:
          err = resp.json()
      except ValueError:
          err = {"detail": resp.text}
      raise RuntimeError(f"TTS failed ({resp.status_code}): {err.get('detail', err)}")

  # Success: treat as audio
  with open("speech.mp3", "wb") as f:
      f.write(resp.content)
```

Streaming variant (Python, httpx):
```python
  import httpx, os, json

  client = httpx.Client(timeout=None)
  resp = client.post(
      url,
      headers={"X-API-KEY": API_KEY},
      json={**payload, "stream": True},
      stream=True,
  )

  if resp.status_code != 200:
      err = resp.json()
      raise RuntimeError(f"TTS failed ({resp.status_code}): {err.get('detail', err)}")

  with open("speech_streamed.mp3", "wb") as f:
      for chunk in resp.iter_bytes():
          if chunk:
              f.write(chunk)
  client.close()
```
  Key points for all Python clients:

  - Always check status_code.
  - Only treat body as audio when status_code == 200.
  - On non‑200, parse JSON and surface detail to the caller.

  ———

  2. Client pattern (JavaScript / TypeScript)

  Non‑streaming with fetch:
```javascript
  const baseUrl = process.env.TLDW_BASE_URL ?? "http://127.0.0.1:8000";

  async function ttsOnce(input: string): Promise<Blob> {
    const resp = await fetch(`${baseUrl}/api/v1/audio/speech`, {
      method: "POST",
      headers: {
        "X-API-KEY": process.env.SINGLE_USER_API_KEY!,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "kokoro",
        input,
        voice: "af_heart",
        response_format: "mp3",
        stream: false,
      }),
    });

    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try {
        const json = await resp.json();
        detail = json.detail ?? JSON.stringify(json);
      } catch (_) {
        detail = await resp.text();
      }
      throw new Error(`TTS failed: ${detail}`);
    }

    return await resp.blob(); // audio/mpeg
  }
```
  Streaming (browser) is trickier; typical pattern is:

  - Check resp.ok first.
  - If ok, read resp.body as a stream (e.g., into a MediaSource or buffer it).
  - If not ok, read JSON/text as above and treat as an error.



 Assumptions

  - Prometheus data source in Grafana is configured (e.g. named Prometheus).
  - You’re scraping:
      - tts_requests_total{provider,model,voice,format,status} (counter)
      - tts_request_duration_seconds_bucket (histogram)
  - For HTTP, adjust metric names/labels to your setup (examples use http_requests_total and path="/api/v1/audio/speech"; if yours differ, just swap names/labels).

  ———

  1. Panel: TTS Success Rate

  - Panel type: Time series
  - Title: TTS Success Rate
  - Query:

  sum(rate(tts_requests_total{status="success"}[5m]))
  /
  sum(rate(tts_requests_total[5m]))

  - Legend: success_rate
  - Display: as percentage (set unit to percent (0-1)).

  ———

  2. Panel: TTS Requests by Status

  - Panel type: Time series (stacked)
  - Title: TTS Requests by Status
  - Queries:

  sum by (status) (rate(tts_requests_total[5m]))

  - Stacking: normal
  - Legend: {{status}}

  This gives you success vs failure volume over time.

  ———

  3. Panel: TTS Latency (p50, p95)

  - Panel type: Time series
  - Title: TTS Latency (p50 / p95)
  - Queries:

  p50:

  histogram_quantile(
    0.50,
    sum(rate(tts_request_duration_seconds_bucket[5m])) by (le)
  )

  p95:

  histogram_quantile(
    0.95,
    sum(rate(tts_request_duration_seconds_bucket[5m])) by (le)
  )

  - Legend: p50, p95
  - Unit: s (seconds).

  If you want per-provider, add provider to the by clause:

  histogram_quantile(
    0.95,
    sum(rate(tts_request_duration_seconds_bucket[5m])) by (provider, le)
  )

  ———

  4. Panel: HTTP Error Rate for /audio/speech

  (Assuming http_requests_total{path="/api/v1/audio/speech",status="200"} or similar.)

  - Panel type: Time series
  - Title: HTTP Error Rate /api/v1/audio/speech
  - Query:

  sum(rate(http_requests_total{path="/api/v1/audio/speech", status=~"5.."}[5m]))
  /
  sum(rate(http_requests_total{path="/api/v1/audio/speech"}[5m]))

  - Unit: percent (0-1).

  If your metric is fastapi_requests_total or something else, just substitute the name and labels.

  ———

  5. Panel: Failures by Provider

  - Panel type: Time series or Bar chart
  - Title: TTS Failures by Provider
  - Query:

  sum by (provider) (
    rate(tts_requests_total{status="failure"}[5m])
  )

  - Legend: {{provider}}.

  This quickly shows which provider is causing most failures.

  ———

  6. Alerts (Grafana 8+ unified alerts conceptually)

  Use the same PromQL queries in alert rules.

  - Alert: TTS success rate below 95%
      - Query expression:

        sum(rate(tts_requests_total{status="success"}[5m]))
        /
        sum(rate(tts_requests_total[5m]))
      - Condition: WHEN query(A) IS BELOW 0.95 FOR 10m
      - Labels: severity=warning
      - Annotation summary: TTS success rate below 95%
      - Annotation description: short text like Check /api/v1/audio/speech logs and provider status.
  - Alert: HTTP 5xx rate for /audio/speech > 1%
      - Query expression:

        sum(rate(http_requests_total{path="/api/v1/audio/speech", status=~"5.."}[5m]))
        /
        sum(rate(http_requests_total{path="/api/v1/audio/speech"}[5m]))
      - Condition: WHEN query(A) IS ABOVE 0.01 FOR 10m
      - Labels: severity=critical
      - Annotation summary: High 5xx rate on /api/v1/audio/speech.
  - Alert: p95 TTS latency too high
      - Query expression (p95):

        histogram_quantile(
          0.95,
          sum(rate(tts_request_duration_seconds_bucket[5m])) by (le)
        )
      - Condition: WHEN query(A) IS ABOVE 5 FOR 10m (5 seconds as an example SLO)
      - Labels: severity=warning
      - Annotation summary: TTS p95 latency > 5s.

  ———
  


FIXME