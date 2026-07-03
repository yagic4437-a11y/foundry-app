import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class LegalChunk:
    id: str
    source: str
    article: str
    title: str
    text: str


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]:
        ...


class SimpleLegalRetriever:
    def __init__(self, chunks: list[LegalChunk]):
        self.chunks = chunks

    def retrieve(self, query: str, top_k: int = 5) -> list[LegalChunk]:
        query_terms = _tokenize(query)
        scored = [(self._score(query_terms, chunk), chunk) for chunk in self.chunks]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:top_k] if score > 0] or self.chunks[:top_k]

    def _score(self, query_terms: set[str], chunk: LegalChunk) -> float:
        body_terms = _tokenize(f"{chunk.source} {chunk.article} {chunk.title} {chunk.text}")
        overlap = query_terms.intersection(body_terms)
        return len(overlap) / math.sqrt(max(len(body_terms), 1))


class ChromaLegalStore:
    def __init__(self, path: str | Path, collection_name: str = "legal_articles"):
        import chromadb

        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(collection_name)

    def upsert(self, chunks: list[LegalChunk], embeddings: list[list[float]]) -> None:
        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {"source": chunk.source, "article": chunk.article, "title": chunk.title}
                for chunk in chunks
            ],
            documents=[chunk.text for chunk in chunks],
        )

    def retrieve_by_embedding(self, embedding: list[float], top_k: int = 5) -> list[LegalChunk]:
        result = self.collection.query(query_embeddings=[embedding], n_results=top_k)
        chunks: list[LegalChunk] = []
        for idx, chunk_id in enumerate(result["ids"][0]):
            metadata = result["metadatas"][0][idx]
            chunks.append(
                LegalChunk(
                    id=chunk_id,
                    source=metadata["source"],
                    article=metadata["article"],
                    title=metadata.get("title", ""),
                    text=result["documents"][0][idx],
                )
            )
        return chunks


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower())
        if token not in {"the", "and", "for", "with", "that", "this", "are"}
    }
