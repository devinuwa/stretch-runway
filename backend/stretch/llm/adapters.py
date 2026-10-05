"""Model adapters for LLM interactions (T7)."""
import json
import time
import httpx
from typing import Protocol, Any

class ModelAdapter(Protocol):
    def generate(self, messages: list[dict], schema: dict | None = None) -> dict[str, Any]:
        """Generate a response. Returns {'content': str, 'prompt_tokens': int, 'completion_tokens': int, 'total_ms': int}."""
        ...

    def health(self) -> str:
        """Returns 'up', 'down', or 'disabled'."""
        ...


class OllamaAdapter:
    def __init__(self, model_id: str, base_url: str = "http://127.0.0.1:11434"):
        self.model_id = model_id
        self.base_url = base_url
        self._client = httpx.Client(timeout=120.0)

    def generate(self, messages: list[dict], schema: dict | None = None) -> dict[str, Any]:
        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
            # CPU laptop: small context, short output, keep the model warm.
            "options": {
                "temperature": 0.0,
                "num_ctx": 2048,
                "num_predict": 256,
            },
            "keep_alive": "30m",
        }
        if schema:
            payload["format"] = schema

        start_t = time.perf_counter()
        r = self._client.post(f"{self.base_url}/api/chat", json=payload)
        r.raise_for_status()
        end_t = time.perf_counter()

        data = r.json()
        return {
            "content": data["message"]["content"],
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_ms": int((end_t - start_t) * 1000)
        }

    def health(self) -> str:
        try:
            r = self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            if r.status_code == 200:
                tags = [m["name"] for m in r.json().get("models", [])]
                if self.model_id in tags:
                    return "up"
        except httpx.RequestError:
            pass
        return "down"

    def warm_up(self):
        try:
            self.generate([{"role": "user", "content": "hi"}])
        except Exception:
            pass


class StubModelAdapter:
    def __init__(self, canned_response: str = "{}"):
        self.canned_response = canned_response
        self.calls = []

    def generate(self, messages: list[dict], schema: dict | None = None) -> dict[str, Any]:
        self.calls.append({"messages": messages, "schema": schema})
        return {
            "content": self.canned_response,
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "total_ms": 50
        }

    def health(self) -> str:
        return "up"
