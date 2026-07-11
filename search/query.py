"""Semantic (+ metadata) query over indexed teachings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .db import DEFAULT_DB_PATH, connect, init_db
from .embed import blob_to_embedding, encode_query

FTS_BOOST = 0.08
SNIPPET_CHARS = 220


@dataclass
class SearchHit:
    path: str
    title: str | None
    series: str | None
    heading: str | None
    score: float
    start_line: int
    snippet: str


def _snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _fts_matching_ids(conn, query: str) -> set[int]:
    # Escape FTS5 special chars by wrapping tokens loosely; fall back on failure.
    try:
        rows = conn.execute(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?",
            (query,),
        ).fetchall()
        return {int(r["rowid"]) for r in rows}
    except Exception:
        # Retry with quoted phrase if the query has operators
        safe = '"' + query.replace('"', " ") + '"'
        try:
            rows = conn.execute(
                "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?",
                (safe,),
            ).fetchall()
            return {int(r["rowid"]) for r in rows}
        except Exception:
            return set()


def search(
    query: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
    top_k: int = 8,
    series: str | None = None,
    tag: str | None = None,
    scripture: str | None = None,
    date: str | None = None,
) -> list[SearchHit]:
    if not query.strip():
        return []

    conn = connect(db_path)
    init_db(conn)

    sql = """
        SELECT
            c.id AS chunk_id,
            c.heading,
            c.text,
            c.start_line,
            c.embedding,
            d.path,
            d.title,
            d.series
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE 1=1
    """
    params: list[object] = []

    if series:
        sql += " AND d.series LIKE ?"
        params.append(f"%{series}%")
    if date:
        sql += " AND d.date = ?"
        params.append(date)
    if tag:
        sql += """
            AND EXISTS (
                SELECT 1 FROM document_tags t
                WHERE t.document_id = d.id AND t.tag LIKE ?
            )
        """
        params.append(f"%{tag}%")
    if scripture:
        sql += """
            AND EXISTS (
                SELECT 1 FROM document_scriptures s
                WHERE s.document_id = d.id AND s.reference LIKE ?
            )
        """
        params.append(f"%{scripture}%")

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        conn.close()
        return []

    q_vec = encode_query(query)
    embeddings = np.vstack([blob_to_embedding(row["embedding"]) for row in rows])
    # Vectors are L2-normalized → cosine == dot product
    scores = embeddings @ q_vec

    fts_ids = _fts_matching_ids(conn, query)
    conn.close()

    ranked: list[tuple[float, int]] = []
    for i, row in enumerate(rows):
        score = float(scores[i])
        if int(row["chunk_id"]) in fts_ids:
            score += FTS_BOOST
        ranked.append((score, i))

    ranked.sort(key=lambda x: x[0], reverse=True)

    hits: list[SearchHit] = []
    for score, i in ranked[:top_k]:
        row = rows[i]
        hits.append(
            SearchHit(
                path=row["path"],
                title=row["title"],
                series=row["series"],
                heading=row["heading"],
                score=score,
                start_line=int(row["start_line"]),
                snippet=_snippet(row["text"]),
            )
        )
    return hits


def format_hits(hits: list[SearchHit]) -> str:
    if not hits:
        return "No matches."
    lines: list[str] = []
    for i, hit in enumerate(hits, 1):
        title = hit.title or "(untitled)"
        heading = f" — {hit.heading}" if hit.heading else ""
        series = f"  series: {hit.series}" if hit.series else ""
        lines.append(
            f"{i}. [{hit.score:.3f}] {hit.path}:{hit.start_line}\n"
            f"   {title}{heading}{series}\n"
            f"   {hit.snippet}"
        )
    return "\n\n".join(lines)
