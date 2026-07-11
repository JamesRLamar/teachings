"""CLI: python -m search index|query ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .db import DEFAULT_DB_PATH
from .index import REPO_ROOT, index_corpus
from .query import format_hits, search


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m search",
        description="Local MiniLM + SQLite semantic search for teachings",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite path (default: {DEFAULT_DB_PATH})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    index_p = sub.add_parser("index", help="Index or refresh the corpus")
    index_p.add_argument(
        "--rebuild",
        action="store_true",
        help="Wipe and rebuild the entire index",
    )
    index_p.add_argument(
        "--repo",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to scan",
    )

    query_p = sub.add_parser("query", help="Semantic search")
    query_p.add_argument("text", help="Search query")
    query_p.add_argument("--top", type=int, default=8, help="Number of results")
    query_p.add_argument("--series", type=str, default=None, help="Filter by series")
    query_p.add_argument("--tag", type=str, default=None, help="Filter by tag")
    query_p.add_argument(
        "--scripture", type=str, default=None, help="Filter by scripture reference"
    )
    query_p.add_argument("--date", type=str, default=None, help="Filter by date YYYY-MM-DD")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "index":
        stats = index_corpus(
            repo_root=args.repo.resolve(),
            db_path=args.db,
            rebuild=args.rebuild,
        )
        print(
            "Indexed: "
            f"scanned={stats['scanned']} "
            f"updated={stats['updated']} "
            f"skipped={stats['skipped']} "
            f"removed={stats['removed']} "
            f"chunks={stats['chunks']}"
        )
        print(f"DB: {args.db}")
        return 0

    if args.command == "query":
        if not Path(args.db).exists():
            print(
                f"No index at {args.db}. Run: python -m search index",
                file=sys.stderr,
            )
            return 1
        hits = search(
            args.text,
            db_path=args.db,
            top_k=args.top,
            series=args.series,
            tag=args.tag,
            scripture=args.scripture,
            date=args.date,
        )
        print(format_hits(hits))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
