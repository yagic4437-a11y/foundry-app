import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from app.rag import LegalChunk


EU_AI_ACT_URL = "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng"
GDPR_URL = "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng"

FALLBACK_EU_AI_ACT = """
Article 3
Definitions
This Article defines terms including AI system and provider.

Article 5
Prohibited AI practices
Certain AI practices are prohibited, including manipulative or exploitative AI practices and certain social scoring uses.

Article 6
Classification rules for high-risk AI systems
AI systems are high-risk when they meet the conditions in this Regulation, including systems listed in Annex III.

Article 50
Transparency obligations for providers and deployers of certain AI systems
Certain AI systems require transparency to users, including interaction with AI systems.
"""

FALLBACK_GDPR = """
Article 5
Principles relating to processing of personal data
Personal data shall be processed lawfully, fairly and transparently, collected for specified purposes, and limited to what is necessary.

Article 6
Lawfulness of processing
Processing shall be lawful only if at least one lawful basis applies.

Article 9
Processing of special categories of personal data
Processing special categories of personal data is prohibited unless a specific exception applies.

Article 32
Security of processing
Controllers and processors shall implement appropriate technical and organisational measures to ensure security.

Article 35
Data protection impact assessment
A data protection impact assessment is required where processing is likely to result in a high risk to rights and freedoms.
"""


def chunk_articles(text: str, source: str) -> list[LegalChunk]:
    matches = list(re.finditer(r"(?im)^\s*(Article\s+\d+[a-zA-Z]?)\s*$", text))
    chunks: list[LegalChunk] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        article = match.group(1).strip()
        body = text[start:end].strip()
        if not body:
            continue
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        title = lines[0] if lines else article
        chunk_text = "\n".join(lines)
        chunk_id = f"{source.lower().replace(' ', '-')}-{article.lower().replace(' ', '-')}"
        chunks.append(LegalChunk(id=chunk_id, source=source, article=article, title=title, text=chunk_text))
    return chunks


async def download_legal_texts(target_dir: Path) -> dict[str, Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "EU AI Act": target_dir / "eu_ai_act.txt",
        "GDPR": target_dir / "gdpr.txt",
    }
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        await _download_or_fallback(client, EU_AI_ACT_URL, outputs["EU AI Act"], FALLBACK_EU_AI_ACT)
        await _download_or_fallback(client, GDPR_URL, outputs["GDPR"], FALLBACK_GDPR)
    return outputs


def load_legal_chunks(target_dir: Path) -> list[LegalChunk]:
    target_dir.mkdir(parents=True, exist_ok=True)
    eu_path = target_dir / "eu_ai_act.txt"
    gdpr_path = target_dir / "gdpr.txt"
    if not eu_path.exists():
        eu_path.write_text(FALLBACK_EU_AI_ACT, encoding="utf-8")
    if not gdpr_path.exists():
        gdpr_path.write_text(FALLBACK_GDPR, encoding="utf-8")
    return [
        *chunk_articles(eu_path.read_text(encoding="utf-8", errors="ignore"), "EU AI Act"),
        *chunk_articles(gdpr_path.read_text(encoding="utf-8", errors="ignore"), "GDPR"),
    ]


async def _download_or_fallback(
    client: httpx.AsyncClient, url: str, output_path: Path, fallback_text: str
) -> None:
    try:
        response = await client.get(url)
        response.raise_for_status()
        text = _html_to_text(response.text)
        if "Article 5" not in text:
            text = fallback_text
    except Exception:
        text = fallback_text
    output_path.write_text(text, encoding="utf-8")


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
