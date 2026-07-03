from app.legal_sources import chunk_articles
from app.rag import LegalChunk, SimpleLegalRetriever


def test_chunk_articles_preserves_article_numbers_and_text():
    text = """
    Article 5
    Prohibited AI practices
    AI systems that manipulate people are prohibited.

    Article 6
    Classification rules for high-risk AI systems
    AI systems listed in Annex III are high-risk.
    """

    chunks = chunk_articles(text, source="EU AI Act")

    assert [chunk.article for chunk in chunks] == ["Article 5", "Article 6"]
    assert chunks[0].source == "EU AI Act"
    assert "manipulate people" in chunks[0].text


def test_simple_retriever_returns_relevant_legal_chunks():
    retriever = SimpleLegalRetriever(
        [
            LegalChunk(
                id="gdpr-6",
                source="GDPR",
                article="Article 6",
                title="Lawfulness of processing",
                text="Processing personal data requires a lawful basis.",
            ),
            LegalChunk(
                id="ai-5",
                source="EU AI Act",
                article="Article 5",
                title="Prohibited practices",
                text="Manipulative or exploitative AI practices can be prohibited.",
            ),
        ]
    )

    results = retriever.retrieve("personal data in employee workflow", top_k=1)

    assert len(results) == 1
    assert results[0].article == "Article 6"
