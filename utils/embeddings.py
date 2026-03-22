from __future__ import annotations
import os
from functools import lru_cache
import numpy as np
from dotenv import load_dotenv
from loguru import logger
load_dotenv()


class LocalEmbedder:

    def __init__(self, model_name=None):
        self.model_name = (
            model_name or os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        )
        self._model = None
        self.dim = 384

    def _load(self):
        if self._model is None:
            logger.info(f"Loading embedding model '{self.model_name}' ...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self.dim = self._model.get_sentence_embedding_dimension()
            logger.success(f"Embedding model ready — dim={self.dim}")

    def embed(self, text: str) -> list:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list, batch_size=64, show_progress=False) -> list:
        self._load()
        all_vecs = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            vecs = self._model.encode(
                chunk,
                normalize_embeddings=True,
                show_progress_bar=show_progress and len(texts) > 100,
                convert_to_numpy=True,
            )
            all_vecs.extend(vecs.tolist())
        return all_vecs

    def cosine_similarity(self, a: list, b: list) -> float:
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if denom < 1e-10:
            return 0.0
        return float(np.dot(va, vb) / denom)

    def most_similar(self, query: str, candidates: list, top_k=5) -> list:
        q_vec = np.array(self.embed(query))
        c_vecs = np.array(self.embed_batch(candidates))
        scores = c_vecs @ q_vec
        ranked = sorted(
            zip(candidates, scores.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]


@lru_cache(maxsize=1)
def get_embedder() -> LocalEmbedder:
    return LocalEmbedder()