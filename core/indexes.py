from __future__ import annotations
import os
from dotenv import load_dotenv
from loguru import logger
from utils.endee_client import EndeeClient
from utils.embeddings import get_embedder
load_dotenv()

MEMORIES_INDEX = os.getenv("MEMORIES_INDEX", "engram_memories")
ENTITIES_INDEX = os.getenv("ENTITIES_INDEX", "engram_entities")
INSIGHTS_INDEX = os.getenv("INSIGHTS_INDEX", "engram_insights")
TIMELINE_INDEX = os.getenv("TIMELINE_INDEX", "engram_timeline")

ALL_INDEXES = [MEMORIES_INDEX, ENTITIES_INDEX, INSIGHTS_INDEX, TIMELINE_INDEX]


def initialise_indexes(overwrite: bool = False) -> dict:
    client   = EndeeClient()
    embedder = get_embedder()
    dim      = embedder.dim

    client.wait_until_ready()

    configs = [
        (MEMORIES_INDEX, "document chunk embeddings"),
        (ENTITIES_INDEX, "named entity embeddings"),
        (INSIGHTS_INDEX, "agent insight embeddings"),
        (TIMELINE_INDEX, "time-tagged memory embeddings"),
    ]

    results = {}
    for name, purpose in configs:
        try:
            result = client.create_index(
                name=name,
                dim=dim,
                metric="cosine",
                overwrite=overwrite,
            )
            status = result.get("status", "created")
            results[name] = status
            logger.info(f"  [{status.upper():8s}] {name} — {purpose} (dim={dim})")
        except Exception as exc:
            # If index already exists just skip — not a real error
            if "already exists" in str(exc).lower() or "conflict" in str(exc).lower():
                results[name] = "exists"
                logger.info(f"  [EXISTS  ] {name} — already exists, skipping")
            else:
                logger.error(f"  [ERROR   ] Failed to create '{name}': {exc}")
                results[name] = "error"

    ok = sum(1 for s in results.values() if s != "error")
    logger.success(f"Indexes ready: {ok}/{len(configs)}")
    return results


def get_index_stats() -> dict:
    client = EndeeClient()
    stats  = {}
    for name in ALL_INDEXES:
        try:
            stats[name] = client.index_stats(name)
        except Exception:
            stats[name] = {"error": "unavailable"}
    return stats


def reset_all_indexes() -> None:
    logger.warning("RESETTING ALL ENGRAM INDEXES — all data will be lost!")
    initialise_indexes(overwrite=True)
    logger.success("All indexes reset.")


if __name__ == "__main__":
    print("Initialising Engram indexes...")
    results = initialise_indexes()
    for name, status in results.items():
        print(f"  {name}: {status}")