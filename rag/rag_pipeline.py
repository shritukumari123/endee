from __future__ import annotations
import os, time
from dotenv import load_dotenv
from loguru import logger
from core.indexes import MEMORIES_INDEX
from core.models import RAGResponse
from utils.embeddings import get_embedder
from utils.endee_client import EndeeClient
load_dotenv()


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline.

    Flow:
      1. Embed user question (local, free)
      2. Search Endee for top K relevant chunks
      3. Feed chunks as context into Groq LLM (free)
      4. Return answer with source citations

    Usage:
        rag      = RAGPipeline()
        response = rag.query("What did I study about CAP theorem?")
        print(response.answer)
        print(response.sources)
    """

    SYSTEM_PROMPT = """You are Engram, a personal AI assistant.
Answer questions strictly based on the context provided below.
The context comes from the user's own uploaded documents — notes, PDFs, emails, meeting notes.

Rules:
- Answer only from the provided context
- If the context does not contain the answer say "I could not find this in your documents"
- Always cite which document your answer comes from using [Source: filename]
- Be concise and direct
- Use the user's own words where possible"""

    def __init__(self):
        self.endee    = EndeeClient()
        self.embedder = get_embedder()
        self._llm     = None

    def _get_llm(self):
        """Lazy load Groq client."""
        if self._llm is None:
            api_key  = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("LLM_BASE_URL", "")
            if not api_key or api_key == "your_groq_api_key_here":
                return None
            from openai import OpenAI
            self._llm = OpenAI(
                api_key=api_key,
                base_url=base_url or None
            )
        return self._llm

    # ── Retrieval ────────────────────────────────────────────────────────

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        file_type: str | None = None,
        source_file: str | None = None,
    ) -> list[dict]:
        """
        Retrieve top K relevant chunks from Endee.

        This is the core of RAG — finding the right context
        from thousands of document chunks in milliseconds.
        """
        q_vec   = self.embedder.embed(question)
        filters = {}
        if file_type:
            filters["file_type"] = file_type
        if source_file:
            filters["source_file"] = source_file

        matches = self.endee.search(
            MEMORIES_INDEX,
            vector=q_vec,
            top_k=top_k,
            filters=filters or None,
        )
        return matches

    # ── Context Builder ──────────────────────────────────────────────────

    def _build_context(self, matches: list[dict]) -> str:
        """Format retrieved chunks into a readable context block."""
        parts = []
        for i, m in enumerate(matches, 1):
            meta    = m.get("metadata", {})
            source  = meta.get("source_file", "unknown")
            content = meta.get("full_content", meta.get("content", ""))
            parts.append(f"[{i}] From: {source}\n{content}")
        return "\n\n---\n\n".join(parts)

    # ── Generation ───────────────────────────────────────────────────────

    def query(
        self,
        question: str,
        top_k: int = 5,
        file_type: str | None = None,
        source_file: str | None = None,
    ) -> RAGResponse:
        """
        Full RAG pipeline — retrieve context then generate answer.

        Args:
            question:    User's natural language question.
            top_k:       Number of chunks to retrieve from Endee.
            file_type:   Only search within this file type.
            source_file: Only search within this specific file.

        Returns:
            RAGResponse with answer, sources, and timing stats.
        """
        # Step 1 — Retrieve
        t0      = time.perf_counter()
        matches = self.retrieve(question, top_k, file_type, source_file)
        retrieval_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not matches:
            return RAGResponse(
                question=question,
                answer="I could not find any relevant documents. Please upload some files first.",
                sources=[],
                retrieval_time_ms=retrieval_ms,
            )

        # Step 2 — Build context
        context = self._build_context(matches)

        # Step 3 — Generate
        llm = self._get_llm()
        if not llm:
            # No LLM key — return retrieved chunks as answer
            answer = "LLM not configured. Top retrieved chunk:\n\n" + \
                     matches[0].get("metadata", {}).get("content", "")
            return RAGResponse(
                question=question,
                answer=answer,
                sources=[m.get("metadata", {}) for m in matches],
                retrieval_time_ms=retrieval_ms,
            )

        t1 = time.perf_counter()
        try:
            resp = llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Context from your documents:\n\n{context}\n\nQuestion: {question}"
                    },
                ],
                temperature=0.2,
                max_tokens=600,
            )
            answer = resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.error(f"LLM generation failed: {exc}")
            answer = f"Generation failed: {exc}"

        generation_ms = round((time.perf_counter() - t1) * 1000, 2)

        # Build sources list
        sources = [
            {
                "source_file": m.get("metadata", {}).get("source_file", ""),
                "content":     m.get("metadata", {}).get("content", "")[:200],
                "score":       round(m.get("score", 0.0), 4),
                "chunk_index": m.get("metadata", {}).get("chunk_index", 0),
            }
            for m in matches
        ]

        logger.info(
            f"RAG complete — retrieve: {retrieval_ms}ms, "
            f"generate: {generation_ms}ms"
        )

        return RAGResponse(
            question=question,
            answer=answer,
            sources=sources,
            retrieval_time_ms=retrieval_ms,
            generation_time_ms=generation_ms,
            chunk_count=len(matches),
        )

    # ── Streaming variant ────────────────────────────────────────────────

    def stream_query(self, question: str, top_k: int = 5):
        """
        Streaming version — yields answer tokens as they arrive.
        Used by the dashboard for real-time response display.
        """
        matches = self.retrieve(question, top_k)
        if not matches:
            yield "No relevant documents found. Please upload some files first."
            return

        context = self._build_context(matches)
        llm     = self._get_llm()
        if not llm:
            yield "LLM not configured. Add your Groq API key to .env"
            return

        try:
            stream = llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Context:\n\n{context}\n\nQuestion: {question}"
                    },
                ],
                temperature=0.2,
                max_tokens=600,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            yield f"Error: {exc}"