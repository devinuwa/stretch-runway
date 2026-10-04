import httpx
import json

schema = {
    "type": "object",
    "properties": {
        "hello": {"type": "string"}
    },
    "required": ["hello"]
}

payload = {
    "model": "gemma3:4b",
    "messages": [{"role": "user", "content": "Say hello world"}],
    "format": schema,
    "stream": False
}

try:
    r = httpx.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=30)
    print("Status:", r.status_code)
    print("Response:", json.dumps(r.json(), indent=2))
except Exception as e:
    print("Error:", e)
