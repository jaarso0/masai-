"""ChromaDB-backed memory store for architectural decisions."""

import os
import uuid
from datetime import datetime, timezone

import chromadb
from dotenv import load_dotenv

load_dotenv()

# Persistent ChromaDB client — saves to .masai_memory/ on disk
# Uses ChromaDB's default embedding function (no external API needed)
_chroma_client = chromadb.PersistentClient(path=".masai_memory")

_collection = _chroma_client.get_or_create_collection(
    name="masai_decisions",
)


def save_decision(agent_name: str, decision: str) -> None:
    """Save an architectural decision to ChromaDB with metadata."""
    _collection.add(
        ids=[str(uuid.uuid4())],
        documents=[decision],
        metadatas=[
            {
                "agent": agent_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )


def search_decisions(query: str, n_results: int = 3) -> str:
    """
    Search ChromaDB for relevant past decisions.
    Return them as a formatted string ready to inject into a prompt.
    Return empty string if nothing relevant found.
    """
    if _collection.count() == 0:
        return ""

    results = _collection.query(query_texts=[query], n_results=n_results)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not documents:
        return ""

    lines: list[str] = ["Relevant past decisions:"]
    for doc, meta in zip(documents, metadatas):
        agent = meta.get("agent", "unknown")
        lines.append(f"- [{agent}] {doc}")

    return "\n".join(lines)


def list_all_decisions() -> list[dict]:
    """
    Return all stored decisions grouped by agent name.
    Each dict has keys: agent, decision, timestamp.
    """
    if _collection.count() == 0:
        return []

    all_data = _collection.get(include=["documents", "metadatas"])

    decisions: list[dict] = []
    documents = all_data.get("documents", [])
    metadatas = all_data.get("metadatas", [])

    for doc, meta in zip(documents, metadatas):
        decisions.append(
            {
                "agent": meta.get("agent", "unknown"),
                "decision": doc,
                "timestamp": meta.get("timestamp", ""),
            }
        )

    decisions.sort(key=lambda d: d["agent"])
    return decisions
