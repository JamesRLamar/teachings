"""SQLite schema and helpers for teachings search."""

from __future__ import annotations

import sqlite3
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PACKAGE_DIR / "data" / "teachings.db"


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT,
    date TEXT,
    series TEXT,
    content_hash TEXT NOT NULL,
    mtime REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (document_id, tag)
);

CREATE TABLE IF NOT EXISTS document_scriptures (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    reference TEXT NOT NULL,
    PRIMARY KEY (document_id, reference)
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    heading TEXT,
    text TEXT NOT NULL,
    start_line INTEGER NOT NULL DEFAULT 1,
    embedding BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_series ON documents(series);
CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(date);
CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag);
CREATE INDEX IF NOT EXISTS idx_document_scriptures_ref ON document_scriptures(reference);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
"""


def ensure_data_dir(db_path: Path = DEFAULT_DB_PATH) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    ensure_data_dir(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def wipe_all(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM chunks;
        DELETE FROM document_tags;
        DELETE FROM document_scriptures;
        DELETE FROM documents;
        """
    )
    # Rebuild FTS index empty
    try:
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def get_document_hash(conn: sqlite3.Connection, path: str) -> str | None:
    row = conn.execute(
        "SELECT content_hash FROM documents WHERE path = ?", (path,)
    ).fetchone()
    return row["content_hash"] if row else None


def delete_document_by_path(conn: sqlite3.Connection, path: str) -> None:
    conn.execute("DELETE FROM documents WHERE path = ?", (path,))


def upsert_document(
    conn: sqlite3.Connection,
    *,
    path: str,
    title: str | None,
    date: str | None,
    series: str | None,
    content_hash: str,
    mtime: float,
    tags: list[str],
    scriptures: list[str],
) -> int:
    delete_document_by_path(conn, path)
    cur = conn.execute(
        """
        INSERT INTO documents (path, title, date, series, content_hash, mtime)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (path, title, date, series, content_hash, mtime),
    )
    doc_id = int(cur.lastrowid)
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag) VALUES (?, ?)",
            (doc_id, tag),
        )
    for ref in scriptures:
        conn.execute(
            "INSERT OR IGNORE INTO document_scriptures (document_id, reference) VALUES (?, ?)",
            (doc_id, ref),
        )
    return doc_id


def insert_chunk(
    conn: sqlite3.Connection,
    *,
    document_id: int,
    heading: str,
    text: str,
    start_line: int,
    embedding: bytes,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO chunks (document_id, heading, text, start_line, embedding)
        VALUES (?, ?, ?, ?, ?)
        """,
        (document_id, heading, text, start_line, embedding),
    )
    return int(cur.lastrowid)


def list_indexed_paths(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT path FROM documents").fetchall()
    return {row["path"] for row in rows}
