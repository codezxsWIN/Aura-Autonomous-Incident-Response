from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from app.adapters import Neo4jTopologyStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed the Aura demo microservice and active-session graph."
    )
    parser.add_argument(
        "--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    )
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument(
        "--password",
        default=os.getenv("NEO4J_PASSWORD", "aura-demo-password"),
    )
    args = parser.parse_args()

    store = Neo4jTopologyStore(args.uri, args.user, args.password)
    if not store.available:
        print(f"Unable to connect to Neo4j at {args.uri}.", file=sys.stderr)
        return 1
    try:
        store.seed()
        print(
            "Seeded 7 service nodes, 6 dependency edges, and 5 active sessions "
            f"into {args.uri}."
        )
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())