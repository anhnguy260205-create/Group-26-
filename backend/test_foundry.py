"""Run from backend/ dir: python test_foundry.py
Bypasses the silent exception-swallowing in llm.py to show the REAL error.
"""
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv
load_dotenv()

endpoint = os.environ.get("AZURE_AI_ENDPOINT")
key = os.environ.get("AZURE_AI_API_KEY")
model = os.environ.get("AZURE_AI_MODEL", "claude-sonnet-4-5")

print(f"AZURE_AI_ENDPOINT = {endpoint!r}")
print(f"AZURE_AI_API_KEY set = {bool(key)}")
print(f"AZURE_AI_MODEL = {model!r}")

if not endpoint or not key:
    print("\n>>> Missing endpoint or key. .env not loading, wrong path, or typo.")
    exit()

url = endpoint.rstrip("/")
if "chat/completions" not in url:
    url = f"{url}/openai/v1/chat/completions"

api_version = os.environ.get("AZURE_AI_API_VERSION")
if api_version and "api-version=" not in url:
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}api-version={api_version}"

print(f"\nFull URL: {url}")

body = {
    "model": model,
    "max_tokens": 30,
    "messages": [
        {"role": "system", "content": "You are a calm respiratory therapist."},
        {"role": "user", "content": "Say hello in one short sentence."},
    ],
}

request = urllib.request.Request(
    url,
    data=json.dumps(body).encode("utf-8"),
    headers={
        "content-type": "application/json",
        "api-key": key,
        "authorization": f"Bearer {key}",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read())
        print("\n>>> SUCCESS")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"\n>>> HTTP ERROR {e.code}")
    print(e.read().decode())
except urllib.error.URLError as e:
    print(f"\n>>> URL ERROR (network/DNS issue)")
    print(e.reason)
except Exception as e:
    print(f"\n>>> OTHER ERROR: {type(e).__name__}: {e}")