from __future__ import annotations
import os, time
from dotenv import load_dotenv
from loguru import logger
from core.indexes import MEMORIES_INDEX, INSIGHTS_INDEX
from core.models import MemoryChunk, SearchResult, AgentInsight, InsightType
from utils.embeddings import get_embedder
from utils.endee_client import EndeeClient
load_dotenv()


class Recommender:
    """
    Recommendation engine powered by Endee vector search.

    Three types of recommendations:
      1. Related memories    — find similar chunks to what you are reading
      2. Forgotten memories  — surface chunks not seen in 30+ days
      3. Knowledge connector — find chunks from DIFFERENT files on same topic

    Usage:
        rec     = Recommender()
        related = rec.find_related(chunk_id="abc123")
        forgot  = rec.find_forgotten(days=30)
    """

    def __init__(self):
        self.endee    = EndeeClient()
        self.embedder = get_embedder()

    # ── 1. Related Memories ──────────────────────────────────────────────

    def find_related(
        self,
        chunk_id: str,
        top_k: int = 5,
        exclude_same_file: bool = False,
    ) -> list[SearchResult]:
        """
        Find memory chunks semantically similar to a given chunk.
        This powers the 'Related memories' panel in the dashboard.

        When user opens any document, this automatically surfaces
        4-5 related memories they may have forgotten about.

        Args:
            chunk_id:          ID of the chunk to find related content for.
            top_k:             Number of related chunks to return.
            exclude_same_file: If True only return chunks from OTHER files.
        """
        fetched = self.endee.fetch(MEMORIES_INDEX, [chunk_id])
        if not fetched:
            logger.warning(f"Chunk '{chunk_id}' not found in Endee.")
            return []

        source_file = fetched[0].get("metadata", {}).get("source_file", "")
        vec         = fetched[0]["values"]

        matches = self.endee.search(
            MEMORIES_INDEX,
            vector=vec,
            top_k=top_k + 5,
        )

        # Exclude the chunk itself
        matches = [m for m in matches if m["id"] != chunk_id]

        # Optionally exclude chunks from the same file
        if exclude_same_file:
            matches = [
                m for m in matches
                if m.get("metadata", {}).get("source_file", "") != source_file
            ]

        matches = matches[:top_k]

        return [
            SearchResult(
                chunk=MemoryChunk.from_endee_match(m),
                score=m.get("score", 0.0),
                rank=i + 1,
            )
            for i, m in enumerate(matches)
        ]

    # ── 2. Related by Query ──────────────────────────────────────────────

    def find_related_by_query(
        self,
        query: str,
        top_k: int = 5,
        exclude_source: str | None = None,
    ) -> list[SearchResult]:
        """
        Find memory chunks related to a natural language query.
        Used to surface memories after a search.

        Args:
            query:          Topic or concept to find related memories for.
            top_k:          Number of results.
            exclude_source: Exclude chunks from this file (avoid duplicates).
        """
        q_vec   = self.embedder.embed(query)
        matches = self.endee.search(
            MEMORIES_INDEX,
            vector=q_vec,
            top_k=top_k + 3,
        )

        if exclude_source:
            matches = [
                m for m in matches
                if m.get("metadata", {}).get("source_file", "") != exclude_source
            ]

        matches = matches[:top_k]

        return [
            SearchResult(
                chunk=MemoryChunk.from_endee_match(m),
                score=m.get("score", 0.0),
                rank=i + 1,
            )
            for i, m in enumerate(matches)
        ]

    # ── 3. Forgotten Memories ────────────────────────────────────────────

    def find_forgotten(
        self,
        query: str = "important notes study knowledge",
        days: int = 30,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Surface memory chunks that were uploaded long ago
        and have not appeared in recent searches.

        This is the 'you forgot about this' feature.
        Searches Endee for old chunks using a broad query.

        Args:
            query:  Broad topic query to find relevant old chunks.
            days:   Consider chunks older than this many days.
            top_k:  Number of forgotten memories to surface.
        """
        q_vec   = self.embedder.embed(query)
        matches = self.endee.search(
            MEMORIES_INDEX,
            vector=q_vec,
            top_k=100,
        )

        # Filter to chunks older than N days
        cutoff  = time.time() - days * 86400
        old     = [
            m for m in matches
            if float(m.get("metadata", {}).get("uploaded_at", time.time())) < cutoff
        ]

        old = old[:top_k]

        if not old:
            logger.info(f"No forgotten memories older than {days} days found.")
            return []

        logger.info(f"Found {len(old)} forgotten memories (>{days} days old)")

        return [
            SearchResult(
                chunk=MemoryChunk.from_endee_match(m),
                score=m.get("score", 0.0),
                rank=i + 1,
            )
            for i, m in enumerate(old)
        ]

    # ── 4. Cross-File Connector ──────────────────────────────────────────

    def find_cross_file_connections(
        self,
        query: str,
        top_k: int = 6,
    ) -> dict[str, list[SearchResult]]:
        """
        Find how the same topic appears across DIFFERENT files.
        Groups results by source file.

        Example:
            connections = rec.find_cross_file_connections("machine learning")
            # Returns:
            # {
            #   "study_notes.txt": [chunk1, chunk2],
            #   "meeting_notes.pdf": [chunk3],
            #   "email_export.txt": [chunk4],
            # }

        This shows the user how their knowledge on a topic
        is spread across multiple documents.
        """
        q_vec   = self.embedder.embed(query)
        matches = self.endee.search(
            MEMORIES_INDEX,
            vector=q_vec,
            top_k=top_k * 3,
        )

        # Group by source file
        grouped: dict[str, list[SearchResult]] = {}
        for m in matches:
            source = m.get("metadata", {}).get("source_file", "unknown")
            if source not in grouped:
                grouped[source] = []
            if len(grouped[source]) < 2:   # max 2 per file
                grouped[source].append(
                    SearchResult(
                        chunk=MemoryChunk.from_endee_match(m),
                        score=m.get("score", 0.0),
                        rank=0,
                    )
                )

        # Only return files that actually have results
        connected = {k: v for k, v in grouped.items() if v}

        logger.info(
            f"Cross-file connections for '{query[:40]}': "
            f"{len(connected)} files"
        )
        return connected

    # ── 5. Store Insight in Endee ────────────────────────────────────────

    def store_insight(self, insight: AgentInsight) -> str:
        """
        Store an agent-generated insight as a vector in Endee
        insights_index so it can be recalled in future sessions.
        """
        insight_text = f"{insight.insight_type.value}: {insight.title}. {insight.description}"
        emb          = self.embedder.embed(insight_text)

        self.endee.upsert(
            INSIGHTS_INDEX,
            [insight.to_endee_doc(emb)],
        )
        logger.info(f"Stored insight: {insight.title[:60]}")
        return insight.id

    def get_recent_insights(self, query: str = "pattern gap contradiction", top_k: int = 10) -> list[dict]:
        """
        Retrieve recent agent insights from Endee insights_index.
        Used by the dashboard insights panel.
        """
        q_vec   = self.embedder.embed(query)
        matches = self.endee.search(
            INSIGHTS_INDEX,
            vector=q_vec,
            top_k=top_k,
        )
        return [m.get("metadata", {}) for m in matches]