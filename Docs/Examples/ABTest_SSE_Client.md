# A/B Test SSE Client Examples

## JavaScript (EventSource)

```html
<script>
  const base = 'http://localhost:8000';
  const testId = 'abtest_123';
  const url = `${base}/api/v1/evaluations/embeddings/abtest/${testId}/events`;

  const evt = new EventSource(url, { withCredentials: false });
  evt.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      console.log('update:', data);
      // render progress and status from data.status and data.stats
    } catch (err) {
      console.error('parse error', err, e.data);
    }
  };
  evt.onerror = (e) => {
    console.error('SSE error', e);
    evt.close();
  };
  // close when done
  // evt.close();
</script>
```

## Python (requests)

```bash
python Helper_Scripts/Examples/abtest_sse_client.py --base http://localhost:8000 --test-id abtest_123 --api-key YOUR_KEY
```

This prints each SSE `data:` payload JSON line as progress updates.

