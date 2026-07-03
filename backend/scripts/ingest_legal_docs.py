import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.legal_sources import download_legal_texts, load_legal_chunks
from app.llm_client import SiliconFlowClient
from app.rag import ChromaLegalStore


async def main() -> None:
    settings = get_settings()
    await download_legal_texts(settings.legal_docs_path)
    chunks = load_legal_chunks(settings.legal_docs_path)
    client = SiliconFlowClient(
        api_key=settings.siliconflow_api_key,
        base_url=settings.siliconflow_base_url,
        model=settings.siliconflow_model,
        embedding_model=settings.siliconflow_embedding_model,
        embedding_fallback_models=settings.embedding_fallback_models,
    )
    embeddings = [await client.embed(f"{chunk.source} {chunk.article}\n{chunk.text}") for chunk in chunks]
    ChromaLegalStore(settings.chroma_path).upsert(chunks, embeddings)
    print(f"Ingested {len(chunks)} legal article chunks into {settings.chroma_path}")


if __name__ == "__main__":
    asyncio.run(main())
