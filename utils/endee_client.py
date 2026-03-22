from __future__ import annotations
import os
from loguru import logger
from dotenv import load_dotenv
load_dotenv()


class EndeeClient:

    def __init__(self, base_url=None, auth_token=None, timeout=30.0):
        from endee import Endee
        token = auth_token or os.getenv("ENDEE_AUTH_TOKEN", "")
        if token:
            self._client = Endee(token)
        else:
            self._client = Endee()
        self.base_url = base_url or os.getenv("ENDEE_BASE_URL", "http://localhost:8080")
        logger.info(f"EndeeClient ready → {self.base_url}")

    def _get_indexes_list(self) -> list:
        """
        Endee SDK returns either a dict {"indexes": [...]} or a list.
        This helper always returns the list.
        """
        raw = self._client.list_indexes()
        if isinstance(raw, dict):
            return raw.get("indexes", [])
        elif isinstance(raw, list):
            return raw
        return []

    def health(self) -> dict:
        try:
            self._get_indexes_list()
            return {"status": "ok"}
        except Exception as e:
            raise Exception(f"Health check failed: {e}")

    def wait_until_ready(self, retries=12, delay=3.0) -> bool:
        import time
        for i in range(1, retries + 1):
            try:
                self.health()
                logger.success("Endee is healthy ✓")
                return True
            except Exception as e:
                logger.warning(f"Endee not ready ({i}/{retries}): {e}")
                time.sleep(delay)
        raise RuntimeError("Endee not reachable.")

    def list_indexes(self) -> list:
        """Return list of index names as strings."""
        indexes = self._get_indexes_list()
        names = []
        for idx in indexes:
            if isinstance(idx, dict):
                names.append(idx.get("name", ""))
            else:
                names.append(str(idx))
        return names

    def create_index(self, name, dim=384, metric="cosine", overwrite=False):
        from endee import Precision
        existing = self.list_indexes()

        if overwrite and name in existing:
            self.delete_index(name)
            existing = []

        if name in existing:
            logger.debug(f"Index '{name}' already exists.")
            return {"status": "exists"}

        try:
            self._client.create_index(
                name=name,
                dimension=dim,
                space_type=metric,
                precision=Precision.INT8,
            )
            logger.success(f"Created index '{name}' (dim={dim})")
            return {"status": "created"}
        except Exception as e:
            if "already exists" in str(e).lower() or "conflict" in str(e).lower():
                logger.debug(f"Index '{name}' already exists — skipping.")
                return {"status": "exists"}
            raise

    def delete_index(self, name):
        self._client.delete_index(name=name)
        logger.warning(f"Deleted index '{name}'")
        return {"status": "deleted"}

    def index_stats(self, name):
        try:
            all_indexes = self._get_indexes_list()
            for idx in all_indexes:
                if isinstance(idx, dict):
                    idx_name  = idx.get("name", "")
                    idx_count = idx.get("total_elements", 0)
                else:
                    idx_name  = str(idx)
                    idx_count = 0
                if idx_name == name:
                    return {
                        "index_name":   name,
                        "vector_count": idx_count,
                    }
            return {"index_name": name, "vector_count": 0}
        except Exception:
            return {"error": "unavailable"}

    def upsert(self, index_name, vectors, batch_size=128):
        index = self._client.get_index(name=index_name)

        endee_vectors = []
        for v in vectors:
            meta = v.get("metadata", {})
            safe_meta = {}
            for k, val in meta.items():
                if isinstance(val, str):
                    safe_meta[k] = val[:200]
                else:
                    safe_meta[k] = val

            endee_vectors.append({
                "id":     v["id"],
                "vector": v["values"],
                "meta":   safe_meta,
            })

        for i in range(0, len(endee_vectors), batch_size):
            batch = endee_vectors[i:i + batch_size]
            try:
                index.upsert(batch)
                logger.debug(f"Upserted batch of {len(batch)} vectors → '{index_name}'")
            except Exception as e:
                logger.error(f"Upsert batch failed: {e}")
                raise

        logger.debug(f"Upserted {len(vectors)} vectors → '{index_name}'")
        return {"upserted": len(vectors)}

    def search(self, index_name, vector, top_k=10, filters=None, include_metadata=True):
        index   = self._client.get_index(name=index_name)
        results = index.query(vector=vector, top_k=top_k)

        # results could be dict or list
        if isinstance(results, dict):
            results = results.get("results", results.get("matches", []))

        matches = []
        for r in results:
            matches.append({
                "id":       r.get("id", ""),
                "score":    r.get("similarity", r.get("score", 0.0)),
                "metadata": r.get("meta", r.get("metadata", {})),
            })
        return matches

    def fetch(self, index_name, ids):
        index   = self._client.get_index(name=index_name)
        results = []
        for id_ in ids:
            try:
                item = index.fetch(id_)
                if item:
                    results.append({
                        "id":       id_,
                        "values":   item.get("vector", []),
                        "metadata": item.get("meta", {}),
                    })
            except Exception:
                pass
        return results

    def delete_vectors(self, index_name, ids):
        index = self._client.get_index(name=index_name)
        for id_ in ids:
            try:
                index.delete(id_)
            except Exception:
                pass
        return {"deleted": len(ids)}

    def index_exists(self, name):
        return name in self.list_indexes()