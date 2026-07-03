import json
from collections.abc import Sequence

import httpx


class SiliconFlowClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        embedding_model: str,
        embedding_fallback_models: Sequence[str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self.embedding_fallback_models = list(embedding_fallback_models or [])
        self.http_client = http_client or httpx.AsyncClient(timeout=60)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        response = await self.http_client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_json_object(content)

    async def embed(self, text: str) -> list[float]:
        last_error: Exception | None = None
        for model in [self.embedding_model, *self.embedding_fallback_models]:
            try:
                return await self._embed_with_model(text, model)
            except httpx.HTTPStatusError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise RuntimeError("No embedding models configured.")

    async def _embed_with_model(self, text: str, model: str) -> list[float]:
        response = await self.http_client.post(
            f"{self.base_url}/embeddings",
            headers=self._headers,
            json={"model": model, "input": text},
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


def _parse_json_object(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object.")
    return parsed
