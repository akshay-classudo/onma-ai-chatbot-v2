"""Paragraph-aware text chunking, small-corpus edition.

The build guide's V2 spec targets 500-800 token chunks with overlap, sized
for a whole crawled site. Our corpus is a handful of hand-written knowledge
entries (a few hundred words each), so a simpler paragraph-packing chunker
with no overlap is enough — there's rarely more than one chunk per entry in
practice, and never so many that overlap would matter for recall.
"""

MAX_CHARS = 800


def chunk_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph

    if current:
        chunks.append(current)

    return chunks
