"""Neo4j client using the official Bolt driver."""

import logging

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thin wrapper around the neo4j Python driver."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a Cypher query and return a list of record dicts."""
        with self.driver.session(database="neo4j") as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]

    def batch_merge(self, cypher: str, rows: list[dict], batch_key: str = "rows"):
        """UNWIND batch pattern for bulk MERGE operations.

        The *cypher* string should reference ``row`` (singular) — for example::

            MERGE (d:Deployment {name: row.name, namespace: row.namespace})
            SET d.replicas = row.replicas
        """
        if not rows:
            return
        with self.driver.session(database="neo4j") as session:
            session.run(
                f"UNWIND ${batch_key} AS row {cypher}",
                {batch_key: rows},
            )

    def write(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a write transaction and return results."""
        with self.driver.session(database="neo4j") as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]

    def verify(self) -> bool:
        """Return True if the database is reachable."""
        try:
            self.query("RETURN 1 AS ok")
            return True
        except Exception:
            return False

    def close(self):
        self.driver.close()
