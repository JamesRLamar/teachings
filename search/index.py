"""Index markdown teachings into SQLite with MiniLM embeddings."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .chunk import chunk_markdown
from .db import (
    DEFAULT_DB_PATH,
    connect,
    get_document_hash,
    init_db,
    insert_chunk,
    list_indexed_paths,
    upsert_document,
    wipe_all,
)
from .embed import embedding_to_blob, encode_texts
from .frontmatter import as_optional_str, as_str_list, parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent


def _iter_source_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    sermons = repo_root / "sermons"
    if sermons.is_dir():
        files.extend(sorted(sermons.glob("*.md")))
    files.extend(sorted(repo_root.glob("*.md")))
    rules = repo_root / ".cursor" / "rules"
    if rules.is_dir():
        files.extend(sorted(rules.glob("*.mdc")))
    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        resolved = path.resolve()
        if resolved not in seen and path.is_file():
            seen.add(resolved)
            unique.append(path)
    return unique


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel_path(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def index_corpus(
    *,
    repo_root: Path = REPO_ROOT,
    db_path: Path = DEFAULT_DB_PATH,
    rebuild: bool = False,
) -> dict[str, int]:
    conn = connect(db_path)
    init_db(conn)

    if rebuild:
        wipe_all(conn)

    files = _iter_source_files(repo_root)
    indexed_paths = list_indexed_paths(conn)
    current_paths: set[str] = set()

    stats = {"scanned": 0, "updated": 0, "skipped": 0, "removed": 0, "chunks": 0}

    pending: list[tuple[str, dict, list, float]] = []
    # Each item: (rel_path, meta, chunks, mtime)

    for path in files:
        stats["scanned"] += 1
        rel = _rel_path(path, repo_root)
        current_paths.add(rel)
        text = path.read_text(encoding="utf-8", errors="replace")
        digest = _content_hash(text)
        if not rebuild and get_document_hash(conn, rel) == digest:
            stats["skipped"] += 1
            continue

        meta, body = parse_frontmatter(text)
        title = as_optional_str(meta.get("title")) or path.stem
        date = as_optional_str(meta.get("date"))
        series = as_optional_str(meta.get("series"))
        tags = as_str_list(meta.get("tags"))
        scriptures = as_str_list(meta.get("scripture"))
        chunks = chunk_markdown(body, default_heading=title)
        if not chunks:
            chunks = chunk_markdown(text, default_heading=title)
        mtime = path.stat().st_mtime
        pending.append(
            (
                rel,
                {
                    "title": title,
                    "date": date,
                    "series": series,
                    "content_hash": digest,
                    "mtime": mtime,
                    "tags": tags,
                    "scriptures": scriptures,
                },
                chunks,
                mtime,
            )
        )

    # Remove deleted files from index
    for stale in indexed_paths - current_paths:
        conn.execute("DELETE FROM documents WHERE path = ?", (stale,))
        stats["removed"] += 1

    if not pending:
        conn.commit()
        conn.close()
        return stats

    # Batch embed all new chunk texts
    all_texts: list[str] = []
    for _, _, chunks, _ in pending:
        for chunk in chunks:
            all_texts.append(chunk.text)

    vectors = encode_texts(all_texts)
    offset = 0
    for rel, meta, chunks, _mtime in pending:
        doc_id = upsert_document(
            conn,
            path=rel,
            title=meta["title"],
            date=meta["date"],
            series=meta["series"],
            content_hash=meta["content_hash"],
            mtime=meta["mtime"],
            tags=meta["tags"],
            scriptures=meta["scriptures"],
        )
        for chunk in chunks:
            vec = vectors[offset]
            offset += 1
            insert_chunk(
                conn,
                document_id=doc_id,
                heading=chunk.heading,
                text=chunk.text,
                start_line=chunk.start_line,
                embedding=embedding_to_blob(vec),
            )
            stats["chunks"] += 1
        stats["updated"] += 1

    conn.commit()
    conn.close()
    return stats
