from __future__ import annotations
import os, time
from dotenv import load_dotenv
from loguru import logger
from core.indexes import MEMORIES_INDEX, ENTITIES_INDEX
from core.models import MemoryChunk, SearchResult
from utils.embeddings import get_embedder
from utils.endee_client import EndeeClient
load_dotenv()


class SearchEngine:
    """
    Semantic search over all documents stored in Endee.

    Three search modes:
      1. Basic semantic search    — embed query → search Endee
      2. Filtered search          — add metadata filters (file type, source)
      3. Multi-query search       — generate paraphrases → merge results

    Usage:
        engine  = SearchEngine()
        results = engine.search("CAP theorem distributed systems")
    """

    def __init__(self):
        self.endee    = EndeeClient()
        self.embedder = get_embedder()

    # ── Basic Semantic Search ────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
        source_file: str | None = None,
        since_days: int | None = None,
    ) -> list[SearchResult]:
        """
        Search all documents in Endee by semantic similarity.

        Args:
            query:       Natural language query.
            top_k:       Number of results to return.
            file_type:   Filter by file type (pdf, txt, csv, docx, markdown).
            source_file: Filter by specific filename.
            since_days:  Only return chunks uploaded in last N days.

        Returns:
            List of SearchResult sorted by similarity score.
        """
        t0    = time.perf_counter()
        q_vec = self.embedder.embed(query)

        # Build metadata filters
        filters = {}
        if file_type:
            filters["file_type"] = file_type
        if source_file:
            filters["source_file"] = source_file

        matches = self.endee.search(
            MEMORIES_INDEX,
            vector=q_vec,
            top_k=top_k * 2 if since_days else top_k,
            filters=filters or None,
        )

        # Filter by upload date if requested
        if since_days:
            cutoff  = time.time() - since_days * 86400
            matches = [
                m for m in matches
                if float(m.get("metadata", {}).get("uploaded_at", 0)) >= cutoff
            ]
            matches = matches[:top_k]

        results = [
            SearchResult(
                chunk=MemoryChunk.from_endee_match(m),
                score=m.get("score", 0.0),
                rank=i + 1,
            )
            for i, m in enumerate(matches)
        ]

        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Search '{query[:50]}' → {len(results)} results in {elapsed}ms"
        )
        return results

    # ── Entity Search ────────────────────────────────────────────────────

    def search_entities(
        self,
        query: str,
        entity_type: str | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        Search for named entities across all documents.

        Example:
            results = engine.search_entities("Rahul", entity_type="person")
            # finds all mentions of Rahul across every uploaded file
        """
        q_vec   = self.embedder.embed(query)
        filters = {"entity_type": entity_type} if entity_type else None

        matches = self.endee.search(
            ENTITIES_INDEX,
            vector=q_vec,
            top_k=top_k,
            filters=filters,
        )

        return [
            {
                "name":        m.get("metadata", {}).get("name", ""),
                "type":        m.get("metadata", {}).get("entity_type", ""),
                "context":     m.get("metadata", {}).get("context", ""),
                "source_file": m.get("metadata", {}).get("source_file", ""),
                "score":       m.get("score", 0.0),
            }
            for m in matches
        ]

    # ── Multi-Query Search ───────────────────────────────────────────────

    def multi_query_search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
    ) -> list[SearchResult]:
        """
        Generate 3 paraphrases of the query using the embedder's
        most_similar trick, search all of them, merge and deduplicate.

        Better recall than single query — finds results that use
        different words to describe the same concept.
        """
        # Generate query variants manually
        variants = [
            query,
            f"information about {query}",
            f"notes on {query}",
        ]

        seen:    dict[str, SearchResult] = {}
        freq:    dict[str, int]          = {}

        for q in variants:
            for r in self.search(q, top_k=top_k, file_type=file_type):
                if r.chunk.id not in seen:
                    seen[r.chunk.id] = r
                    freq[r.chunk.id] = 0
                freq[r.chunk.id] += 1

        # Re-rank: results found by more queries rank higher
        ranked = sorted(
            seen.values(),
            key=lambda r: (freq[r.chunk.id], r.score),
            reverse=True,
        )
        return ranked[:top_k]

    # ── Related Documents ────────────────────────────────────────────────

    def find_related(
        self,
        chunk_id: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Find documents semantically related to a specific chunk.
        Used by the recommendation panel in the dashboard.

        Example:
            # User opens a note about CAP theorem
            # System automatically surfaces related chunks
            related = engine.find_related(chunk.id)
        """
        fetched = self.endee.fetch(MEMORIES_INDEX, [chunk_id])
        if not fetched:
            logger.warning(f"Chunk '{chunk_id}' not found.")
            return []

        vec     = fetched[0]["values"]
        matches = self.endee.search(
            MEMORIES_INDEX,
            vector=vec,
            top_k=top_k + 1,
        )

        # Exclude the chunk itself
        matches = [m for m in matches if m["id"] != chunk_id][:top_k]

        return [
            SearchResult(
                chunk=MemoryChunk.from_endee_match(m),
                score=m.get("score", 0.0),
                rank=i + 1,
            )
            for i, m in enumerate(matches)
        ]

    # ── Stats ────────────────────────────────────────────────────────────

    def get_all_sources(self) -> list[str]:
        """
        Get list of all unique source files in Endee.
        Used to populate the filter dropdown in the dashboard.
        """
        try:
            # Broad search to get a sample of all chunks
            dummy_vec = [0.01] * self.embedder.dim
            matches   = self.endee.search(
                MEMORIES_INDEX,
                vector=dummy_vec,
                top_k=200,
            )
            sources = list(set(
                m.get("metadata", {}).get("source_file", "")
                for m in matches
                if m.get("metadata", {}).get("source_file", "")
            ))
            return sorted(sources)
        except Exception:
            return []