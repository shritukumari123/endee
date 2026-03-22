from __future__ import annotations
import time
import uuid
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FileType(str, Enum):
    PDF      = "pdf"
    TEXT     = "text"
    MARKDOWN = "markdown"
    CSV      = "csv"
    DOCX     = "docx"
    UNKNOWN  = "unknown"


class InsightType(str, Enum):
    PATTERN       = "pattern"
    CONTRADICTION = "contradiction"
    KNOWLEDGE_GAP = "knowledge_gap"
    FORGOTTEN     = "forgotten_memory"
    CONNECTION    = "connection"


class MemoryChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    content: str
    source_file: str
    file_type: FileType
    chunk_index: int = 0
    total_chunks: int = 0
    uploaded_at: float = Field(default_factory=time.time)
    word_count: int = 0
    is_duplicate: bool = False

    @property
    def embed_text(self) -> str:
        return f"[{self.file_type.value}] {self.source_file}: {self.content}"

    def to_endee_doc(self, embedding: list) -> dict:
        return {
            "id": self.id,
            "values": embedding,
            "metadata": {
                "content":      self.content[:150],
                "full_content": self.content[:300],
                "source_file":  self.source_file[:100],
                "file_type":    self.file_type.value,
                "chunk_index":  self.chunk_index,
                "total_chunks": self.total_chunks,
                "uploaded_at":  self.uploaded_at,
                "word_count":   len(self.content.split()),
            },
        }

    @classmethod
    def from_endee_match(cls, match: dict) -> "MemoryChunk":
        meta = match.get("metadata", {})
        return cls(
            id=match.get("id", ""),
            content=meta.get("full_content", meta.get("content", "")),
            source_file=meta.get("source_file", "unknown"),
            file_type=FileType(meta.get("file_type", "unknown")),
            chunk_index=int(meta.get("chunk_index", 0)),
            total_chunks=int(meta.get("total_chunks", 0)),
            uploaded_at=float(meta.get("uploaded_at", 0)),
            word_count=int(meta.get("word_count", 0)),
        )


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:10])
    name: str
    entity_type: str
    context: str
    source_file: str
    chunk_id: str
    extracted_at: float = Field(default_factory=time.time)

    def to_endee_doc(self, embedding: list) -> dict:
        return {
            "id": self.id,
            "values": embedding,
            "metadata": {
                "name":         self.name[:100],
                "entity_type":  self.entity_type[:50],
                "context":      self.context[:150],
                "source_file":  self.source_file[:100],
                "chunk_id":     self.chunk_id[:20],
                "extracted_at": self.extracted_at,
            },
        }


class SearchResult(BaseModel):
    chunk: MemoryChunk
    score: float
    rank: int = 0

    @property
    def source_file(self) -> str:
        return self.chunk.source_file

    @property
    def content(self) -> str:
        return self.chunk.content

    @property
    def snippet(self) -> str:
        return self.chunk.content[:200].strip()


class RAGResponse(BaseModel):
    question: str
    answer: str
    sources: list = Field(default_factory=list)
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    chunk_count: int = 0


class AgentInsight(BaseModel):
    id: str = Field(default_factory=lambda: f"ins_{uuid.uuid4().hex[:8]}")
    insight_type: InsightType
    title: str
    description: str
    evidence: list = Field(default_factory=list)
    confidence: float = 0.5
    action_needed: bool = False
    created_at: float = Field(default_factory=time.time)

    def to_endee_doc(self, embedding: list) -> dict:
        return {
            "id": self.id,
            "values": embedding,
            "metadata": {
                "insight_type": self.insight_type.value,
                "title":        self.title[:100],
                "description":  self.description[:200],
                "confidence":   self.confidence,
                "action_needed": str(self.action_needed),
                "created_at":   self.created_at,
            },
        }


class UploadResponse(BaseModel):
    filename: str
    file_type: str
    chunks_created: int
    duplicates_skipped: int
    entities_extracted: int
    processing_time_ms: float


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    file_type: Optional[str] = None
    source_file: Optional[str] = None
    since_days: Optional[int] = None
    include_rag_answer: bool = True