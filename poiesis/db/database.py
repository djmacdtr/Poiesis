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
        conn.commit()

    # ------------------------------------------------------------------
    # Characters
    # ------------------------------------------------------------------

    def upsert_character(
        self,
        name: str,
        description: str | None = None,
        core_motivation: str | None = None,
        attributes: dict[str, Any] | None = None,
        status: str = "active",
    ) -> int:
        """Insert or update a character record. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO characters (name, description, core_motivation, attributes, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    core_motivation = excluded.core_motivation,
                    attributes = excluded.attributes,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    name,
                    description,
                    core_motivation,
                    json.dumps(attributes or {}),
                    status,
                ),
            )
            return cur.lastrowid or 0

    def get_character(self, name: str) -> dict[str, Any] | None:
        """Return a character dict by name, or None if not found."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM characters WHERE name = ?", (name,))
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["attributes"] = json.loads(result.get("attributes") or "{}")
        return result

    def list_characters(self, status: str | None = None) -> list[dict[str, Any]]:
        """Return all characters, optionally filtered by status."""
        with self._cursor() as cur:
            if status:
                cur.execute("SELECT * FROM characters WHERE status = ?", (status,))
            else:
                cur.execute("SELECT * FROM characters")
            rows = cur.fetchall()
        return [
            {**dict(r), "attributes": json.loads(r["attributes"] or "{}")} for r in rows
        ]

    # ------------------------------------------------------------------
    # World rules
    # ------------------------------------------------------------------

    def upsert_world_rule(
        self,
        rule_key: str,
        description: str,
        is_immutable: bool = False,
        category: str | None = None,
    ) -> int:
        """Insert or update a world rule. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO world_rules (rule_key, description, is_immutable, category)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(rule_key) DO UPDATE SET
                    description = excluded.description,
                    is_immutable = excluded.is_immutable,
                    category = excluded.category
                """,
                (rule_key, description, int(is_immutable), category),
            )
            return cur.lastrowid or 0

    def get_world_rule(self, rule_key: str) -> dict[str, Any] | None:
        """Return a world rule by key, or None."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM world_rules WHERE rule_key = ?", (rule_key,))
            row = cur.fetchone()
        return dict(row) if row else None

    def list_world_rules(self, immutable_only: bool = False) -> list[dict[str, Any]]:
        """Return all world rules, optionally filtering to immutable ones."""
        with self._cursor() as cur:
            if immutable_only:
                cur.execute("SELECT * FROM world_rules WHERE is_immutable = 1")
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
        chapter_number: int | None = None,
        characters_involved: list[str] | None = None,
        timestamp_in_world: str | None = None,
    ) -> int:
        """Insert or update a timeline event. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO timeline
                    (event_key, description, chapter_number,
                     characters_involved, timestamp_in_world)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_key) DO UPDATE SET
                    description = excluded.description,
                    chapter_number = excluded.chapter_number,
                    characters_involved = excluded.characters_involved,
                    timestamp_in_world = excluded.timestamp_in_world
                """,
                (
                    event_key,
                    description,
                    chapter_number,
                    json.dumps(characters_involved or []),
                    timestamp_in_world,
                ),
            )
            return cur.lastrowid or 0

    def list_timeline_events(self) -> list[dict[str, Any]]:
        """Return all timeline events ordered by chapter number."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM timeline ORDER BY chapter_number ASC")
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
        introduced_in_chapter: int | None = None,
        resolved_in_chapter: int | None = None,
        status: str = "pending",
    ) -> int:
        """Insert or update a foreshadowing hint. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO foreshadowing
                    (hint_key, description, introduced_in_chapter, resolved_in_chapter, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(hint_key) DO UPDATE SET
                    description = excluded.description,
                    introduced_in_chapter = excluded.introduced_in_chapter,
                    resolved_in_chapter = excluded.resolved_in_chapter,
                    status = excluded.status
                """,
                (hint_key, description, introduced_in_chapter, resolved_in_chapter, status),
            )
            return cur.lastrowid or 0

    def list_foreshadowing(self, status: str | None = None) -> list[dict[str, Any]]:
        """Return foreshadowing hints, optionally filtered by status."""
        with self._cursor() as cur:
            if status:
                cur.execute("SELECT * FROM foreshadowing WHERE status = ?", (status,))
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
        source_chapter: int | None = None,
    ) -> int:
        """Add a proposed change to the staging table. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO staging_changes
                    (change_type, entity_type, entity_key, proposed_data, source_chapter)
                VALUES (?, ?, ?, ?, ?)
                """,
                (change_type, entity_type, entity_key, json.dumps(proposed_data), source_chapter),
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

    def list_staging_changes(self, status: str | None = "pending") -> list[dict[str, Any]]:
        """Return staging changes filtered by status.

        Args:
            status: Filter by status value. Pass ``None`` to return all records.
        """
        with self._cursor() as cur:
            if status is None:
                cur.execute("SELECT * FROM staging_changes ORDER BY id ASC")
            else:
                cur.execute("SELECT * FROM staging_changes WHERE status = ?", (status,))
            rows = cur.fetchall()
        return [
            {**dict(r), "proposed_data": json.loads(r["proposed_data"] or "{}")} for r in rows
        ]

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
        title: str | None = None,
        plan: dict[str, Any] | None = None,
        word_count: int = 0,
        status: str = "draft",
    ) -> int:
        """Insert or update a chapter. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO chapters (chapter_number, title, content, plan, word_count, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chapter_number) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    plan = excluded.plan,
                    word_count = excluded.word_count,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    chapter_number,
                    title,
                    content,
                    json.dumps(plan or {}),
                    word_count,
                    status,
                ),
            )
            return cur.lastrowid or 0

    def get_chapter_by_id(self, chapter_id: int) -> dict[str, Any] | None:
        """Return a chapter by its primary key (id), or None."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["plan"] = json.loads(result.get("plan") or "{}")
        return result

    def get_chapter(self, chapter_number: int) -> dict[str, Any] | None:
        """Return a chapter by number, or None."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM chapters WHERE chapter_number = ?", (chapter_number,))
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["plan"] = json.loads(result.get("plan") or "{}")
        return result

    def list_chapters(self) -> list[dict[str, Any]]:
        """Return all chapters ordered by chapter number."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM chapters ORDER BY chapter_number ASC")
            rows = cur.fetchall()
        return [{**dict(r), "plan": json.loads(r["plan"] or "{}")} for r in rows]

    # ------------------------------------------------------------------
    # Chapter summaries
    # ------------------------------------------------------------------

    def upsert_chapter_summary(
        self,
        chapter_number: int,
        summary: str,
        key_events: list[str] | None = None,
        characters_featured: list[str] | None = None,
        new_facts_introduced: list[str] | None = None,
    ) -> int:
        """Insert or update a chapter summary. Returns the row id."""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO chapter_summaries
                    (chapter_number, summary, key_events, characters_featured, new_facts_introduced)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chapter_number) DO UPDATE SET
                    summary = excluded.summary,
                    key_events = excluded.key_events,
                    characters_featured = excluded.characters_featured,
                    new_facts_introduced = excluded.new_facts_introduced
                """,
                (
                    chapter_number,
                    summary,
                    json.dumps(key_events or []),
                    json.dumps(characters_featured or []),
                    json.dumps(new_facts_introduced or []),
                ),
            )
            return cur.lastrowid or 0

    def get_chapter_summary(self, chapter_number: int) -> dict[str, Any] | None:
        """Return a chapter summary by chapter number, or None."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM chapter_summaries WHERE chapter_number = ?", (chapter_number,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        for key in ("key_events", "characters_featured", "new_facts_introduced"):
            result[key] = json.loads(result.get(key) or "[]")
        return result

    def list_chapter_summaries(self) -> list[dict[str, Any]]:
        """Return all chapter summaries ordered by chapter number."""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM chapter_summaries ORDER BY chapter_number ASC")
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
