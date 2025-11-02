"""
Simple SSE client to stream A/B test progress updates.

Usage:
  python Helper_Scripts/Examples/abtest_sse_client.py --base http://localhost:8000 --test-id abtest_123 --api-key YOUR_KEY
"""
import argparse
import requests


def stream_events(base_url: str, test_id: str, api_key: str):
    url = f"{base_url.rstrip('/')}/api/v1/evaluations/embeddings/abtest/{test_id}/events"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    with requests.get(url, headers=headers, stream=True) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith('data: '):
                payload = line[len('data: '):]
                print(payload)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='Base server URL, e.g., http://localhost:8000')
    ap.add_argument('--test-id', required=True, help='AB test ID')
    ap.add_argument('--api-key', default='', help='API key or JWT token')
    args = ap.parse_args()
    stream_events(args.base, args.test_id, args.api_key)
