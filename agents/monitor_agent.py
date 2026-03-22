from __future__ import annotations
import os, time, uuid
from dataclasses import dataclass, field
from dotenv import load_dotenv
from loguru import logger
from core.indexes import MEMORIES_INDEX, INSIGHTS_INDEX
from core.models import AgentInsight, InsightType
from recommendations.recommender import Recommender
from utils.embeddings import get_embedder
from utils.endee_client import EndeeClient
load_dotenv()


@dataclass
class AgentRunReport:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: float = field(default_factory=time.time)
    patterns_found: int = 0
    contradictions_found: int = 0
    gaps_found: int = 0
    forgotten_found: int = 0
    insights_stored: int = 0
    duration_seconds: float = 0.0
    summary: str = ""


class MonitorAgent:
    """
    Autonomous agent that scans your entire memory in Endee
    and generates insights — patterns, contradictions, gaps.

    Runs automatically on a schedule or manually from dashboard.

    How Endee is used here:
      - Reads all chunks from memories_index
      - Stores each insight as a vector in insights_index
      - Future runs recall past insights for comparison

    Usage:
        agent  = MonitorAgent()
        report = agent.run()
        print(report.summary)
    """

    def __init__(self):
        self.endee      = EndeeClient()
        self.embedder   = get_embedder()
        self.recommender = Recommender()
        self._llm       = None

    def _get_llm(self):
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

    # ── Fetch sample chunks from Endee ───────────────────────────────────

    def _fetch_sample_chunks(self, top_k: int = 100) -> list[dict]:
        """
        Pull a broad sample of chunks from Endee memories_index.
        Uses a generic query to get maximum coverage.
        """
        query    = "knowledge notes study information learning"
        q_vec    = self.embedder.embed(query)
        matches  = self.endee.search(
            MEMORIES_INDEX,
            vector=q_vec,
            top_k=top_k,
        )
        return matches

    # ── Pattern Detection ────────────────────────────────────────────────

    def detect_patterns(self, chunks: list[dict]) -> list[AgentInsight]:
        """
        Detect what topics appear most frequently in your memory.
        Uses Endee to find topic clusters.
        """
        llm = self._get_llm()
        if not llm or not chunks:
            return []

        # Sample content from chunks
        sample = "\n".join([
            f"- {c.get('metadata', {}).get('content', '')[:100]}"
            for c in chunks[:20]
        ])

        prompt = f"""Analyse these document excerpts and identify 2-3 recurring topics or patterns.
For each pattern write ONE sentence.

Excerpts:
{sample}

Return only a numbered list like:
1. Pattern description here
2. Pattern description here"""

        try:
            resp = llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            raw      = resp.choices[0].message.content.strip()
            lines    = [l.strip() for l in raw.split("\n") if l.strip() and l[0].isdigit()]
            insights = []

            for line in lines[:3]:
                # Remove leading number
                desc = line.split(".", 1)[-1].strip()
                insight = AgentInsight(
                    insight_type=InsightType.PATTERN,
                    title="Recurring topic detected",
                    description=desc,
                    confidence=0.75,
                    evidence=[c["id"] for c in chunks[:5]],
                )
                insights.append(insight)
                self.recommender.store_insight(insight)

            logger.info(f"Detected {len(insights)} patterns")
            return insights

        except Exception as exc:
            logger.error(f"Pattern detection failed: {exc}")
            return []

    # ── Contradiction Detection ──────────────────────────────────────────

    def detect_contradictions(self, chunks: list[dict]) -> list[AgentInsight]:
        """
        Find chunks where the user stated conflicting things.
        Searches Endee for semantically similar chunks and
        asks LLM to check if they contradict each other.
        """
        llm = self._get_llm()
        if not llm or len(chunks) < 2:
            return []

        insights = []

        # Compare first chunk against others
        for i in range(min(3, len(chunks))):
            content_a = chunks[i].get("metadata", {}).get("content", "")[:200]
            content_b = chunks[i + 1].get("metadata", {}).get("content", "")[:200] if i + 1 < len(chunks) else ""

            if not content_a or not content_b:
                continue

            prompt = f"""Do these two excerpts contradict each other?
Answer with YES or NO followed by one sentence explanation.

Excerpt 1: {content_a}

Excerpt 2: {content_b}"""

            try:
                resp = llm.chat.completions.create(
                    model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=100,
                )
                answer = resp.choices[0].message.content.strip()

                if answer.upper().startswith("YES"):
                    insight = AgentInsight(
                        insight_type=InsightType.CONTRADICTION,
                        title="Conflicting statements found",
                        description=answer.split("\n")[0].replace("YES", "").strip(". "),
                        confidence=0.70,
                        action_needed=True,
                        evidence=[chunks[i]["id"], chunks[i+1]["id"]],
                    )
                    insights.append(insight)
                    self.recommender.store_insight(insight)

            except Exception as exc:
                logger.warning(f"Contradiction check failed: {exc}")

        logger.info(f"Found {len(insights)} contradictions")
        return insights

    # ── Knowledge Gap Detection ──────────────────────────────────────────

    def detect_knowledge_gaps(self, chunks: list[dict]) -> list[AgentInsight]:
        """
        Identify topics that are mentioned but not deeply covered.
        Uses LLM to spot surface-level mentions without deep notes.
        """
        llm = self._get_llm()
        if not llm or not chunks:
            return []

        sample = "\n".join([
            f"- {c.get('metadata', {}).get('content', '')[:80]}"
            for c in chunks[:15]
        ])

        prompt = f"""Based on these study notes, what important related topics
are mentioned briefly but NOT covered in depth?
List 2-3 knowledge gaps in one sentence each.

Notes:
{sample}

Return only a numbered list:
1. Gap description
2. Gap description"""

        try:
            resp = llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150,
            )
            raw      = resp.choices[0].message.content.strip()
            lines    = [l.strip() for l in raw.split("\n") if l.strip() and l[0].isdigit()]
            insights = []

            for line in lines[:3]:
                desc    = line.split(".", 1)[-1].strip()
                insight = AgentInsight(
                    insight_type=InsightType.KNOWLEDGE_GAP,
                    title="Knowledge gap detected",
                    description=desc,
                    confidence=0.65,
                    action_needed=True,
                    evidence=[c["id"] for c in chunks[:3]],
                )
                insights.append(insight)
                self.recommender.store_insight(insight)

            logger.info(f"Found {len(insights)} knowledge gaps")
            return insights

        except Exception as exc:
            logger.error(f"Gap detection failed: {exc}")
            return []

    # ── Generate Summary ─────────────────────────────────────────────────

    def _generate_summary(self, report: AgentRunReport) -> str:
        llm = self._get_llm()
        if not llm:
            return (
                f"Agent completed. Found {report.patterns_found} patterns, "
                f"{report.contradictions_found} contradictions, "
                f"{report.gaps_found} knowledge gaps, "
                f"{report.forgotten_found} forgotten memories."
            )

        prompt = (
            f"Summarise this knowledge analysis in 2 sentences:\n"
            f"Patterns found: {report.patterns_found}\n"
            f"Contradictions: {report.contradictions_found}\n"
            f"Knowledge gaps: {report.gaps_found}\n"
            f"Forgotten memories: {report.forgotten_found}\n"
            f"Total insights stored in Endee: {report.insights_stored}"
        )

        try:
            resp = llm.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return f"Agent run {report.run_id} complete."

    # ── Main Run ─────────────────────────────────────────────────────────

    def run(self) -> AgentRunReport:
        """
        Execute one full agent monitoring cycle.

        Steps:
          1. Fetch sample chunks from Endee
          2. Detect patterns
          3. Detect contradictions
          4. Detect knowledge gaps
          5. Find forgotten memories
          6. Store all insights back into Endee
          7. Generate summary

        Returns AgentRunReport with full stats.
        """
        t0     = time.time()
        report = AgentRunReport()
        logger.info(f"Agent run {report.run_id} starting...")

        # Fetch chunks from Endee
        chunks = self._fetch_sample_chunks(top_k=50)
        if not chunks:
            report.summary = "No documents found. Please upload files first."
            return report

        logger.info(f"Fetched {len(chunks)} chunks from Endee")

        # Run all detectors
        patterns      = self.detect_patterns(chunks)
        contradictions = self.detect_contradictions(chunks)
        gaps          = self.detect_knowledge_gaps(chunks)
        forgotten     = self.recommender.find_forgotten(days=30, top_k=3)

        # Update report
        report.patterns_found      = len(patterns)
        report.contradictions_found = len(contradictions)
        report.gaps_found          = len(gaps)
        report.forgotten_found     = len(forgotten)
        report.insights_stored     = len(patterns) + len(contradictions) + len(gaps)
        report.duration_seconds    = round(time.time() - t0, 2)
        report.summary             = self._generate_summary(report)

        logger.success(
            f"Agent run {report.run_id} done in {report.duration_seconds}s — "
            f"{report.insights_stored} insights stored in Endee"
        )
        return report