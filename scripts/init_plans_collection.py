#!/usr/bin/env python3
"""
Initialize Qdrant collections for the planning-agent skill.

Collections created:
- plans: Store generated plans with metadata
- external_research: Cache external research with TTL
- profiles: Index profile definitions for semantic matching

Usage:
    python init_plans_collection.py

Requires:
    - QDRANT_URL environment variable (default: http://qdrant.ai-platform.svc:6333)
    - qdrant-client package
"""

import os
import sys
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        PayloadSchemaType,
    )
except ImportError:
    print("Error: qdrant-client not installed")
    print("Install with: pip install qdrant-client")
    sys.exit(1)

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant.ai-platform.svc:6333")
VECTOR_SIZE = 768  # Gemini text-embedding-004 dimensions


def init_collections(client: QdrantClient):
    """Initialize all planning-agent collections."""

    collections = {
        "plans": {
            "description": "Generated plans from planning-agent skill",
            "schema": {
                "id": PayloadSchemaType.KEYWORD,
                "title": PayloadSchemaType.TEXT,
                "profiles_used": PayloadSchemaType.KEYWORD,
                "domain": PayloadSchemaType.KEYWORD,
                "status": PayloadSchemaType.KEYWORD,
                "outcome": PayloadSchemaType.KEYWORD,
                "created_at": PayloadSchemaType.DATETIME,
                "executed_at": PayloadSchemaType.DATETIME,
                "git_path": PayloadSchemaType.KEYWORD,
            }
        },
        "external_research": {
            "description": "Cached external research with TTL",
            "schema": {
                "query": PayloadSchemaType.KEYWORD,
                "source": PayloadSchemaType.KEYWORD,
                "content": PayloadSchemaType.TEXT,
                "fetched_at": PayloadSchemaType.DATETIME,
                "credibility_score": PayloadSchemaType.FLOAT,
                "ttl_days": PayloadSchemaType.INTEGER,
            }
        },
        "profiles": {
            "description": "Profile definitions for semantic matching",
            "schema": {
                "id": PayloadSchemaType.KEYWORD,
                "name": PayloadSchemaType.KEYWORD,
                "category": PayloadSchemaType.KEYWORD,
                "domains": PayloadSchemaType.KEYWORD,
                "mcps": PayloadSchemaType.KEYWORD,
                "description": PayloadSchemaType.TEXT,
            }
        }
    }

    for name, config in collections.items():
        # Check if collection exists
        existing = client.get_collections().collections
        exists = any(c.name == name for c in existing)

        if exists:
            print(f"Collection '{name}' already exists, skipping creation")
        else:
            print(f"Creating collection '{name}'...")
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            print(f"  Created with {VECTOR_SIZE}-dim vectors (cosine)")

        # Create payload indexes for efficient filtering
        print(f"  Setting up payload indexes for '{name}'...")
        for field_name, field_type in config["schema"].items():
            try:
                client.create_payload_index(
                    collection_name=name,
                    field_name=field_name,
                    field_schema=field_type,
                )
            except Exception as e:
                # Index might already exist
                if "already exists" not in str(e).lower():
                    print(f"    Warning: Could not create index for {field_name}: {e}")

        print(f"  Collection '{name}' ready")

    print("\nAll collections initialized successfully!")


def verify_collections(client: QdrantClient):
    """Verify all collections exist and are accessible."""
    required = ["plans", "external_research", "profiles"]

    existing = [c.name for c in client.get_collections().collections]

    print("\nVerifying collections:")
    all_ok = True
    for name in required:
        if name in existing:
            info = client.get_collection(name)
            print(f"  {name}: OK ({info.points_count} points)")
        else:
            print(f"  {name}: MISSING")
            all_ok = False

    return all_ok


def main():
    print(f"Connecting to Qdrant at {QDRANT_URL}...")

    try:
        client = QdrantClient(url=QDRANT_URL)
        # Test connection
        client.get_collections()
        print("Connected successfully!\n")
    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")
        sys.exit(1)

    init_collections(client)

    if verify_collections(client):
        print("\nSetup complete! Planning-agent collections are ready.")
    else:
        print("\nWarning: Some collections are missing. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
