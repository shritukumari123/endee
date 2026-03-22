from __future__ import annotations
import os
from dotenv import load_dotenv
from loguru import logger
from core.models import MemoryChunk
from ingestion.file_parser import ParsedFile
load_dotenv()

CHUNK_SIZE      = int(os.getenv("CHUNK_SIZE",    400))
CHUNK_OVERLAP   = int(os.getenv("CHUNK_OVERLAP",  50))
MIN_CHUNK_WORDS = 30


def chunk_text(text: str, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> list:
    """
    Split text into overlapping word-count-based chunks.
    Overlap ensures no sentence is lost at chunk boundaries.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step   = max(1, chunk_size - overlap)
    i      = 0

    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) >= MIN_CHUNK_WORDS:
            chunks.append(" ".join(chunk_words))
        i += step

    return chunks


def create_chunks(parsed_file: ParsedFile) -> list:
    """
    Convert a ParsedFile into MemoryChunk objects ready for Endee.

    Each chunk knows:
      - which file it came from
      - its position in the document
      - total chunks from this file
    """
    raw_chunks = chunk_text(parsed_file.text)

    if not raw_chunks:
        logger.warning(f"No chunks created from '{parsed_file.filename}'")
        return []

    total  = len(raw_chunks)
    chunks = [
        MemoryChunk(
            content=content,
            source_file=parsed_file.filename,
            file_type=parsed_file.file_type,
            chunk_index=idx,
            total_chunks=total,
            word_count=len(content.split()),
        )
        for idx, content in enumerate(raw_chunks)
    ]

    avg_words = sum(c.word_count for c in chunks) // total
    logger.info(
        f"Created {total} chunks from '{parsed_file.filename}' "
        f"(avg {avg_words} words/chunk)"
    )
    return chunks