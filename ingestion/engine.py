from __future__ import annotations
import json, os, time
from dataclasses import dataclass, field
from dotenv import load_dotenv
from loguru import logger
from core.indexes import ENTITIES_INDEX, MEMORIES_INDEX
from core.models import Entity, MemoryChunk
from ingestion.chunker import create_chunks
from ingestion.file_parser import parse_file
from utils.embeddings import get_embedder
from utils.endee_client import EndeeClient
load_dotenv()

DEDUP_THRESHOLD = float(os.getenv("DEDUP_THRESHOLD", 0.85))


@dataclass
class IngestionResult:
    filename: str
    chunks_created: int = 0
    chunks_stored: int = 0
    duplicates_skipped: int = 0
    entities_extracted: int = 0
    processing_time_ms: float = 0.0
    errors: list = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class IngestionEngine:
    """
    Full ingestion pipeline:
    parse → chunk → embed (local, free) → dedup → store in Endee

    Usage:
        engine = IngestionEngine()
        result = engine.ingest_bytes(file_bytes, "notes.pdf")
    """

    def __init__(self):
        self.endee    = EndeeClient()
        self.embedder = get_embedder()
        self._llm     = None

    def _get_llm(self):
        """Lazy load Groq client — only for entity extraction."""
        if self._llm is None:
            api_key  = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("LLM_BASE_URL", "")
            if not api_key or api_key == "your_groq_api_key_here":
                return None
            from openai import OpenAI
            self._llm = OpenAI(api_key=api_key, base_url=base_url or None)
        return self._llm

    # ── Step 13 — Deduplication ─────────────────────────────────────────

    def _is_duplicate(self, chunk: MemoryChunk, embedding: list) -> bool:
        """
        Search Endee for a near-identical chunk.
        If cosine similarity >= DEDUP_THRESHOLD and same source file → duplicate.
        """
        try:
            matches = self.endee.search(
                MEMORIES_INDEX,
                vector=embedding,
                top_k=1,
            )
            if not matches:
                return False
            top         = matches[0]
            score       = top.get("score", 0.0)
            same_source = (
                top.get("metadata", {}).get("source_file", "") == chunk.source_file
            )
            if score >= DEDUP_THRESHOLD and same_source:
                logger.debug(f"Duplicate skipped (score={score:.3f})")
                return True
        except Exception as exc:
            logger.warning(f"Dedup check failed: {exc}")
        return False

    # ── Step 14 — Entity Extraction ─────────────────────────────────────

    def _extract_entities(self, chunks: list, embeddings: list) -> int:
        """
        Extract named entities from chunks using Groq (free).
        Stores entities in Endee entities_index.
        Returns number of entities stored.
        """
        llm = self._get_llm()
        if not llm:
            logger.debug("No LLM key — skipping entity extraction.")
            return 0

        model          = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        entity_vectors = []
        total_entities = 0

        for i in range(0, len(chunks), 5):
            batch_chunks = chunks[i:i + 5]
            combined     = "\n\n".join(
                f"[Chunk {c.chunk_index}] {c.content[:300]}"
                for c in batch_chunks
            )

            prompt = f"""Extract named entities from the text.
Return ONLY a JSON array. Each item must have:
  "name": entity name
  "type": person | place | organisation | concept | decision
  "context": sentence where it appears (max 80 words)
  "chunk_index": which chunk number

Text:
{combined}

Return only the JSON array, nothing else."""

            try:
                resp = llm.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=500,
                )
                raw = resp.choices[0].message.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]

                entities_data = json.loads(raw)
                if not isinstance(entities_data, list):
                    continue

                for ed in entities_data:
                    if not isinstance(ed, dict) or "name" not in ed:
                        continue

                    chunk_idx    = int(ed.get("chunk_index", 0))
                    source_chunk = batch_chunks[min(chunk_idx, len(batch_chunks) - 1)]

                    entity = Entity(
                        name=str(ed.get("name", ""))[:100],
                        entity_type=str(ed.get("type", "concept")),
                        context=str(ed.get("context", ""))[:400],
                        source_file=source_chunk.source_file,
                        chunk_id=source_chunk.id,
                    )

                    entity_text = f"{entity.entity_type} {entity.name}: {entity.context}"
                    emb         = self.embedder.embed(entity_text)
                    entity_vectors.append(entity.to_endee_doc(emb))
                    total_entities += 1

            except json.JSONDecodeError as exc:
                logger.warning(f"Entity JSON parse failed: {exc}")
            except Exception as exc:
                logger.warning(f"Entity extraction error: {exc}")

        if entity_vectors:
            self.endee.upsert(ENTITIES_INDEX, entity_vectors)
            logger.info(f"Stored {total_entities} entities")

        return total_entities

    # ── Step 12 — Core Ingestion ────────────────────────────────────────

    def _ingest_chunks(self, chunks: list) -> tuple:
        """
        Embed all chunks locally (free) then
        upsert non-duplicates into Endee memories_index.
        Returns (stored, skipped, all_embeddings)
        """
        if not chunks:
            return 0, 0, []

        texts      = [c.embed_text for c in chunks]
        embeddings = self.embedder.embed_batch(
            texts, show_progress=len(chunks) > 50
        )

        vectors_to_store = []
        skipped          = 0
        stored_embeddings = []

        for chunk, emb in zip(chunks, embeddings):
            if self._is_duplicate(chunk, emb):
                chunk.is_duplicate = True
                skipped += 1
                stored_embeddings.append(None)
            else:
                vectors_to_store.append(chunk.to_endee_doc(emb))
                stored_embeddings.append(emb)

        if vectors_to_store:
            self.endee.upsert(MEMORIES_INDEX, vectors_to_store)

        stored = len(vectors_to_store)
        logger.info(f"Stored {stored} chunks | {skipped} duplicates skipped")
        return stored, skipped, embeddings

    # ── Public API ──────────────────────────────────────────────────────

    def ingest_bytes(
        self,
        data: bytes,
        filename: str,
        extract_entities: bool = True,
    ) -> IngestionResult:
        """
        Full pipeline from raw bytes to Endee.

        Args:
            data:             Raw file bytes.
            filename:         Original filename.
            extract_entities: Run entity extraction (needs Groq key).

        Returns:
            IngestionResult with full stats.
        """
        t0     = time.perf_counter()
        result = IngestionResult(filename=filename)

        try:
            # Parse file
            parsed = parse_file(filename, data)

            # Create chunks
            chunks               = create_chunks(parsed)
            result.chunks_created = len(chunks)

            if not chunks:
                result.errors.append("No text could be extracted.")
                return result

            # Embed + dedup + store
            stored, skipped, all_embeddings = self._ingest_chunks(chunks)
            result.chunks_stored      = stored
            result.duplicates_skipped = skipped

            # Entity extraction
            if extract_entities and stored > 0:
                non_dup = [c for c in chunks if not c.is_duplicate]
                result.entities_extracted = self._extract_entities(
                    non_dup, all_embeddings
                )

        except ValueError as exc:
            result.errors.append(str(exc))
            logger.error(f"Ingestion error '{filename}': {exc}")
        except Exception as exc:
            result.errors.append(f"Unexpected error: {exc}")
            logger.exception(f"Unexpected error '{filename}'")

        result.processing_time_ms = round(
            (time.perf_counter() - t0) * 1000, 2
        )
        logger.success(
            f"Ingested '{filename}': "
            f"{result.chunks_stored} stored, "
            f"{result.duplicates_skipped} skipped, "
            f"{result.entities_extracted} entities, "
            f"{result.processing_time_ms}ms"
        )
        return result

    def ingest_file(self, filepath: str, extract_entities=True) -> IngestionResult:
        """Ingest directly from a file path."""
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            data = f.read()
        return self.ingest_bytes(data, filename, extract_entities)