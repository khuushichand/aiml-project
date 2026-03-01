# A/B Test SSE Client Example

Use Server-Sent Events to monitor an embeddings A/B test run in real time.

## JavaScript (EventSource)

```javascript
const runId = "<RUN_ID>";
const apiKey = "<SINGLE_USER_API_KEY>";

const url = `http://127.0.0.1:8000/api/v1/evaluations/abtest/runs/${runId}/events`;
const es = new EventSource(url, { withCredentials: false });

es.onmessage = (evt) => {
  const data = JSON.parse(evt.data);
  console.log("event", data.type, data);
};

es.addEventListener("completed", () => {
  console.log("run completed");
  es.close();
});

es.onerror = (err) => {
  console.error("sse error", err);
  es.close();
};
```

## Python (httpx stream)

```python
import httpx

run_id = "<RUN_ID>"
headers = {"X-API-KEY": "<SINGLE_USER_API_KEY>"}
url = f"http://127.0.0.1:8000/api/v1/evaluations/abtest/runs/{run_id}/events"

with httpx.stream("GET", url, headers=headers, timeout=60.0) as resp:
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        if line.startswith("data:"):
            print(line[5:].strip())
```
