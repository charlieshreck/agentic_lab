#!/usr/bin/env python3
"""
Index knowledge base documentation into Qdrant.

Reads markdown files from docs/knowledge-base/ and runbooks/
and indexes them into Qdrant via LiteLLM embeddings.

Usage:
    python scripts/index-knowledge-base.py

Environment:
    QDRANT_URL: Qdrant URL (default: http://10.20.0.40:30633)
    LITELLM_URL: LiteLLM URL (default: http://10.20.0.40:30400)
"""

import os
import sys
import json
import uuid
import httpx
from pathlib import Path
from datetime import datetime, timezone

# Configuration
QDRANT_URL = os.environ.get("QDRANT_URL", "http://10.20.0.40:30633")
LITELLM_URL = os.environ.get("LITELLM_URL", "http://10.20.0.40:30400")
EMBEDDING_MODEL = "embeddings"

# Paths
REPO_ROOT = Path("/home/agentic_lab")
DOCS_PATH = REPO_ROOT / "docs" / "knowledge-base"
RUNBOOKS_PATH = REPO_ROOT / "runbooks"


def get_embedding(text: str) -> list[float]:
    """Get embedding vector via LiteLLM."""
    response = httpx.post(
        f"{LITELLM_URL}/v1/embeddings",
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=60.0
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def upsert_points(collection: str, points: list[dict]) -> bool:
    """Upsert points to Qdrant collection."""
    response = httpx.put(
        f"{QDRANT_URL}/collections/{collection}/points",
        json={"points": points},
        timeout=30.0
    )
    return response.status_code == 200


def read_markdown(file_path: Path) -> dict:
    """Read markdown file and extract metadata."""
    content = file_path.read_text()

    # Extract title from first H1
    lines = content.split("\n")
    title = file_path.stem
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Extract tags if present
    tags = []
    for line in lines:
        if line.lower().startswith("tags for indexing"):
            # Next line or inline tags
            tag_line = line.split(":")[-1] if ":" in line else ""
            tags = [t.strip().strip("`") for t in tag_line.split(",") if t.strip()]
            break

    return {
        "title": title,
        "content": content,
        "path": str(file_path.relative_to(REPO_ROOT)),
        "tags": tags,
        "indexed_at": datetime.now(timezone.utc).isoformat()
    }


def index_documentation():
    """Index documentation files into Qdrant."""
    print(f"Indexing documentation from {DOCS_PATH}")

    if not DOCS_PATH.exists():
        print(f"  Directory not found: {DOCS_PATH}")
        return 0

    points = []
    for md_file in DOCS_PATH.glob("*.md"):
        print(f"  Processing: {md_file.name}")
        try:
            doc = read_markdown(md_file)

            # Create embedding from title + content summary
            embed_text = f"{doc['title']}\n\n{doc['content'][:2000]}"
            vector = get_embedding(embed_text)

            point = {
                "id": str(uuid.uuid4()),
                "vector": vector,
                "payload": doc
            }
            points.append(point)
            print(f"    ✓ Embedded: {doc['title']}")
        except Exception as e:
            print(f"    ✗ Error: {e}")

    if points:
        print(f"\n  Upserting {len(points)} documents to 'documentation' collection...")
        if upsert_points("documentation", points):
            print("    ✓ Success")
            return len(points)
        else:
            print("    ✗ Failed to upsert")

    return 0


def index_runbooks():
    """Index runbook files into Qdrant."""
    print(f"\nIndexing runbooks from {RUNBOOKS_PATH}")

    if not RUNBOOKS_PATH.exists():
        print(f"  Directory not found: {RUNBOOKS_PATH}")
        return 0

    points = []
    for md_file in RUNBOOKS_PATH.rglob("*.md"):
        print(f"  Processing: {md_file.relative_to(RUNBOOKS_PATH)}")
        try:
            doc = read_markdown(md_file)

            # Runbooks use 'solution' field for content
            embed_text = f"{doc['title']}\n\n{doc['content'][:2000]}"
            vector = get_embedding(embed_text)

            # Extract trigger pattern from overview section
            trigger_pattern = doc['title']

            point = {
                "id": str(uuid.uuid4()),
                "vector": vector,
                "payload": {
                    "title": doc['title'],
                    "trigger_pattern": trigger_pattern,
                    "solution": doc['content'],
                    "path": doc['path'],
                    "created_at": doc['indexed_at']
                }
            }
            points.append(point)
            print(f"    ✓ Embedded: {doc['title']}")
        except Exception as e:
            print(f"    ✗ Error: {e}")

    if points:
        print(f"\n  Upserting {len(points)} runbooks to 'runbooks' collection...")
        if upsert_points("runbooks", points):
            print("    ✓ Success")
            return len(points)
        else:
            print("    ✗ Failed to upsert")

    return 0


def verify_connectivity():
    """Verify Qdrant and LiteLLM are accessible."""
    print("Verifying connectivity...")

    # Check Qdrant
    try:
        response = httpx.get(f"{QDRANT_URL}/collections", timeout=10.0)
        response.raise_for_status()
        print(f"  ✓ Qdrant: {QDRANT_URL}")
    except Exception as e:
        print(f"  ✗ Qdrant: {e}")
        return False

    # Check LiteLLM
    try:
        response = httpx.get(f"{LITELLM_URL}/health", timeout=10.0)
        print(f"  ✓ LiteLLM: {LITELLM_URL}")
    except Exception as e:
        print(f"  ✗ LiteLLM: {e}")
        return False

    return True


def main():
    print("=" * 60)
    print("Knowledge Base Indexer")
    print("=" * 60)

    if not verify_connectivity():
        print("\nConnectivity check failed. Exiting.")
        sys.exit(1)

    print()
    docs_count = index_documentation()
    runbooks_count = index_runbooks()

    print("\n" + "=" * 60)
    print(f"Indexing complete:")
    print(f"  Documentation: {docs_count} files")
    print(f"  Runbooks: {runbooks_count} files")
    print("=" * 60)


if __name__ == "__main__":
    main()
