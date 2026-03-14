"""Poiesis SQLite 数据库管理模块。"""

from __future__ import annotations

import json
import os
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
            db_path = Path(self.db_path)
            if db_path.parent != Path(""):
                db_path.parent.mkdir(parents=True, exist_ok=True)

            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            try:
                # WAL can fail on some mounted filesystems (for example Docker on Windows).
                self._conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                self._conn.execute("PRAGMA journal_mode=DELETE")
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

    def ping(self) -> None:
        """Open the configured SQLite file and execute a trivial query."""
        conn = self._get_connection()
        conn.execute("SELECT 1")

    def debug_info(self) -> dict[str, Any]:
        """Return a compact snapshot to aid DB mount diagnostics."""
        db_path = Path(self.db_path)
        return {
            "db_path": self.db_path,
            "cwd": os.getcwd(),
            "exists": db_path.exists(),
            "parent_exists": db_path.parent.exists() if db_path.parent != Path("") else True,
        }

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
        self._ensure_column(conn, "loops", "due_start_chapter", "INTEGER")
        self._ensure_column(conn, "loops", "due_end_chapter", "INTEGER")
        self._ensure_column(conn, "book_creation_intents", "variant_preference", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_concept_variants", "variant_strategy", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_concept_variants", "core_driver", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_concept_variants", "conflict_source", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_concept_variants", "world_structure", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_concept_variants", "protagonist_arc_mode", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_concept_variants", "tone_signature", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_concept_variants", "diversity_note", "TEXT DEFAULT ''")
        self._ensure_column(conn, "book_blueprints", "relationship_graph_draft_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "relationship_graph_confirmed_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "story_arcs_draft_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "story_arcs_confirmed_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "expanded_arc_numbers_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "blueprint_continuity_state_json", "JSON DEFAULT '{}'")
        self._ensure_column(conn, "book_blueprints", "roadmap_validation_issues_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "creative_repair_proposals_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "creative_repair_runs_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "creative_control_snapshots_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprints", "generation_evals_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "book_blueprint_revisions", "relationship_graph_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "blueprint_chapter_roadmap", "relationship_progress_json", "JSON DEFAULT '[]'")
        self._ensure_column(conn, "story_state_snapshots", "blueprint_revision_id", "INTEGER")
        self._ensure_column(conn, "chapter_outputs", "blueprint_revision_id", "INTEGER")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blueprint_world_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revision_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (revision_id) REFERENCES book_blueprint_revisions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blueprint_world_factions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revision_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                position TEXT DEFAULT '',
                goal TEXT DEFAULT '',
                methods_json JSON DEFAULT '[]',
                public_image TEXT DEFAULT '',
                hidden_truth TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (revision_id) REFERENCES book_blueprint_revisions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blueprint_power_system_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revision_id INTEGER NOT NULL UNIQUE,
                core_mechanics TEXT DEFAULT '',
                costs_json JSON DEFAULT '[]',
                limitations_json JSON DEFAULT '[]',
                advancement_path_json JSON DEFAULT '[]',
                symbols_json JSON DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (revision_id) REFERENCES book_blueprint_revisions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blueprint_relationship_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revision_id INTEGER NOT NULL,
                edge_id TEXT NOT NULL,
                source_character_id TEXT NOT NULL,
                target_character_id TEXT NOT NULL,
                relation_type TEXT DEFAULT '',
                polarity TEXT DEFAULT '复杂',
                intensity INTEGER NOT NULL DEFAULT 3,
                visibility TEXT DEFAULT '半公开',
                stability TEXT DEFAULT '稳定',
                summary TEXT DEFAULT '',
                hidden_truth TEXT DEFAULT '',
                non_breakable_without_reveal INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(revision_id, edge_id),
                FOREIGN KEY (revision_id) REFERENCES book_blueprint_revisions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS character_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT '',
                public_persona TEXT DEFAULT '',
                core_motivation TEXT DEFAULT '',
                fatal_flaw TEXT DEFAULT '',
                non_negotiable_traits_json JSON DEFAULT '[]',
                arc_outline_json JSON DEFAULT '[]',
                faction_affiliation TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, character_id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                edge_id TEXT NOT NULL,
                source_character_id TEXT NOT NULL,
                target_character_id TEXT NOT NULL,
                relation_type TEXT DEFAULT '',
                polarity TEXT DEFAULT '复杂',
                intensity INTEGER NOT NULL DEFAULT 3,
                visibility TEXT DEFAULT '半公开',
                stability TEXT DEFAULT '稳定',
                summary TEXT DEFAULT '',
                hidden_truth TEXT DEFAULT '',
                non_breakable_without_reveal INTEGER NOT NULL DEFAULT 0,
                status TEXT DEFAULT 'confirmed',
                latest_chapter INTEGER,
                latest_scene_ref TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, edge_id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                edge_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                chapter_number INTEGER,
                scene_ref TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                revealed_fact TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, event_id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_pending_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                source_chapter INTEGER,
                source_scene_ref TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                character_json JSON DEFAULT '{}',
                relationship_json JSON DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                revision_number INTEGER NOT NULL,
                relationship_graph_json JSON DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, revision_number),
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_replan_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                edge_id TEXT NOT NULL,
                request_reason TEXT DEFAULT '',
                desired_change TEXT DEFAULT '',
                conflict_report_json JSON DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_replan_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                proposal_id TEXT NOT NULL,
                proposal_json JSON DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(request_id, proposal_id),
                FOREIGN KEY (request_id) REFERENCES relationship_replan_requests(id)
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_character_nodes_book_id ON character_nodes(book_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relationship_edges_book_id ON relationship_edges(book_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relationship_events_book_id ON relationship_events(book_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_relationship_pending_book_id ON relationship_pending_items(book_id)"
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
    # 创作蓝图
    # ------------------------------------------------------------------

    def upsert_creation_intent(self, book_id: int, payload: dict[str, Any]) -> int:
        """保存作者给出的高层创作意图。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO book_creation_intents (
                    book_id, genre, themes_json, tone, protagonist_prompt, conflict_prompt,
                    ending_preference, forbidden_elements_json, length_preference, target_experience,
                    variant_preference
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    genre = excluded.genre,
                    themes_json = excluded.themes_json,
                    tone = excluded.tone,
                    protagonist_prompt = excluded.protagonist_prompt,
                    conflict_prompt = excluded.conflict_prompt,
                    ending_preference = excluded.ending_preference,
                    forbidden_elements_json = excluded.forbidden_elements_json,
                    length_preference = excluded.length_preference,
                    target_experience = excluded.target_experience,
                    variant_preference = excluded.variant_preference,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book_id,
                    str(payload.get("genre") or ""),
                    json.dumps(payload.get("themes") or []),
                    str(payload.get("tone") or ""),
                    str(payload.get("protagonist_prompt") or ""),
                    str(payload.get("conflict_prompt") or ""),
                    str(payload.get("ending_preference") or ""),
                    json.dumps(payload.get("forbidden_elements") or []),
                    str(payload.get("length_preference") or ""),
                    str(payload.get("target_experience") or ""),
                    str(payload.get("variant_preference") or ""),
                ),
            )
            return cur.lastrowid or 0

    def get_creation_intent(self, book_id: int) -> dict[str, Any] | None:
        """读取单本书的创作意图。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM book_creation_intents WHERE book_id = ?", (book_id,))
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["themes"] = json.loads(item.pop("themes_json", "[]") or "[]")
        item["forbidden_elements"] = json.loads(item.pop("forbidden_elements_json", "[]") or "[]")
        return item

    def replace_concept_variants(self, book_id: int, variants: list[dict[str, Any]]) -> None:
        """重置某本书的候选方向。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM book_concept_variants WHERE book_id = ?", (book_id,))
            for item in variants:
                cur.execute(
                    """
                    INSERT INTO book_concept_variants (
                        book_id, variant_no, hook, world_pitch, main_arc_pitch,
                        ending_pitch, variant_strategy, core_driver, conflict_source,
                        world_structure, protagonist_arc_mode, tone_signature,
                        differentiators_json, diversity_note, selected
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        int(item.get("variant_no") or 0),
                        str(item.get("hook") or ""),
                        str(item.get("world_pitch") or ""),
                        str(item.get("main_arc_pitch") or ""),
                        str(item.get("ending_pitch") or ""),
                        str(item.get("variant_strategy") or ""),
                        str(item.get("core_driver") or ""),
                        str(item.get("conflict_source") or ""),
                        str(item.get("world_structure") or ""),
                        str(item.get("protagonist_arc_mode") or ""),
                        str(item.get("tone_signature") or ""),
                        json.dumps(item.get("differentiators") or []),
                        str(item.get("diversity_note") or ""),
                        int(bool(item.get("selected"))),
                    ),
                )

    def update_concept_variant(self, variant_id: int, payload: dict[str, Any]) -> None:
        """更新单条候选方向，用于单版重生成。"""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE book_concept_variants
                SET hook = ?, world_pitch = ?, main_arc_pitch = ?, ending_pitch = ?,
                    variant_strategy = ?, core_driver = ?, conflict_source = ?,
                    world_structure = ?, protagonist_arc_mode = ?, tone_signature = ?,
                    differentiators_json = ?, diversity_note = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    str(payload.get("hook") or ""),
                    str(payload.get("world_pitch") or ""),
                    str(payload.get("main_arc_pitch") or ""),
                    str(payload.get("ending_pitch") or ""),
                    str(payload.get("variant_strategy") or ""),
                    str(payload.get("core_driver") or ""),
                    str(payload.get("conflict_source") or ""),
                    str(payload.get("world_structure") or ""),
                    str(payload.get("protagonist_arc_mode") or ""),
                    str(payload.get("tone_signature") or ""),
                    json.dumps(payload.get("differentiators") or []),
                    str(payload.get("diversity_note") or ""),
                    variant_id,
                ),
            )

    def list_concept_variants(self, book_id: int) -> list[dict[str, Any]]:
        """返回候选方向列表。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM book_concept_variants WHERE book_id = ? ORDER BY variant_no ASC",
                (book_id,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["differentiators"] = json.loads(item.pop("differentiators_json", "[]") or "[]")
            item["selected"] = bool(item.get("selected"))
            result.append(item)
        return result

    def get_concept_variant(self, variant_id: int) -> dict[str, Any] | None:
        """按主键读取单条候选方向。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM book_concept_variants WHERE id = ?", (variant_id,))
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["differentiators"] = json.loads(item.pop("differentiators_json", "[]") or "[]")
        item["selected"] = bool(item.get("selected"))
        return item

    def select_concept_variant(self, book_id: int, variant_id: int) -> None:
        """标记当前作品选择的候选方向。"""
        with self._cursor() as cur:
            cur.execute("UPDATE book_concept_variants SET selected = 0 WHERE book_id = ?", (book_id,))
            cur.execute(
                "UPDATE book_concept_variants SET selected = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND book_id = ?",
                (variant_id, book_id),
            )

    def upsert_book_blueprint_state(
        self,
        book_id: int,
        *,
        status: str,
        current_step: str,
        selected_variant_id: int | None = None,
        active_revision_id: int | None = None,
        world_draft: dict[str, Any] | None = None,
        world_confirmed: dict[str, Any] | None = None,
        character_draft: list[dict[str, Any]] | None = None,
        character_confirmed: list[dict[str, Any]] | None = None,
        relationship_graph_draft: list[dict[str, Any]] | None = None,
        relationship_graph_confirmed: list[dict[str, Any]] | None = None,
        story_arcs_draft: list[dict[str, Any]] | None = None,
        story_arcs_confirmed: list[dict[str, Any]] | None = None,
        expanded_arc_numbers: list[int] | None = None,
          roadmap_draft: list[dict[str, Any]] | None = None,
          roadmap_confirmed: list[dict[str, Any]] | None = None,
          blueprint_continuity_state: dict[str, Any] | None = None,
          roadmap_validation_issues: list[dict[str, Any]] | None = None,
          creative_repair_proposals: list[dict[str, Any]] | None = None,
          creative_repair_runs: list[dict[str, Any]] | None = None,
          creative_control_snapshots: list[dict[str, Any]] | None = None,
          generation_evals: list[dict[str, Any]] | None = None,
      ) -> int:
        """保存蓝图工作态，供控制台逐层确认。

        闭环控制面的 proposals / runs / snapshots 也挂在同一行上，
        目的是先用统一真源把第一阶段 roadmap 闭环跑通，再逐层接入 scene / canon。
        """
        existing = self.get_book_blueprint_state(book_id) or {}
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO book_blueprints (
                    book_id, status, current_step, selected_variant_id, active_revision_id,
                    world_draft_json, world_confirmed_json, character_draft_json, character_confirmed_json,
                    relationship_graph_draft_json, relationship_graph_confirmed_json,
                    story_arcs_draft_json, story_arcs_confirmed_json, expanded_arc_numbers_json,
                    roadmap_draft_json, roadmap_confirmed_json, blueprint_continuity_state_json, roadmap_validation_issues_json,
                    creative_repair_proposals_json, creative_repair_runs_json, creative_control_snapshots_json, generation_evals_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    status = excluded.status,
                    current_step = excluded.current_step,
                    selected_variant_id = excluded.selected_variant_id,
                    active_revision_id = excluded.active_revision_id,
                    world_draft_json = excluded.world_draft_json,
                    world_confirmed_json = excluded.world_confirmed_json,
                    character_draft_json = excluded.character_draft_json,
                    character_confirmed_json = excluded.character_confirmed_json,
                    relationship_graph_draft_json = excluded.relationship_graph_draft_json,
                    relationship_graph_confirmed_json = excluded.relationship_graph_confirmed_json,
                    story_arcs_draft_json = excluded.story_arcs_draft_json,
                    story_arcs_confirmed_json = excluded.story_arcs_confirmed_json,
                    expanded_arc_numbers_json = excluded.expanded_arc_numbers_json,
                    roadmap_draft_json = excluded.roadmap_draft_json,
                    roadmap_confirmed_json = excluded.roadmap_confirmed_json,
                    blueprint_continuity_state_json = excluded.blueprint_continuity_state_json,
                    roadmap_validation_issues_json = excluded.roadmap_validation_issues_json,
                    creative_repair_proposals_json = excluded.creative_repair_proposals_json,
                    creative_repair_runs_json = excluded.creative_repair_runs_json,
                    creative_control_snapshots_json = excluded.creative_control_snapshots_json,
                    generation_evals_json = excluded.generation_evals_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book_id,
                    status,
                    current_step,
                    selected_variant_id if selected_variant_id is not None else existing.get("selected_variant_id"),
                    active_revision_id if active_revision_id is not None else existing.get("active_revision_id"),
                    json.dumps(world_draft if world_draft is not None else existing.get("world_draft") or {}),
                    json.dumps(
                        world_confirmed if world_confirmed is not None else existing.get("world_confirmed") or {}
                    ),
                    json.dumps(
                        character_draft if character_draft is not None else existing.get("character_draft") or []
                    ),
                    json.dumps(
                        character_confirmed
                        if character_confirmed is not None
                        else existing.get("character_confirmed") or []
                    ),
                    json.dumps(
                        relationship_graph_draft
                        if relationship_graph_draft is not None
                        else existing.get("relationship_graph_draft") or []
                    ),
                    json.dumps(
                        relationship_graph_confirmed
                        if relationship_graph_confirmed is not None
                        else existing.get("relationship_graph_confirmed") or []
                    ),
                    json.dumps(story_arcs_draft if story_arcs_draft is not None else existing.get("story_arcs_draft") or []),
                    json.dumps(
                        story_arcs_confirmed
                        if story_arcs_confirmed is not None
                        else existing.get("story_arcs_confirmed") or []
                    ),
                    json.dumps(
                        expanded_arc_numbers
                        if expanded_arc_numbers is not None
                        else existing.get("expanded_arc_numbers") or []
                    ),
                    json.dumps(roadmap_draft if roadmap_draft is not None else existing.get("roadmap_draft") or []),
                    json.dumps(
                        roadmap_confirmed if roadmap_confirmed is not None else existing.get("roadmap_confirmed") or []
                    ),
                    json.dumps(
                        blueprint_continuity_state
                        if blueprint_continuity_state is not None
                        else existing.get("blueprint_continuity_state") or {}
                    ),
                    json.dumps(
                        roadmap_validation_issues
                        if roadmap_validation_issues is not None
                        else existing.get("roadmap_validation_issues") or []
                    ),
                    json.dumps(
                        creative_repair_proposals
                        if creative_repair_proposals is not None
                        else existing.get("creative_repair_proposals") or []
                    ),
                    json.dumps(
                        creative_repair_runs if creative_repair_runs is not None else existing.get("creative_repair_runs") or []
                    ),
                    json.dumps(
                        creative_control_snapshots
                        if creative_control_snapshots is not None
                        else existing.get("creative_control_snapshots") or []
                    ),
                    json.dumps(
                        generation_evals if generation_evals is not None else existing.get("generation_evals") or []
                    ),
                ),
            )
            return cur.lastrowid or 0

    def get_book_blueprint_state(self, book_id: int) -> dict[str, Any] | None:
        """读取当前蓝图工作态。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM book_blueprints WHERE book_id = ?", (book_id,))
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["world_draft"] = json.loads(item.pop("world_draft_json", "{}") or "{}")
        item["world_confirmed"] = json.loads(item.pop("world_confirmed_json", "{}") or "{}")
        item["character_draft"] = json.loads(item.pop("character_draft_json", "[]") or "[]")
        item["character_confirmed"] = json.loads(item.pop("character_confirmed_json", "[]") or "[]")
        item["relationship_graph_draft"] = json.loads(item.pop("relationship_graph_draft_json", "[]") or "[]")
        item["relationship_graph_confirmed"] = json.loads(item.pop("relationship_graph_confirmed_json", "[]") or "[]")
        item["story_arcs_draft"] = json.loads(item.pop("story_arcs_draft_json", "[]") or "[]")
        item["story_arcs_confirmed"] = json.loads(item.pop("story_arcs_confirmed_json", "[]") or "[]")
        item["expanded_arc_numbers"] = json.loads(item.pop("expanded_arc_numbers_json", "[]") or "[]")
        item["roadmap_draft"] = json.loads(item.pop("roadmap_draft_json", "[]") or "[]")
        item["roadmap_confirmed"] = json.loads(item.pop("roadmap_confirmed_json", "[]") or "[]")
        item["blueprint_continuity_state"] = json.loads(item.pop("blueprint_continuity_state_json", "{}") or "{}")
        item["roadmap_validation_issues"] = json.loads(item.pop("roadmap_validation_issues_json", "[]") or "[]")
        item["creative_repair_proposals"] = json.loads(item.pop("creative_repair_proposals_json", "[]") or "[]")
        item["creative_repair_runs"] = json.loads(item.pop("creative_repair_runs_json", "[]") or "[]")
        item["creative_control_snapshots"] = json.loads(item.pop("creative_control_snapshots_json", "[]") or "[]")
        item["generation_evals"] = json.loads(item.pop("generation_evals_json", "[]") or "[]")
        return item

    def create_blueprint_revision(
        self,
        book_id: int,
        *,
        revision_number: int,
        selected_variant_id: int | None,
        change_reason: str,
        change_summary: str,
        affected_range: list[int],
        world_blueprint: dict[str, Any],
        character_blueprints: list[dict[str, Any]],
        relationship_graph: list[dict[str, Any]],
        roadmap: list[dict[str, Any]],
        is_active: bool,
    ) -> int:
        """创建新的蓝图版本快照。"""
        blueprint_payload = {
            "book_id": book_id,
            "selected_variant_id": selected_variant_id,
            "world": world_blueprint,
            "characters": character_blueprints,
            "relationship_graph": relationship_graph,
            "roadmap": roadmap,
        }
        with self._cursor() as cur:
            if is_active:
                cur.execute("UPDATE book_blueprint_revisions SET is_active = 0 WHERE book_id = ?", (book_id,))
            cur.execute(
                """
                INSERT INTO book_blueprint_revisions (
                    book_id, revision_number, selected_variant_id, change_reason, change_summary,
                    affected_range_json, world_blueprint_json, character_blueprints_json, relationship_graph_json, roadmap_json,
                    blueprint_json, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    revision_number,
                    selected_variant_id,
                    change_reason,
                    change_summary,
                    json.dumps(affected_range),
                    json.dumps(world_blueprint),
                    json.dumps(character_blueprints),
                    json.dumps(relationship_graph),
                    json.dumps(roadmap),
                    json.dumps(blueprint_payload),
                    int(is_active),
                ),
            )
            revision_id = cur.lastrowid or 0
        self.replace_blueprint_world_rules(revision_id, world_blueprint)
        self.replace_blueprint_characters(revision_id, character_blueprints)
        self.replace_blueprint_relationship_edges(revision_id, relationship_graph)
        self.replace_blueprint_chapter_roadmap(revision_id, roadmap)
        if change_reason or change_summary:
            self.add_blueprint_revision_change(revision_id, change_reason, change_summary, affected_range)
        return revision_id

    def list_blueprint_revisions(self, book_id: int) -> list[dict[str, Any]]:
        """返回蓝图版本历史。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM book_blueprint_revisions WHERE book_id = ? ORDER BY revision_number DESC",
                (book_id,),
            )
            rows = cur.fetchall()
        return [self._decode_blueprint_revision(dict(row)) for row in rows]

    def get_blueprint_revision(self, revision_id: int) -> dict[str, Any] | None:
        """读取单个蓝图版本。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM book_blueprint_revisions WHERE id = ?", (revision_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._decode_blueprint_revision(dict(row))

    def get_active_blueprint_revision(self, book_id: int) -> dict[str, Any] | None:
        """读取当前激活的蓝图版本。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM book_blueprint_revisions WHERE book_id = ? AND is_active = 1 ORDER BY revision_number DESC LIMIT 1",
                (book_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._decode_blueprint_revision(dict(row))

    def _decode_blueprint_revision(self, row: dict[str, Any]) -> dict[str, Any]:
        row["affected_range"] = json.loads(row.pop("affected_range_json", "[]") or "[]")
        row["world_blueprint"] = json.loads(row.pop("world_blueprint_json", "{}") or "{}")
        row["character_blueprints"] = json.loads(row.pop("character_blueprints_json", "[]") or "[]")
        row["relationship_graph"] = json.loads(row.pop("relationship_graph_json", "[]") or "[]")
        row["roadmap"] = json.loads(row.pop("roadmap_json", "[]") or "[]")
        row["blueprint"] = json.loads(row.pop("blueprint_json", "{}") or "{}")
        row["is_active"] = bool(row.get("is_active"))
        return row

    def replace_blueprint_world_rules(self, revision_id: int, world_blueprint: dict[str, Any]) -> None:
        """用当前世界观蓝图刷新版本下的规则快照。"""
        rules = list(world_blueprint.get("immutable_rules") or [])
        taboo_rules = list(world_blueprint.get("taboo_rules") or [])
        geography = list(world_blueprint.get("geography") or [])
        factions = list(world_blueprint.get("factions") or [])
        power_system = dict(world_blueprint.get("power_system") or {})
        with self._cursor() as cur:
            cur.execute("DELETE FROM blueprint_world_rules WHERE revision_id = ?", (revision_id,))
            cur.execute("DELETE FROM blueprint_world_locations WHERE revision_id = ?", (revision_id,))
            cur.execute("DELETE FROM blueprint_world_factions WHERE revision_id = ?", (revision_id,))
            cur.execute("DELETE FROM blueprint_power_system_snapshots WHERE revision_id = ?", (revision_id,))
            for rule in rules:
                cur.execute(
                    """
                    INSERT INTO blueprint_world_rules (revision_id, rule_key, description, is_immutable, category)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        str(rule.get("key") or ""),
                        str(rule.get("description") or ""),
                        int(bool(rule.get("is_immutable", True))),
                        str(rule.get("category") or "world"),
                    ),
                )
            for taboo in taboo_rules:
                cur.execute(
                    """
                    INSERT INTO blueprint_world_rules (revision_id, rule_key, description, is_immutable, category)
                    VALUES (?, ?, ?, 1, 'taboo')
                    """,
                    (
                        revision_id,
                        str(taboo.get("key") or ""),
                        str(taboo.get("description") or ""),
                    ),
                )
            if world_blueprint.get("setting_summary"):
                cur.execute(
                    """
                    INSERT INTO blueprint_world_rules (revision_id, rule_key, description, is_immutable, category)
                    VALUES (?, 'world_setting', ?, 1, 'setting')
                    """,
                    (revision_id, str(world_blueprint.get("setting_summary") or "")),
                )
            if world_blueprint.get("era_context"):
                cur.execute(
                    """
                    INSERT INTO blueprint_world_rules (revision_id, rule_key, description, is_immutable, category)
                    VALUES (?, 'era_context', ?, 1, 'setting')
                    """,
                    (revision_id, str(world_blueprint.get("era_context") or "")),
                )
            if world_blueprint.get("social_order"):
                cur.execute(
                    """
                    INSERT INTO blueprint_world_rules (revision_id, rule_key, description, is_immutable, category)
                    VALUES (?, 'social_order', ?, 0, 'setting')
                    """,
                    (revision_id, str(world_blueprint.get("social_order") or "")),
                )
            if power_system:
                cur.execute(
                    """
                    INSERT INTO blueprint_power_system_snapshots (
                        revision_id, core_mechanics, costs_json, limitations_json, advancement_path_json, symbols_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        str(power_system.get("core_mechanics") or ""),
                        json.dumps(power_system.get("costs") or []),
                        json.dumps(power_system.get("limitations") or []),
                        json.dumps(power_system.get("advancement_path") or []),
                        json.dumps(power_system.get("symbols") or []),
                    ),
                )
            for location in geography:
                cur.execute(
                    """
                    INSERT INTO blueprint_world_locations (revision_id, name, role, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        str(location.get("name") or ""),
                        str(location.get("role") or ""),
                        str(location.get("description") or ""),
                    ),
                )
            for faction in factions:
                cur.execute(
                    """
                    INSERT INTO blueprint_world_factions (
                        revision_id, name, position, goal, methods_json, public_image, hidden_truth
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        str(faction.get("name") or ""),
                        str(faction.get("position") or ""),
                        str(faction.get("goal") or ""),
                        json.dumps(faction.get("methods") or []),
                        str(faction.get("public_image") or ""),
                        str(faction.get("hidden_truth") or ""),
                    ),
                )

    def list_blueprint_world_rules(self, revision_id: int) -> list[dict[str, Any]]:
        """读取版本下的世界规则快照。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_world_rules WHERE revision_id = ? ORDER BY id ASC",
                (revision_id,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_blueprint_world_locations(self, revision_id: int) -> list[dict[str, Any]]:
        """读取版本下的关键地点。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_world_locations WHERE revision_id = ? ORDER BY id ASC",
                (revision_id,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_blueprint_world_factions(self, revision_id: int) -> list[dict[str, Any]]:
        """读取版本下的势力结构。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_world_factions WHERE revision_id = ? ORDER BY id ASC",
                (revision_id,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["methods"] = json.loads(item.pop("methods_json", "[]") or "[]")
            result.append(item)
        return result

    def get_blueprint_power_system_snapshot(self, revision_id: int) -> dict[str, Any] | None:
        """读取版本下的力量体系快照。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_power_system_snapshots WHERE revision_id = ?",
                (revision_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["costs"] = json.loads(item.pop("costs_json", "[]") or "[]")
        item["limitations"] = json.loads(item.pop("limitations_json", "[]") or "[]")
        item["advancement_path"] = json.loads(item.pop("advancement_path_json", "[]") or "[]")
        item["symbols"] = json.loads(item.pop("symbols_json", "[]") or "[]")
        return item

    def replace_blueprint_characters(self, revision_id: int, characters: list[dict[str, Any]]) -> None:
        """刷新版本下的人物蓝图快照。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM blueprint_characters WHERE revision_id = ?", (revision_id,))
            for item in characters:
                cur.execute(
                    """
                    INSERT INTO blueprint_characters (
                        revision_id, name, role, public_persona, core_motivation, fatal_flaw,
                        non_negotiable_traits_json, relationship_constraints_json, arc_outline_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        str(item.get("name") or ""),
                        str(item.get("role") or ""),
                        str(item.get("public_persona") or ""),
                        str(item.get("core_motivation") or ""),
                        str(item.get("fatal_flaw") or ""),
                        json.dumps(item.get("non_negotiable_traits") or []),
                        json.dumps(item.get("relationship_constraints") or []),
                        json.dumps(item.get("arc_outline") or []),
                    ),
                )

    def replace_blueprint_relationship_edges(self, revision_id: int, edges: list[dict[str, Any]]) -> None:
        """刷新版本下的人物关系图谱快照。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM blueprint_relationship_edges WHERE revision_id = ?", (revision_id,))
            for item in edges:
                cur.execute(
                    """
                    INSERT INTO blueprint_relationship_edges (
                        revision_id, edge_id, source_character_id, target_character_id, relation_type,
                        polarity, intensity, visibility, stability, summary, hidden_truth,
                        non_breakable_without_reveal
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        str(item.get("edge_id") or ""),
                        str(item.get("source_character_id") or ""),
                        str(item.get("target_character_id") or ""),
                        str(item.get("relation_type") or ""),
                        str(item.get("polarity") or "复杂"),
                        int(item.get("intensity") or 3),
                        str(item.get("visibility") or "半公开"),
                        str(item.get("stability") or "稳定"),
                        str(item.get("summary") or ""),
                        str(item.get("hidden_truth") or ""),
                        int(bool(item.get("non_breakable_without_reveal"))),
                    ),
                )

    def list_blueprint_characters(self, revision_id: int) -> list[dict[str, Any]]:
        """读取版本下的人物蓝图快照。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_characters WHERE revision_id = ? ORDER BY id ASC",
                (revision_id,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["non_negotiable_traits"] = json.loads(item.pop("non_negotiable_traits_json", "[]") or "[]")
            item["relationship_constraints"] = json.loads(
                item.pop("relationship_constraints_json", "[]") or "[]"
            )
            item["arc_outline"] = json.loads(item.pop("arc_outline_json", "[]") or "[]")
            result.append(item)
        return result

    def list_blueprint_relationship_edges(self, revision_id: int) -> list[dict[str, Any]]:
        """读取版本下的关系图谱快照。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_relationship_edges WHERE revision_id = ? ORDER BY id ASC",
                (revision_id,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["non_breakable_without_reveal"] = bool(item.get("non_breakable_without_reveal"))
            result.append(item)
        return result

    def replace_blueprint_chapter_roadmap(self, revision_id: int, roadmap: list[dict[str, Any]]) -> None:
        """刷新版本下的章节路线快照。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM blueprint_chapter_roadmap WHERE revision_id = ?", (revision_id,))
            for item in roadmap:
                cur.execute(
                    """
                    INSERT INTO blueprint_chapter_roadmap (
                        revision_id, chapter_number, title, goal, core_conflict, turning_point,
                        character_progress_json, relationship_progress_json, planned_loops_json, closure_function
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        int(item.get("chapter_number") or 0),
                        str(item.get("title") or ""),
                        str(item.get("goal") or ""),
                        str(item.get("core_conflict") or ""),
                        str(item.get("turning_point") or ""),
                        json.dumps(item.get("character_progress") or []),
                        json.dumps(item.get("relationship_progress") or []),
                        json.dumps(item.get("planned_loops") or []),
                        str(item.get("closure_function") or ""),
                    ),
                )

    def list_blueprint_chapter_roadmap(self, revision_id: int) -> list[dict[str, Any]]:
        """返回版本下全部章节路线项。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_chapter_roadmap WHERE revision_id = ? ORDER BY chapter_number ASC",
                (revision_id,),
            )
            rows = cur.fetchall()
        return [self._decode_blueprint_roadmap_row(dict(row)) for row in rows]

    def get_blueprint_chapter_roadmap_item(self, revision_id: int, chapter_number: int) -> dict[str, Any] | None:
        """读取单章路线项。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_chapter_roadmap WHERE revision_id = ? AND chapter_number = ?",
                (revision_id, chapter_number),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._decode_blueprint_roadmap_row(dict(row))

    def _decode_blueprint_roadmap_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["character_progress"] = json.loads(row.pop("character_progress_json", "[]") or "[]")
        row["relationship_progress"] = json.loads(row.pop("relationship_progress_json", "[]") or "[]")
        row["planned_loops"] = json.loads(row.pop("planned_loops_json", "[]") or "[]")
        return row

    def add_blueprint_revision_change(
        self,
        revision_id: int,
        change_reason: str,
        change_summary: str,
        affected_range: list[int],
    ) -> int:
        """记录蓝图版本变更摘要。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO blueprint_revision_changes (revision_id, change_reason, change_summary, affected_range_json)
                VALUES (?, ?, ?, ?)
                """,
                (revision_id, change_reason, change_summary, json.dumps(affected_range)),
            )
            return cur.lastrowid or 0

    def list_blueprint_revision_changes(self, revision_id: int) -> list[dict[str, Any]]:
        """读取某个蓝图版本的变更说明。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM blueprint_revision_changes WHERE revision_id = ? ORDER BY id ASC",
                (revision_id,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["affected_range"] = json.loads(item.pop("affected_range_json", "[]") or "[]")
            result.append(item)
        return result

    def replace_character_nodes(self, book_id: int, nodes: list[dict[str, Any]]) -> None:
        """用当前确认版人物节点重建执行态人物图谱。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM character_nodes WHERE book_id = ?", (book_id,))
            for item in nodes:
                cur.execute(
                    """
                    INSERT INTO character_nodes (
                        book_id, character_id, name, role, public_persona, core_motivation, fatal_flaw,
                        non_negotiable_traits_json, arc_outline_json, faction_affiliation, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        str(item.get("character_id") or item.get("name") or ""),
                        str(item.get("name") or ""),
                        str(item.get("role") or ""),
                        str(item.get("public_persona") or ""),
                        str(item.get("core_motivation") or ""),
                        str(item.get("fatal_flaw") or ""),
                        json.dumps(item.get("non_negotiable_traits") or []),
                        json.dumps(item.get("arc_outline") or []),
                        str(item.get("faction_affiliation") or ""),
                        str(item.get("status") or "active"),
                    ),
                )

    def list_character_nodes(self, book_id: int) -> list[dict[str, Any]]:
        """读取执行态人物节点。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM character_nodes WHERE book_id = ? ORDER BY id ASC", (book_id,))
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["non_negotiable_traits"] = json.loads(item.pop("non_negotiable_traits_json", "[]") or "[]")
            item["arc_outline"] = json.loads(item.pop("arc_outline_json", "[]") or "[]")
            result.append(item)
        return result

    def get_character_node(self, book_id: int, character_id: str) -> dict[str, Any] | None:
        """按 character_id 读取人物节点。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM character_nodes WHERE book_id = ? AND character_id = ?",
                (book_id, character_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["non_negotiable_traits"] = json.loads(item.pop("non_negotiable_traits_json", "[]") or "[]")
        item["arc_outline"] = json.loads(item.pop("arc_outline_json", "[]") or "[]")
        return item

    def replace_relationship_graph(self, book_id: int, edges: list[dict[str, Any]]) -> None:
        """用当前确认版关系图谱重建执行态关系边。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM relationship_edges WHERE book_id = ?", (book_id,))
            for item in edges:
                cur.execute(
                    """
                    INSERT INTO relationship_edges (
                        book_id, edge_id, source_character_id, target_character_id, relation_type,
                        polarity, intensity, visibility, stability, summary, hidden_truth,
                        non_breakable_without_reveal, status, latest_chapter, latest_scene_ref
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        str(item.get("edge_id") or ""),
                        str(item.get("source_character_id") or ""),
                        str(item.get("target_character_id") or ""),
                        str(item.get("relation_type") or ""),
                        str(item.get("polarity") or "复杂"),
                        int(item.get("intensity") or 3),
                        str(item.get("visibility") or "半公开"),
                        str(item.get("stability") or "稳定"),
                        str(item.get("summary") or ""),
                        str(item.get("hidden_truth") or ""),
                        int(bool(item.get("non_breakable_without_reveal"))),
                        str(item.get("status") or "confirmed"),
                        item.get("latest_chapter"),
                        str(item.get("latest_scene_ref") or ""),
                    ),
                )

    def upsert_relationship_edge(self, book_id: int, edge: dict[str, Any]) -> int:
        """插入或更新执行态关系边。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO relationship_edges (
                    book_id, edge_id, source_character_id, target_character_id, relation_type,
                    polarity, intensity, visibility, stability, summary, hidden_truth,
                    non_breakable_without_reveal, status, latest_chapter, latest_scene_ref
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, edge_id) DO UPDATE SET
                    source_character_id = excluded.source_character_id,
                    target_character_id = excluded.target_character_id,
                    relation_type = excluded.relation_type,
                    polarity = excluded.polarity,
                    intensity = excluded.intensity,
                    visibility = excluded.visibility,
                    stability = excluded.stability,
                    summary = excluded.summary,
                    hidden_truth = excluded.hidden_truth,
                    non_breakable_without_reveal = excluded.non_breakable_without_reveal,
                    status = excluded.status,
                    latest_chapter = excluded.latest_chapter,
                    latest_scene_ref = excluded.latest_scene_ref,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    book_id,
                    str(edge.get("edge_id") or ""),
                    str(edge.get("source_character_id") or ""),
                    str(edge.get("target_character_id") or ""),
                    str(edge.get("relation_type") or ""),
                    str(edge.get("polarity") or "复杂"),
                    int(edge.get("intensity") or 3),
                    str(edge.get("visibility") or "半公开"),
                    str(edge.get("stability") or "稳定"),
                    str(edge.get("summary") or ""),
                    str(edge.get("hidden_truth") or ""),
                    int(bool(edge.get("non_breakable_without_reveal"))),
                    str(edge.get("status") or "confirmed"),
                    edge.get("latest_chapter"),
                    str(edge.get("latest_scene_ref") or ""),
                ),
            )
            return cur.lastrowid or 0

    def list_relationship_edges(self, book_id: int, include_pending: bool = True) -> list[dict[str, Any]]:
        """读取执行态关系边。"""
        with self._cursor() as cur:
            if include_pending:
                cur.execute("SELECT * FROM relationship_edges WHERE book_id = ? ORDER BY id ASC", (book_id,))
            else:
                cur.execute(
                    "SELECT * FROM relationship_edges WHERE book_id = ? AND status = 'confirmed' ORDER BY id ASC",
                    (book_id,),
                )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["non_breakable_without_reveal"] = bool(item.get("non_breakable_without_reveal"))
            result.append(item)
        return result

    def get_relationship_edge(self, book_id: int, edge_id: str) -> dict[str, Any] | None:
        """按 edge_id 读取关系边。"""
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM relationship_edges WHERE book_id = ? AND edge_id = ?",
                (book_id, edge_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["non_breakable_without_reveal"] = bool(item.get("non_breakable_without_reveal"))
        return item

    def add_relationship_event(self, book_id: int, payload: dict[str, Any]) -> int:
        """记录关系推进事件。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO relationship_events (
                    book_id, edge_id, event_id, event_type, chapter_number, scene_ref, summary, revealed_fact
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    str(payload.get("edge_id") or ""),
                    str(payload.get("event_id") or ""),
                    str(payload.get("event_type") or ""),
                    payload.get("chapter_number"),
                    str(payload.get("scene_ref") or ""),
                    str(payload.get("summary") or ""),
                    str(payload.get("revealed_fact") or ""),
                ),
            )
            return cur.lastrowid or 0

    def list_relationship_events(self, book_id: int, edge_id: str | None = None) -> list[dict[str, Any]]:
        """读取关系事件列表。"""
        with self._cursor() as cur:
            if edge_id:
                cur.execute(
                    "SELECT * FROM relationship_events WHERE book_id = ? AND edge_id = ? ORDER BY id ASC",
                    (book_id, edge_id),
                )
            else:
                cur.execute(
                    "SELECT * FROM relationship_events WHERE book_id = ? ORDER BY id ASC",
                    (book_id,),
                )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def add_relationship_pending_item(self, book_id: int, payload: dict[str, Any]) -> int:
        """新增待确认人物或关系项。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO relationship_pending_items (
                    book_id, item_type, status, source_chapter, source_scene_ref, summary,
                    character_json, relationship_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    str(payload.get("item_type") or "character"),
                    str(payload.get("status") or "pending"),
                    payload.get("source_chapter"),
                    str(payload.get("source_scene_ref") or ""),
                    str(payload.get("summary") or ""),
                    json.dumps(payload.get("character") or {}),
                    json.dumps(payload.get("relationship") or {}),
                ),
            )
            return cur.lastrowid or 0

    def list_relationship_pending_items(self, book_id: int, status: str | None = None) -> list[dict[str, Any]]:
        """读取待确认的人物/关系队列。"""
        with self._cursor() as cur:
            if status:
                cur.execute(
                    "SELECT * FROM relationship_pending_items WHERE book_id = ? AND status = ? ORDER BY id ASC",
                    (book_id, status),
                )
            else:
                cur.execute(
                    "SELECT * FROM relationship_pending_items WHERE book_id = ? ORDER BY id ASC",
                    (book_id,),
                )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["character"] = json.loads(item.pop("character_json", "{}") or "{}")
            item["relationship"] = json.loads(item.pop("relationship_json", "{}") or "{}")
            result.append(item)
        return result

    def get_relationship_pending_item(self, item_id: int) -> dict[str, Any] | None:
        """读取单个待确认项。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM relationship_pending_items WHERE id = ?", (item_id,))
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["character"] = json.loads(item.pop("character_json", "{}") or "{}")
        item["relationship"] = json.loads(item.pop("relationship_json", "{}") or "{}")
        return item

    def update_relationship_pending_item_status(self, item_id: int, status: str) -> dict[str, Any] | None:
        """更新待确认项状态。"""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE relationship_pending_items
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, item_id),
            )
        return self.get_relationship_pending_item(item_id)

    def create_relationship_replan_request(self, book_id: int, payload: dict[str, Any]) -> int:
        """创建关系重规划请求。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO relationship_replan_requests (
                    book_id, edge_id, request_reason, desired_change, conflict_report_json, status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    str(payload.get("edge_id") or ""),
                    str(payload.get("request_reason") or ""),
                    str(payload.get("desired_change") or ""),
                    json.dumps(payload.get("conflict_report") or {}),
                    str(payload.get("status") or "pending"),
                ),
            )
            return cur.lastrowid or 0

    def get_relationship_replan_request(self, request_id: int) -> dict[str, Any] | None:
        """读取关系重规划请求。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM relationship_replan_requests WHERE id = ?", (request_id,))
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["conflict_report"] = json.loads(item.pop("conflict_report_json", "{}") or "{}")
        return item

    def add_relationship_replan_proposal(self, request_id: int, proposal_id: str, payload: dict[str, Any]) -> int:
        """保存关系重规划提案。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO relationship_replan_proposals (request_id, proposal_id, proposal_json, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    request_id,
                    proposal_id,
                    json.dumps(payload),
                    str(payload.get("status") or "draft"),
                ),
            )
            return cur.lastrowid or 0

    def get_relationship_replan_proposal(self, request_id: int, proposal_id: str) -> dict[str, Any] | None:
        """读取指定关系重规划提案。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM relationship_replan_proposals
                WHERE request_id = ? AND proposal_id = ?
                """,
                (request_id, proposal_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        item = dict(row)
        item["proposal"] = json.loads(item.pop("proposal_json", "{}") or "{}")
        return item

    def update_relationship_replan_status(self, request_id: int, status: str) -> None:
        """更新关系重规划请求状态。"""
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE relationship_replan_requests
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, request_id),
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

    def delete_characters(self, book_id: int) -> None:
        """删除某本书当前角色 canon，供蓝图确认后整体重建。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM characters WHERE book_id = ?", (book_id,))

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

    def delete_world_rules(self, book_id: int) -> None:
        """删除某本书当前世界规则 canon。"""
        with self._cursor() as cur:
            cur.execute("DELETE FROM world_rules WHERE book_id = ?", (book_id,))

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
        blueprint_revision_id: int | None = None,
    ) -> int:
        """保存章节后的故事状态快照。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO story_state_snapshots (book_id, chapter_number, blueprint_revision_id, snapshot_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(book_id, chapter_number) DO UPDATE SET
                    blueprint_revision_id = excluded.blueprint_revision_id,
                    snapshot_json = excluded.snapshot_json
                """,
                (book_id, chapter_number, blueprint_revision_id, json.dumps(snapshot)),
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

    def get_latest_story_state_snapshot(self, book_id: int) -> dict[str, Any] | None:
        """读取最近一次已发布章节的故事状态快照。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM story_state_snapshots
                WHERE book_id = ?
                ORDER BY chapter_number DESC, id DESC
                LIMIT 1
                """,
                (book_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["snapshot_json"] = json.loads(result.get("snapshot_json") or "{}")
        return result

    def list_story_state_snapshots(self, book_id: int) -> list[dict[str, Any]]:
        """列出某本书的全部故事状态快照，用于构建发布历史摘要。"""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM story_state_snapshots
                WHERE book_id = ?
                ORDER BY chapter_number ASC, id ASC
                """,
                (book_id,),
            )
            rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["snapshot_json"] = json.loads(item.get("snapshot_json") or "{}")
            result.append(item)
        return result

    def upsert_loop(self, book_id: int, loop: dict[str, Any]) -> int:
        """插入或更新 loop 状态。"""
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO loops (
                    book_id, loop_id, title, status, introduced_in_scene, due_start_chapter,
                    due_end_chapter, due_window, priority, related_characters,
                    resolution_requirements, last_updated_scene
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, loop_id) DO UPDATE SET
                    title = excluded.title,
                    status = excluded.status,
                    introduced_in_scene = excluded.introduced_in_scene,
                    due_start_chapter = excluded.due_start_chapter,
                    due_end_chapter = excluded.due_end_chapter,
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
                    loop.get("due_start_chapter"),
                    loop.get("due_end_chapter"),
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
            item["due_start_chapter"] = item.get("due_start_chapter")
            item["due_end_chapter"] = item.get("due_end_chapter")
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
                    book_id, run_id, chapter_number, blueprint_revision_id, title, content, summary_json, scene_count, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id, chapter_number) DO UPDATE SET
                    run_id = excluded.run_id,
                    blueprint_revision_id = excluded.blueprint_revision_id,
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
                    payload.get("blueprint_revision_id"),
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
