import httpx
import pytest

from app.llm_client import SiliconFlowClient


@pytest.mark.asyncio
async def test_chat_json_posts_to_openai_compatible_endpoint():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"ok\": true}"}}]},
        )

    client = SiliconFlowClient(
        api_key="secret",
        base_url="https://api.siliconflow.com/v1",
        model="Qwen/Qwen3-8B",
        embedding_model="Qwen/Qwen3-Embedding-8B",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await client.chat_json("system", "user")

    assert result == {"ok": True}
    assert requests[0].url.path == "/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer secret"


@pytest.mark.asyncio
async def test_embed_tries_fallback_model_after_failure():
    requested_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode()
        requested_models.append(payload)
        if "Qwen/Qwen3-Embedding-8B" in payload:
            return httpx.Response(403, json={"error": {"message": "not free tier"}})
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    client = SiliconFlowClient(
        api_key="secret",
        base_url="https://api.siliconflow.com/v1",
        model="Qwen/Qwen3-8B",
        embedding_model="Qwen/Qwen3-Embedding-8B",
        embedding_fallback_models=["BAAI/bge-large-en-v1.5"],
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    embedding = await client.embed("hello")

    assert embedding == [0.1, 0.2, 0.3]
    assert len(requested_models) == 2
    assert "BAAI/bge-large-en-v1.5" in requested_models[1]
