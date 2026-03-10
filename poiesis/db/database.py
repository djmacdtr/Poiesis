"""Poiesis SQLite 数据库管理模块。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class Database:
    """Manages the SQLite database for Poiesis world state."""

    def __init__(self, db_path: str) -> None:
        """Initialise the database manager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def initialize_schema(self, schema_path: str | None = None) -> None:
        """Run schema.sql to create tables if they do not exist.

        Args:
            schema_path: Path to the SQL schema file. Defaults to the
                bundled schema next to this module.
        """
        if schema_path is None:
            schema_path = str(Path(__file__).parent / "schema.sql")

        with open(schema_path, encoding="utf-8") as fh:
            sql = fh.read()

        conn = self._get_connection()
        conn.executescript(sql)
        self._run_post_schema_migrations(conn)
        conn.commit()

    def _run_post_schema_migrations(self, conn: sqlite3.Connection) -> None:
        """Apply additive migrations for legacy databases."""
        # PRAGMA foreign_keys cannot be toggled inside an active transaction.
        conn.commit()
        self._ensure_default_book(conn)
        self._ensure_column(conn, "characters", "book_id", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(conn, "world_rules", "book_id", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(conn, "foreshadowing", "book_id", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(conn, "timeline", "book_id", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column(
            conn,
            "staging_changes",
            "book_id",
            "INTEGER NOT NULL DEFAULT 1",
        )
        self._ensure_column(conn, "scene_reviews", "resolved_scene_status", "TEXT DEFAULT ''")
        self._ensure_column(conn, "scene_reviews", "result_summary", "TEXT DEFAULT ''")
        self._ensure_column(conn, "scene_reviews", "closed_at", "TIMESTAMP")
        self._ensure_column(conn, "scene_patches", "before_text", "TEXT DEFAULT ''")
        self._ensure_column(conn, "scene_patches", "after_text", "TEXT DEFAULT ''")
        self._ensure_column(
            conn,
            "scene_patches",
            "verifier_issues_json",
            "JSON DEFAULT '[]'",
        )
        self._ensure_column(
            conn,
            "scene_patches",
            "applied_successfully",
            "INTEGER NOT NULL DEFAULT 0",
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scene_review_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                operator TEXT DEFAULT '',
                input_payload_json JSON DEFAULT '{}',
                result_payload_json JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES scene_reviews(id)
            )
            """
        )

        # Rebuild migrations replace tables in-place; temporarily disable FK checks
        # to avoid transient parent/child dependency failures during swap.
        conn.commit()
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            if not self._has_composite_unique(conn, "chapters", ["book_id", "chapter_number"]):
                self._migrate_chapters_table(conn)

            if not self._has_composite_unique(
                conn,
                "chapter_summaries",
                ["book_id", "chapter_number"],
            ):
                self._migrate_chapter_summaries_table(conn)

            if not self._has_composite_unique(conn, "characters", ["book_id", "name"]):
                self._migrate_characters_table(conn)

            if not self._has_composite_unique(conn, "world_rules", ["book_id", "rule_key"]):
                self._migrate_world_rules_table(conn)

            if not self._has_composite_unique(conn, "foreshadowing", ["book_id", "hint_key"]):
                self._migrate_foreshadowing_table(conn)
        finally:
            conn.execute("PRAGMA foreign_keys=ON")

        conn.execute("UPDATE characters SET book_id = 1 WHERE book_id IS NULL")
        conn.execute("UPDATE world_rules SET book_id = 1 WHERE book_id IS NULL")
        conn.execute("UPDATE foreshadowing SET book_id = 1 WHERE book_id IS NULL")
        conn.execute("UPDATE timeline SET book_id = 1 WHERE book_id IS NULL")
        conn.execute("UPDATE staging_changes SET book_id = 1 WHERE book_id IS NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_characters_book_id ON characters(book_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_world_rules_book_id ON world_rules(book_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_foreshadowing_book_id ON foreshadowing(book_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timeline_book_id ON timeline(book_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_staging_changes_book_id ON staging_changes(book_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_book_id ON runs(book_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_run_chapters_run_id ON run_chapters(run_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scene_reviews_run_scene ON scene_reviews(run_id, chapter_number, scene_number)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scene_review_events_review_id ON scene_review_events(review_id)"
        )

    def _ensure_default_book(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            INSERT INTO books (
                id, name, language, style_preset, style_prompt, naming_policy, is_default
            )
            SELECT 1, '默认小说', 'zh-CN', 'literary_cn', '', 'localized_zh', 1
            WHERE NOT EXISTS (SELECT 1 FROM books WHERE id = 1)
            """
        )
        conn.execute("UPDATE books SET is_default = CASE WHEN id = 1 THEN 1 ELSE 0 END")

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_def_sql: str,
    ) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def_sql}")

    def _has_composite_unique(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        expected_columns: list[str],
    ) -> bool:
        for index_row in conn.execute(f"PRAGMA index_list({table_name})"):
            if int(index_row[2]) != 1:
                continue
            index_name = index_row[1]
            cols = [info_row[2] for info_row in conn.execute(f"PRAGMA index_info({index_name})")]
            if cols == expected_columns:
                return True
        return False

    def _migrate_chapters_table(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(conn, "chapters", "book_id", "INTEGER NOT NULL DEFAULT 1")
        conn.executescript(
            """
            DROP TABLE IF EXISTS chapters_v2;

            CREATE TABLE IF NOT EXISTS chapters_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL DEFAULT 1,
                chapter_number INTEGER NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                plan JSON DEFAULT '{}',
                word_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, chapter_number),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            INSERT INTO chapters_v2 (
                id, book_id, chapter_number, title, content,
                plan, word_count, status, created_at, updated_at
            )
            SELECT
                id,
                CASE
                    WHEN book_id IS NULL OR book_id NOT IN (SELECT id FROM books) THEN 1
                    ELSE book_id
                END,
                chapter_number,
                title,
                content,
                plan,
                word_count,
                status,
                created_at,
                updated_at
            FROM chapters;

            DROP TABLE chapters;
            ALTER TABLE chapters_v2 RENAME TO chapters;
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chapters_book_id ON chapters(book_id)")

    def _migrate_chapter_summaries_table(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(
            conn,
            "chapter_summaries",
            "book_id",
            "INTEGER NOT NULL DEFAULT 1",
        )
        conn.executescript(
            """
            DROP TABLE IF EXISTS chapter_summaries_v2;

            CREATE TABLE IF NOT EXISTS chapter_summaries_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL DEFAULT 1,
                chapter_number INTEGER NOT NULL,
                summary TEXT NOT NULL,
                key_events JSON DEFAULT '[]',
                characters_featured JSON DEFAULT '[]',
                new_facts_introduced JSON DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, chapter_number),
                FOREIGN KEY (book_id, chapter_number) REFERENCES chapters(book_id, chapter_number)
            );

            INSERT INTO chapter_summaries_v2 (
                id,
                book_id,
                chapter_number,
                summary,
                key_events,
                characters_featured,
                new_facts_introduced,
                created_at
            )
            SELECT
                id,
                CASE
                    WHEN book_id IS NULL OR book_id NOT IN (SELECT id FROM books) THEN 1
                    ELSE book_id
                END,
                chapter_number,
                summary,
                key_events,
                characters_featured,
                new_facts_introduced,
                created_at
            FROM chapter_summaries;

            DROP TABLE chapter_summaries;
            ALTER TABLE chapter_summaries_v2 RENAME TO chapter_summaries;
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chapter_summaries_book_id ON chapter_summaries(book_id)"
        )

    def _migrate_characters_table(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(conn, "characters", "book_id", "INTEGER NOT NULL DEFAULT 1")
        conn.executescript(
            """
            DROP TABLE IF EXISTS characters_v2;

            CREATE TABLE IF NOT EXISTS characters_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                description TEXT,
                core_motivation TEXT,
                attributes JSON DEFAULT '{}',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, name),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            INSERT INTO characters_v2 (
                id, book_id, name, description, core_motivation,
                attributes, status, created_at, updated_at
            )
            SELECT
                id,
                CASE
                    WHEN book_id IS NULL OR book_id NOT IN (SELECT id FROM books) THEN 1
                    ELSE book_id
                END,
                name,
                description,
                core_motivation,
                attributes,
                status,
                created_at,
                updated_at
            FROM characters;

            DROP TABLE characters;
            ALTER TABLE characters_v2 RENAME TO characters;
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_characters_book_id ON characters(book_id)")

    def _migrate_world_rules_table(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(conn, "world_rules", "book_id", "INTEGER NOT NULL DEFAULT 1")
        conn.executescript(
            """
            DROP TABLE IF EXISTS world_rules_v2;

            CREATE TABLE IF NOT EXISTS world_rules_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL DEFAULT 1,
                rule_key TEXT NOT NULL,
                description TEXT NOT NULL,
                is_immutable INTEGER DEFAULT 0,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, rule_key),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            INSERT INTO world_rules_v2 (
                id, book_id, rule_key, description, is_immutable, category, created_at
            )
            SELECT
                id,
                CASE
                    WHEN book_id IS NULL OR book_id NOT IN (SELECT id FROM books) THEN 1
                    ELSE book_id
                END,
                rule_key,
                description,
                is_immutable,
                category,
                created_at
            FROM world_rules;

            DROP TABLE world_rules;
            ALTER TABLE world_rules_v2 RENAME TO world_rules;
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_world_rules_book_id ON world_rules(book_id)")

    def _migrate_foreshadowing_table(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(conn, "foreshadowing", "book_id", "INTEGER NOT NULL DEFAULT 1")
        conn.executescript(
            """
            DROP TABLE IF EXISTS foreshadowing_v2;

            CREATE TABLE IF NOT EXISTS foreshadowing_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL DEFAULT 1,
                hint_key TEXT NOT NULL,
                description TEXT NOT NULL,
                introduced_in_chapter INTEGER,
                resolved_in_chapter INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, hint_key),
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            INSERT INTO foreshadowing_v2 (
                id,
                book_id,
                hint_key,
                description,
                introduced_in_chapter,
                resolved_in_chapter,
                status,
                created_at
            )
            SELECT
                id,
                CASE
                    WHEN book_id IS NULL OR book_id NOT IN (SELECT id FROM books) THEN 1
                    ELSE book_id
                END,
                hint_key,
                description,
                introduced_in_chapter,
                resolved_in_chapter,
                status,
                created_at
            FROM foreshadowing;

            DROP TABLE foreshadowing;
            ALTER TABLE foreshadowing_v2 RENAME TO foreshadowing;
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_foreshadowing_book_id ON foreshadowing(book_id)"
        )

    # ------------------------------------------------------------------
    # Books
    # ------------------------------------------------------------------

    def list_books(self) -> list[dict[str, Any]]:
        """Return all books ordered by default first, then id."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM books ORDER BY is_default DESC, id ASC")
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_book(self, book_id: int) -> dict[str, Any] | None:
        """Return a single book by id."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM books WHERE id = ?", (book_id,))
            row = cur.fetchone()
        return dict(row) if row else None

    def create_book(
        self,
        name: str,
        language: str = "zh-CN",
        style_preset: str = "literary_cn",
        style_prompt: str = "",
        naming_policy: str = "localized_zh",
        is_default: bool = False,
    ) -> int:
        """Create a book and optionally mark it as default."""
        with self._cursor() as cur:
            if is_default:
                cur.execute("UPDATE books SET is_default = 0")
            cur.execute(
                """
                INSERT INTO books (
                    name, language, style_preset, style_prompt, naming_policy, is_default
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, language, style_preset, style_prompt, naming_policy, int(is_default)),
            )
            return cur.lastrowid or 0

    def update_book(
        self,
        book_id: int,
        name: str,
        language: str,
        style_preset: str,
        style_prompt: str,
        naming_policy: str,
        is_default: bool,
    ) -> None:
        """Update book metadata."""
        with self._cursor() as cur:
            if is_default:
                cur.execute("UPDATE books SET is_default = 0")
            cur.execute(
                """
                UPDATE books
                SET
                    name = ?,
                    language = ?,
                    style_preset = ?,
                    style_prompt = ?,
                    naming_policy = ?,
                    is_default = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    name,
                    language,
                    style_preset,
                    style_prompt,
                    naming_policy,
                    int(is_default),
                    book_id,
                ),
            )

    # ------------------------------------------------------------------
    # Characters
    # ------------------------------------------------------------------

    def upsert_character(
        self,
        name: str,
        book_id: int = 1,
        description: str | None = None,
        core_motivation: str | None = None,
        attributes: dict[str, Any] | None = None,
        status: str = "active",
    ) -> int:
        """Insert or update a character record. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO characters (
                    book_id, name, description, core_motivation, attributes, status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, name) DO UPDATE SET
                    description = excluded.description,
                    core_motivation = excluded.core_motivation,
                    attributes = excluded.attributes,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book_id,
                    name,
                    description,
                    core_motivation,
                    json.dumps(attributes or {}),
                    status,
                ),
            )
            return cur.lastrowid or 0

    def get_character(self, name: str, book_id: int | None = 1) -> dict[str, Any] | None:
        """Return a character dict by name, or None if not found."""
        with self._cursor() as cur:
            if book_id is None:
                cur.execute("SELECT * FROM characters WHERE name = ?", (name,))
            else:
                cur.execute(
                    "SELECT * FROM characters WHERE name = ? AND book_id = ?",
                    (name, book_id),
                )
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["attributes"] = json.loads(result.get("attributes") or "{}")
        return result

    def list_characters(
        self,
        status: str | None = None,
        book_id: int | None = 1,
    ) -> list[dict[str, Any]]:
        """Return all characters, optionally filtered by status."""
        with self._cursor() as cur:
            if status and book_id is not None:
                cur.execute(
                    "SELECT * FROM characters WHERE status = ? AND book_id = ?",
                    (status, book_id),
                )
            elif status:
                cur.execute("SELECT * FROM characters WHERE status = ?", (status,))
            elif book_id is not None:
                cur.execute("SELECT * FROM characters WHERE book_id = ?", (book_id,))
            else:
                cur.execute("SELECT * FROM characters")
            rows = cur.fetchall()
        return [{**dict(r), "attributes": json.loads(r["attributes"] or "{}")} for r in rows]

    # ------------------------------------------------------------------
    # World rules
    # ------------------------------------------------------------------

    def upsert_world_rule(
        self,
        rule_key: str,
        description: str,
        book_id: int = 1,
        is_immutable: bool = False,
        category: str | None = None,
    ) -> int:
        """Insert or update a world rule. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO world_rules (book_id, rule_key, description, is_immutable, category)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(book_id, rule_key) DO UPDATE SET
                    description = excluded.description,
                    is_immutable = excluded.is_immutable,
                    category = excluded.category
                """,
                (book_id, rule_key, description, int(is_immutable), category),
            )
            return cur.lastrowid or 0

    def get_world_rule(self, rule_key: str, book_id: int | None = 1) -> dict[str, Any] | None:
        """Return a world rule by key, or None."""
        with self._cursor() as cur:
            if book_id is None:
                cur.execute("SELECT * FROM world_rules WHERE rule_key = ?", (rule_key,))
            else:
                cur.execute(
                    "SELECT * FROM world_rules WHERE rule_key = ? AND book_id = ?",
                    (rule_key, book_id),
                )
            row = cur.fetchone()
        return dict(row) if row else None

    def list_world_rules(
        self,
        immutable_only: bool = False,
        book_id: int | None = 1,
    ) -> list[dict[str, Any]]:
        """Return all world rules, optionally filtering to immutable ones."""
        with self._cursor() as cur:
            if immutable_only and book_id is not None:
                cur.execute(
                    "SELECT * FROM world_rules WHERE is_immutable = 1 AND book_id = ?",
                    (book_id,),
                )
            elif immutable_only:
                cur.execute("SELECT * FROM world_rules WHERE is_immutable = 1")
            elif book_id is not None:
                cur.execute("SELECT * FROM world_rules WHERE book_id = ?", (book_id,))
            else:
                cur.execute("SELECT * FROM world_rules")
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def upsert_timeline_event(
        self,
        event_key: str,
        description: str,
        book_id: int = 1,
        chapter_number: int | None = None,
        characters_involved: list[str] | None = None,
        timestamp_in_world: str | None = None,
    ) -> int:
        """Insert or update a timeline event. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO timeline
                    (book_id, event_key, description, chapter_number,
                     characters_involved, timestamp_in_world)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_key) DO UPDATE SET
                    book_id = excluded.book_id,
                    description = excluded.description,
                    chapter_number = excluded.chapter_number,
                    characters_involved = excluded.characters_involved,
                    timestamp_in_world = excluded.timestamp_in_world
                """,
                (
                    book_id,
                    event_key,
                    description,
                    chapter_number,
                    json.dumps(characters_involved or []),
                    timestamp_in_world,
                ),
            )
            return cur.lastrowid or 0

    def list_timeline_events(self, book_id: int | None = 1) -> list[dict[str, Any]]:
        """Return all timeline events ordered by chapter number."""
        with self._cursor() as cur:
            if book_id is None:
                cur.execute("SELECT * FROM timeline ORDER BY chapter_number ASC")
            else:
                cur.execute(
                    "SELECT * FROM timeline WHERE book_id = ? ORDER BY chapter_number ASC",
                    (book_id,),
                )
            rows = cur.fetchall()
        return [
            {**dict(r), "characters_involved": json.loads(r["characters_involved"] or "[]")}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Foreshadowing
    # ------------------------------------------------------------------

    def upsert_foreshadowing(
        self,
        hint_key: str,
        description: str,
        book_id: int = 1,
        introduced_in_chapter: int | None = None,
        resolved_in_chapter: int | None = None,
        status: str = "pending",
    ) -> int:
        """Insert or update a foreshadowing hint. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO foreshadowing
                    (
                        book_id, hint_key, description,
                        introduced_in_chapter, resolved_in_chapter, status
                    )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, hint_key) DO UPDATE SET
                    description = excluded.description,
                    introduced_in_chapter = excluded.introduced_in_chapter,
                    resolved_in_chapter = excluded.resolved_in_chapter,
                    status = excluded.status
                """,
                (
                    book_id,
                    hint_key,
                    description,
                    introduced_in_chapter,
                    resolved_in_chapter,
                    status,
                ),
            )
            return cur.lastrowid or 0

    def list_foreshadowing(
        self,
        status: str | None = None,
        book_id: int | None = 1,
    ) -> list[dict[str, Any]]:
        """Return foreshadowing hints, optionally filtered by status."""
        with self._cursor() as cur:
            if status and book_id is not None:
                cur.execute(
                    "SELECT * FROM foreshadowing WHERE status = ? AND book_id = ?",
                    (status, book_id),
                )
            elif status:
                cur.execute("SELECT * FROM foreshadowing WHERE status = ?", (status,))
            elif book_id is not None:
                cur.execute("SELECT * FROM foreshadowing WHERE book_id = ?", (book_id,))
            else:
                cur.execute("SELECT * FROM foreshadowing")
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Staging changes
    # ------------------------------------------------------------------

    def add_staging_change(
        self,
        change_type: str,
        entity_type: str,
        entity_key: str,
        proposed_data: dict[str, Any],
        book_id: int = 1,
        source_chapter: int | None = None,
    ) -> int:
        """Add a proposed change to the staging table. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO staging_changes
                    (book_id, change_type, entity_type, entity_key, proposed_data, source_chapter)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    change_type,
                    entity_type,
                    entity_key,
                    json.dumps(proposed_data),
                    source_chapter,
                ),
            )
            return cur.lastrowid or 0

    def get_staging_change(self, change_id: int) -> dict[str, Any] | None:
        """Return a staging change by id."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM staging_changes WHERE id = ?", (change_id,))
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["proposed_data"] = json.loads(result.get("proposed_data") or "{}")
        return result

    def list_staging_changes(
        self,
        status: str | None = "pending",
        book_id: int | None = 1,
    ) -> list[dict[str, Any]]:
        """Return staging changes filtered by status.

        Args:
            status: Filter by status value. Pass ``None`` to return all records.
        """
        with self._cursor() as cur:
            if status is None and book_id is None:
                cur.execute("SELECT * FROM staging_changes ORDER BY id ASC")
            elif status is None:
                cur.execute(
                    "SELECT * FROM staging_changes WHERE book_id = ? ORDER BY id ASC",
                    (book_id,),
                )
            elif book_id is None:
                cur.execute("SELECT * FROM staging_changes WHERE status = ?", (status,))
            else:
                cur.execute(
                    "SELECT * FROM staging_changes WHERE status = ? AND book_id = ?",
                    (status, book_id),
                )
            rows = cur.fetchall()
        return [{**dict(r), "proposed_data": json.loads(r["proposed_data"] or "{}")} for r in rows]

    def update_staging_status(
        self, change_id: int, status: str, rejection_reason: str | None = None
    ) -> None:
        """Update the status of a staging change."""
        with self._cursor() as cur:
            cur.execute(
                "UPDATE staging_changes SET status = ?, rejection_reason = ? WHERE id = ?",
                (status, rejection_reason, change_id),
            )

    # ------------------------------------------------------------------
    # Chapters
    # ------------------------------------------------------------------

    def upsert_chapter(
        self,
        chapter_number: int,
        content: str,
        book_id: int = 1,
        title: str | None = None,
        plan: dict[str, Any] | None = None,
        word_count: int = 0,
        status: str = "draft",
    ) -> int:
        """Insert or update a chapter. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO chapters (
                    book_id, chapter_number, title, content, plan, word_count, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, chapter_number) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    plan = excluded.plan,
                    word_count = excluded.word_count,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book_id,
                    chapter_number,
                    title,
                    content,
                    json.dumps(plan or {}),
                    word_count,
                    status,
                ),
            )
            return cur.lastrowid or 0

    def get_chapter_by_id(self, chapter_id: int, book_id: int | None = 1) -> dict[str, Any] | None:
        """Return a chapter by its primary key (id), or None."""
        with self._cursor() as cur:
            if book_id is None:
                cur.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
            else:
                cur.execute(
                    "SELECT * FROM chapters WHERE id = ? AND book_id = ?",
                    (chapter_id, book_id),
                )
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["plan"] = json.loads(result.get("plan") or "{}")
        return result

    def get_chapter(self, chapter_number: int, book_id: int = 1) -> dict[str, Any] | None:
        """Return a chapter by number, or None."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM chapters WHERE chapter_number = ? AND book_id = ?",
                (chapter_number, book_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["plan"] = json.loads(result.get("plan") or "{}")
        return result

    def list_chapters(self, book_id: int | None = 1) -> list[dict[str, Any]]:
        """Return all chapters ordered by chapter number."""
        with self._cursor() as cur:
            if book_id is None:
                cur.execute("SELECT * FROM chapters ORDER BY chapter_number ASC")
            else:
                cur.execute(
                    "SELECT * FROM chapters WHERE book_id = ? ORDER BY chapter_number ASC",
                    (book_id,),
                )
            rows = cur.fetchall()
        return [{**dict(r), "plan": json.loads(r["plan"] or "{}")} for r in rows]

    # ------------------------------------------------------------------
    # Chapter summaries
    # ------------------------------------------------------------------

    def upsert_chapter_summary(
        self,
        chapter_number: int,
        summary: str,
        book_id: int = 1,
        key_events: list[str] | None = None,
        characters_featured: list[str] | None = None,
        new_facts_introduced: list[str] | None = None,
    ) -> int:
        """Insert or update a chapter summary. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO chapter_summaries
                    (
                        book_id, chapter_number, summary,
                        key_events, characters_featured, new_facts_introduced
                    )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, chapter_number) DO UPDATE SET
                    summary = excluded.summary,
                    key_events = excluded.key_events,
                    characters_featured = excluded.characters_featured,
                    new_facts_introduced = excluded.new_facts_introduced
                """,
                (
                    book_id,
                    chapter_number,
                    summary,
                    json.dumps(key_events or []),
                    json.dumps(characters_featured or []),
                    json.dumps(new_facts_introduced or []),
                ),
            )
            return cur.lastrowid or 0

    def get_chapter_summary(self, chapter_number: int, book_id: int = 1) -> dict[str, Any] | None:
        """Return a chapter summary by chapter number, or None."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM chapter_summaries WHERE chapter_number = ? AND book_id = ?",
                (chapter_number, book_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        for key in ("key_events", "characters_featured", "new_facts_introduced"):
            result[key] = json.loads(result.get(key) or "[]")
        return result

    def list_chapter_summaries(self, book_id: int | None = 1) -> list[dict[str, Any]]:
        """Return all chapter summaries ordered by chapter number."""
        with self._cursor() as cur:
            if book_id is None:
                cur.execute("SELECT * FROM chapter_summaries ORDER BY chapter_number ASC")
            else:
                cur.execute(
                    "SELECT * FROM chapter_summaries WHERE book_id = ? ORDER BY chapter_number ASC",
                    (book_id,),
                )
            rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("key_events", "characters_featured", "new_facts_introduced"):
                d[key] = json.loads(d.get(key) or "[]")
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # 系统配置（system_config）
    # ------------------------------------------------------------------

    def set_system_config(self, config_key: str, config_value: str) -> None:
        """Insert or update a system config entry."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO system_config (config_key, config_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = excluded.config_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (config_key, config_value),
            )

    def get_system_config(self, config_key: str) -> str | None:
        """Return the raw (possibly encrypted) value for a config key, or None."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT config_value FROM system_config WHERE config_key = ?",
                (config_key,),
            )
            row = cur.fetchone()
        return row["config_value"] if row else None

    def list_system_config(self) -> dict[str, str]:
        """Return all system config entries as a dict {key: value}."""
        with self._cursor() as cur:
            cur.execute("SELECT config_key, config_value FROM system_config")
            rows = cur.fetchall()
        return {r["config_key"]: r["config_value"] for r in rows}

    # ------------------------------------------------------------------
    # 用户管理（users）
    # ------------------------------------------------------------------

    def create_user(self, username: str, password_hash: str, role: str = "user") -> int:
        """创建新用户，返回行 id。"""
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, password_hash, role),
            )
            return cur.lastrowid or 0

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """按用户名查找用户，不存在则返回 None。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
        return dict(row) if row else None

    def count_admins(self) -> int:
        """返回 admin 角色的用户数量。"""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'")
            row = cur.fetchone()
        return row["cnt"] if row else 0

    def update_user_password(self, user_id: int, new_password_hash: str) -> None:
        """Update a user's password hash by user id."""
        with self._cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_password_hash, user_id),
            )

    # ------------------------------------------------------------------
    # Run traces
    # ------------------------------------------------------------------

    def create_run_trace(
        self,
        task_id: str,
        book_id: int,
        status: str,
        config_snapshot: dict[str, Any],
        llm_snapshot: dict[str, Any],
    ) -> int:
        """创建一次 run 的摘要记录。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (
                    task_id, book_id, status, config_snapshot, llm_snapshot
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    book_id,
                    status,
                    json.dumps(config_snapshot),
                    json.dumps(llm_snapshot),
                ),
            )
            return cur.lastrowid or 0

    def update_run_trace_status(
        self,
        run_id: int,
        status: str,
        error_message: str | None = None,
        finished: bool = False,
    ) -> None:
        """更新 run 状态，必要时补 finished_at 与错误信息。"""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE runs
                SET
                    status = ?,
                    error_message = ?,
                    finished_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE finished_at END
                WHERE id = ?
                """,
                (status, error_message, int(finished), run_id),
            )

    def get_run_trace_by_task_id(self, task_id: str) -> dict[str, Any] | None:
        """按 task_id 读取单条 run trace。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["config_snapshot"] = json.loads(result.get("config_snapshot") or "{}")
        result["llm_snapshot"] = json.loads(result.get("llm_snapshot") or "{}")
        return result

    def get_run_trace(self, run_id: int) -> dict[str, Any] | None:
        """按 run_id 读取单条 run trace。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["config_snapshot"] = json.loads(result.get("config_snapshot") or "{}")
        result["llm_snapshot"] = json.loads(result.get("llm_snapshot") or "{}")
        return result

    def upsert_run_chapter_trace(
        self,
        run_id: int,
        chapter_number: int,
        status: str,
        planner_output: dict[str, Any],
        retrieval_pack: dict[str, Any],
        draft_text: str,
        final_content: str,
        changeset: dict[str, Any],
        verifier_issues: list[dict[str, Any]],
        editor_rewrites: list[dict[str, Any]],
        merge_result: dict[str, Any],
        summary_result: dict[str, Any],
        metrics: dict[str, Any],
        error_message: str | None = None,
    ) -> int:
        """插入或更新某次 run 的单章 trace。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO run_chapters (
                    run_id,
                    chapter_number,
                    status,
                    planner_output_json,
                    retrieval_pack_json,
                    draft_text,
                    final_content,
                    changeset_json,
                    verifier_issues_json,
                    editor_rewrites_json,
                    merge_result_json,
                    summary_json,
                    metrics_json,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, chapter_number) DO UPDATE SET
                    status = excluded.status,
                    planner_output_json = excluded.planner_output_json,
                    retrieval_pack_json = excluded.retrieval_pack_json,
                    draft_text = excluded.draft_text,
                    final_content = excluded.final_content,
                    changeset_json = excluded.changeset_json,
                    verifier_issues_json = excluded.verifier_issues_json,
                    editor_rewrites_json = excluded.editor_rewrites_json,
                    merge_result_json = excluded.merge_result_json,
                    summary_json = excluded.summary_json,
                    metrics_json = excluded.metrics_json,
                    error_message = excluded.error_message,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    run_id,
                    chapter_number,
                    status,
                    json.dumps(planner_output),
                    json.dumps(retrieval_pack),
                    draft_text,
                    final_content,
                    json.dumps(changeset),
                    json.dumps(verifier_issues),
                    json.dumps(editor_rewrites),
                    json.dumps(merge_result),
                    json.dumps(summary_result),
                    json.dumps(metrics),
                    error_message,
                ),
            )
            return cur.lastrowid or 0

    def list_run_chapter_traces(self, run_id: int) -> list[dict[str, Any]]:
        """按章节号顺序返回某次 run 的全部章节 trace。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM run_chapters WHERE run_id = ? ORDER BY chapter_number ASC",
                (run_id,),
            )
            rows = cur.fetchall()
        return [self._decode_run_chapter_trace(dict(row)) for row in rows]

    def get_run_chapter_trace(self, run_id: int, chapter_number: int) -> dict[str, Any] | None:
        """读取某次 run 的单章 trace。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM run_chapters
                WHERE run_id = ? AND chapter_number = ?
                """,
                (run_id, chapter_number),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._decode_run_chapter_trace(dict(row))

    def _decode_run_chapter_trace(self, result: dict[str, Any]) -> dict[str, Any]:
        """把 JSON 列反序列化回 Python 结构，供服务层直接消费。"""
        result["planner_output_json"] = json.loads(result.get("planner_output_json") or "{}")
        result["retrieval_pack_json"] = json.loads(result.get("retrieval_pack_json") or "{}")
        result["changeset_json"] = json.loads(result.get("changeset_json") or "{}")
        result["verifier_issues_json"] = json.loads(result.get("verifier_issues_json") or "[]")
        result["editor_rewrites_json"] = json.loads(result.get("editor_rewrites_json") or "[]")
        result["merge_result_json"] = json.loads(result.get("merge_result_json") or "{}")
        result["summary_json"] = json.loads(result.get("summary_json") or "{}")
        result["metrics_json"] = json.loads(result.get("metrics_json") or "{}")
        return result

    # ------------------------------------------------------------------
    # Scene 驱动架构：run scenes / reviews / loops / outputs
    # ------------------------------------------------------------------

    def upsert_run_scene_trace(self, run_id: int, payload: dict[str, Any]) -> int:
        """插入或更新单个 scene 的 trace。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO run_scenes (
                    run_id, chapter_number, scene_number, status, scene_plan_json, draft_json,
                    final_text, changeset_json, verifier_issues_json, review_required,
                    review_reason, review_status, metrics_json, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, chapter_number, scene_number) DO UPDATE SET
                    status = excluded.status,
                    scene_plan_json = excluded.scene_plan_json,
                    draft_json = excluded.draft_json,
                    final_text = excluded.final_text,
                    changeset_json = excluded.changeset_json,
                    verifier_issues_json = excluded.verifier_issues_json,
                    review_required = excluded.review_required,
                    review_reason = excluded.review_reason,
                    review_status = excluded.review_status,
                    metrics_json = excluded.metrics_json,
                    error_message = excluded.error_message,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    run_id,
                    int(payload["chapter_number"]),
                    int(payload["scene_number"]),
                    str(payload.get("status") or "pending"),
                    json.dumps(payload.get("scene_plan") or {}),
                    json.dumps(payload.get("draft") or {}),
                    str(payload.get("final_text") or ""),
                    json.dumps(payload.get("changeset") or {}),
                    json.dumps(payload.get("verifier_issues") or []),
                    int(bool(payload.get("review_required"))),
                    str(payload.get("review_reason") or ""),
                    str(payload.get("review_status") or "auto_approved"),
                    json.dumps(payload.get("metrics") or {}),
                    payload.get("error_message"),
                ),
            )
            return cur.lastrowid or 0

    def list_run_scene_traces(self, run_id: int, chapter_number: int | None = None) -> list[dict[str, Any]]:
        """返回某次 run 下的全部 scene trace。"""
        with self._cursor() as cur:
            if chapter_number is None:
                cur.execute(
                    "SELECT * FROM run_scenes WHERE run_id = ? ORDER BY chapter_number, scene_number",
                    (run_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM run_scenes
                    WHERE run_id = ? AND chapter_number = ?
                    ORDER BY scene_number
                    """,
                    (run_id, chapter_number),
                )
            rows = cur.fetchall()
        return [self._decode_run_scene_trace(dict(row)) for row in rows]

    def get_run_scene_trace(self, run_id: int, chapter_number: int, scene_number: int) -> dict[str, Any] | None:
        """读取单个 scene trace。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM run_scenes
                WHERE run_id = ? AND chapter_number = ? AND scene_number = ?
                """,
                (run_id, chapter_number, scene_number),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._decode_run_scene_trace(dict(row))

    def _decode_run_scene_trace(self, row: dict[str, Any]) -> dict[str, Any]:
        """反序列化 scene trace。"""
        row["scene_plan_json"] = json.loads(row.get("scene_plan_json") or "{}")
        row["draft_json"] = json.loads(row.get("draft_json") or "{}")
        row["changeset_json"] = json.loads(row.get("changeset_json") or "{}")
        row["verifier_issues_json"] = json.loads(row.get("verifier_issues_json") or "[]")
        row["metrics_json"] = json.loads(row.get("metrics_json") or "{}")
        row["review_required"] = bool(row.get("review_required"))
        return row

    def upsert_story_state_snapshot(
        self,
        book_id: int,
        chapter_number: int,
        snapshot: dict[str, Any],
    ) -> int:
        """保存章节后的故事状态快照。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO story_state_snapshots (book_id, chapter_number, snapshot_json)
                VALUES (?, ?, ?)
                ON CONFLICT(book_id, chapter_number) DO UPDATE SET
                    snapshot_json = excluded.snapshot_json
                """,
                (book_id, chapter_number, json.dumps(snapshot)),
            )
            return cur.lastrowid or 0

    def get_story_state_snapshot(self, book_id: int, chapter_number: int) -> dict[str, Any] | None:
        """读取某一章的故事状态快照。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM story_state_snapshots
                WHERE book_id = ? AND chapter_number = ?
                """,
                (book_id, chapter_number),
            )
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["snapshot_json"] = json.loads(result.get("snapshot_json") or "{}")
        return result

    def upsert_loop(self, book_id: int, loop: dict[str, Any]) -> int:
        """插入或更新 loop 状态。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO loops (
                    book_id, loop_id, title, status, introduced_in_scene, due_window,
                    priority, related_characters, resolution_requirements, last_updated_scene
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, loop_id) DO UPDATE SET
                    title = excluded.title,
                    status = excluded.status,
                    introduced_in_scene = excluded.introduced_in_scene,
                    due_window = excluded.due_window,
                    priority = excluded.priority,
                    related_characters = excluded.related_characters,
                    resolution_requirements = excluded.resolution_requirements,
                    last_updated_scene = excluded.last_updated_scene,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book_id,
                    loop["loop_id"],
                    loop["title"],
                    loop.get("status", "open"),
                    loop.get("introduced_in_scene", ""),
                    loop.get("due_window", ""),
                    int(loop.get("priority", 1)),
                    json.dumps(loop.get("related_characters") or []),
                    json.dumps(loop.get("resolution_requirements") or []),
                    loop.get("last_updated_scene", ""),
                ),
            )
            return cur.lastrowid or 0

    def list_loops(self, book_id: int) -> list[dict[str, Any]]:
        """返回一本书的全部 loop。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM loops WHERE book_id = ? ORDER BY updated_at DESC, id DESC", (book_id,))
            rows = cur.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["related_characters"] = json.loads(item.get("related_characters") or "[]")
            item["resolution_requirements"] = json.loads(item.get("resolution_requirements") or "[]")
            result.append(item)
        return result

    def add_loop_event(
        self,
        book_id: int,
        loop_id: str,
        chapter_number: int,
        scene_number: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """记录 loop 生命周期事件。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO loop_events (
                    book_id, loop_id, chapter_number, scene_number, event_type, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (book_id, loop_id, chapter_number, scene_number, event_type, json.dumps(payload)),
            )
            return cur.lastrowid or 0

    def create_scene_review(
        self,
        run_id: int,
        chapter_number: int,
        scene_number: int,
        reason: str,
    ) -> int:
        """创建审阅队列项。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO scene_reviews (
                    run_id, chapter_number, scene_number, action, status, reason
                )
                VALUES (?, ?, ?, 'pending', 'pending', ?)
                """,
                (run_id, chapter_number, scene_number, reason),
            )
            return cur.lastrowid or 0

    def list_scene_reviews(self, book_id: int | None = None) -> list[dict[str, Any]]:
        """返回审阅队列。"""
        with self._cursor() as cur:
            if book_id is None:
                cur.execute(
                    """
                    SELECT
                        sr.*,
                        rs.status AS scene_status,
                        COALESCE(event_stats.event_count, 0) AS event_count
                    FROM scene_reviews sr
                    LEFT JOIN run_scenes rs
                        ON rs.run_id = sr.run_id
                        AND rs.chapter_number = sr.chapter_number
                        AND rs.scene_number = sr.scene_number
                    LEFT JOIN (
                        SELECT review_id, COUNT(*) AS event_count
                        FROM scene_review_events
                        GROUP BY review_id
                    ) AS event_stats ON event_stats.review_id = sr.id
                    ORDER BY sr.created_at DESC, sr.id DESC
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT
                        sr.*,
                        rs.status AS scene_status,
                        COALESCE(event_stats.event_count, 0) AS event_count
                    FROM scene_reviews sr
                    JOIN runs r ON r.id = sr.run_id
                    LEFT JOIN run_scenes rs
                        ON rs.run_id = sr.run_id
                        AND rs.chapter_number = sr.chapter_number
                        AND rs.scene_number = sr.scene_number
                    LEFT JOIN (
                        SELECT review_id, COUNT(*) AS event_count
                        FROM scene_review_events
                        GROUP BY review_id
                    ) AS event_stats ON event_stats.review_id = sr.id
                    WHERE r.book_id = ?
                    ORDER BY sr.created_at DESC, sr.id DESC
                    """,
                    (book_id,),
                )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_scene_review(self, review_id: int) -> dict[str, Any] | None:
        """读取单条审阅记录。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT
                    sr.*,
                    rs.status AS scene_status,
                    COALESCE(event_stats.event_count, 0) AS event_count
                FROM scene_reviews sr
                LEFT JOIN run_scenes rs
                    ON rs.run_id = sr.run_id
                    AND rs.chapter_number = sr.chapter_number
                    AND rs.scene_number = sr.scene_number
                LEFT JOIN (
                    SELECT review_id, COUNT(*) AS event_count
                    FROM scene_review_events
                    GROUP BY review_id
                ) AS event_stats ON event_stats.review_id = sr.id
                WHERE sr.id = ?
                """,
                (review_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def get_scene_review_by_scene(
        self,
        run_id: int,
        chapter_number: int,
        scene_number: int,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        """按 scene 定位对应 review，可选过滤状态。"""
        with self._cursor() as cur:
            if status is None:
                cur.execute(
                    """
                    SELECT * FROM scene_reviews
                    WHERE run_id = ? AND chapter_number = ? AND scene_number = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (run_id, chapter_number, scene_number),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM scene_reviews
                    WHERE run_id = ? AND chapter_number = ? AND scene_number = ? AND status = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (run_id, chapter_number, scene_number, status),
                )
            row = cur.fetchone()
        return dict(row) if row else None

    def update_scene_review(
        self,
        review_id: int,
        action: str,
        status: str,
        patch_text: str | None = None,
        reason: str | None = None,
        result_summary: str | None = None,
        resolved_scene_status: str | None = None,
        close_review: bool = False,
    ) -> dict[str, Any] | None:
        """更新审阅动作。"""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE scene_reviews
                SET
                    action = ?,
                    status = ?,
                    reason = COALESCE(?, reason),
                    patch_text = COALESCE(?, patch_text),
                    result_summary = COALESCE(?, result_summary),
                    resolved_scene_status = COALESCE(?, resolved_scene_status),
                    closed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE closed_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    action,
                    status,
                    reason,
                    patch_text,
                    result_summary,
                    resolved_scene_status,
                    int(close_review),
                    review_id,
                ),
            )
        return self.get_scene_review(review_id)

    def close_scene_review(
        self,
        review_id: int,
        action: str,
        status: str,
        resolved_scene_status: str,
        result_summary: str,
        patch_text: str | None = None,
    ) -> dict[str, Any] | None:
        """关闭一条 review。"""
        return self.update_scene_review(
            review_id=review_id,
            action=action,
            status=status,
            patch_text=patch_text,
            result_summary=result_summary,
            resolved_scene_status=resolved_scene_status,
            close_review=True,
        )

    def add_scene_review_event(
        self,
        review_id: int,
        action: str,
        status: str,
        operator: str,
        input_payload: dict[str, Any],
        result_payload: dict[str, Any],
    ) -> int:
        """记录一次 review 动作。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO scene_review_events (
                    review_id, action, status, operator, input_payload_json, result_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    action,
                    status,
                    operator,
                    json.dumps(input_payload),
                    json.dumps(result_payload),
                ),
            )
            return cur.lastrowid or 0

    def list_scene_review_events(self, review_id: int) -> list[dict[str, Any]]:
        """读取某条 review 的动作历史。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM scene_review_events
                WHERE review_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (review_id,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["input_payload_json"] = json.loads(item.get("input_payload_json") or "{}")
            item["result_payload_json"] = json.loads(item.get("result_payload_json") or "{}")
            result.append(item)
        return result

    def add_scene_patch(
        self,
        run_id: int,
        chapter_number: int,
        scene_number: int,
        patch_text: str,
        before_text: str = "",
        after_text: str = "",
        verifier_issues: list[dict[str, Any]] | None = None,
        applied_successfully: bool = False,
    ) -> int:
        """记录 patch 文本。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO scene_patches (
                    run_id, chapter_number, scene_number, patch_text, before_text,
                    after_text, verifier_issues_json, applied_successfully
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    chapter_number,
                    scene_number,
                    patch_text,
                    before_text,
                    after_text,
                    json.dumps(verifier_issues or []),
                    int(applied_successfully),
                ),
            )
            return cur.lastrowid or 0

    def list_scene_patches(self, run_id: int, chapter_number: int, scene_number: int) -> list[dict[str, Any]]:
        """读取 scene 的全部 patch 记录。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM scene_patches
                WHERE run_id = ? AND chapter_number = ? AND scene_number = ?
                ORDER BY created_at ASC, id ASC
                """,
                (run_id, chapter_number, scene_number),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["verifier_issues_json"] = json.loads(item.get("verifier_issues_json") or "[]")
            item["applied_successfully"] = bool(item.get("applied_successfully"))
            result.append(item)
        return result

    def count_pending_scene_reviews(
        self,
        run_id: int,
        chapter_number: int | None = None,
    ) -> int:
        """统计待处理 review 数量。"""
        with self._cursor() as cur:
            if chapter_number is None:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM scene_reviews WHERE run_id = ? AND status = 'pending'",
                    (run_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM scene_reviews
                    WHERE run_id = ? AND chapter_number = ? AND status = 'pending'
                    """,
                    (run_id, chapter_number),
                )
            row = cur.fetchone()
        return int(row["cnt"]) if row else 0

    def upsert_chapter_output(self, book_id: int, payload: dict[str, Any]) -> int:
        """保存最终章节输出。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO chapter_outputs (
                    book_id, run_id, chapter_number, title, content, summary_json, scene_count, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, chapter_number) DO UPDATE SET
                    run_id = excluded.run_id,
                    title = excluded.title,
                    content = excluded.content,
                    summary_json = excluded.summary_json,
                    scene_count = excluded.scene_count,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book_id,
                    payload["run_id"],
                    payload["chapter_number"],
                    payload["title"],
                    payload["content"],
                    json.dumps(payload.get("summary") or {}),
                    int(payload.get("scene_count") or 0),
                    payload.get("status", "draft"),
                ),
            )
            return cur.lastrowid or 0

    def get_chapter_output(self, book_id: int, chapter_number: int) -> dict[str, Any] | None:
        """读取最终章节输出。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM chapter_outputs
                WHERE book_id = ? AND chapter_number = ?
                """,
                (book_id, chapter_number),
            )
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["summary_json"] = json.loads(item.get("summary_json") or "{}")
        return item

    def update_chapter_output_status(
        self,
        book_id: int,
        chapter_number: int,
        status: str,
    ) -> dict[str, Any] | None:
        """只更新章节输出状态。"""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE chapter_outputs
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE book_id = ? AND chapter_number = ?
                """,
                (status, book_id, chapter_number),
            )
        return self.get_chapter_output(book_id, chapter_number)

    def list_chapter_outputs(self, book_id: int) -> list[dict[str, Any]]:
        """列出最终章节输出，供 runs/chapters 页面消费。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM chapter_outputs WHERE book_id = ? ORDER BY chapter_number ASC",
                (book_id,),
            )
            rows = cur.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["summary_json"] = json.loads(item.get("summary_json") or "{}")
            item["summary_text"] = str(item["summary_json"].get("summary") or "")
            result.append(item)
        return result
