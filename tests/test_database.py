"""Tests for the Database layer."""

from __future__ import annotations

from poiesis.db.database import Database


class TestSchemaInitialization:
    """Tests for schema creation."""

    def test_initialize_schema_creates_tables(self, tmp_db: Database) -> None:
        """All expected tables exist after schema initialization."""
        expected_tables = {
            "characters",
            "world_rules",
            "timeline",
            "foreshadowing",
            "staging_changes",
            "chapters",
            "chapter_summaries",
        }
        with tmp_db._cursor() as cur:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row["name"] for row in cur.fetchall()}
        assert expected_tables.issubset(tables)

    def test_initialize_schema_is_idempotent(self, tmp_db: Database) -> None:
        """Calling initialize_schema twice does not raise or duplicate tables."""
        tmp_db.initialize_schema()  # second call
        with tmp_db._cursor() as cur:
            cur.execute(
                "SELECT count(*) AS cnt FROM sqlite_master WHERE type='table' AND name='characters'"
            )
            row = cur.fetchone()
        assert row["cnt"] == 1


class TestCharacterCRUD:
    """CRUD tests for the characters table."""

    def test_upsert_and_get_character(self, tmp_db: Database) -> None:
        tmp_db.upsert_character(
            name="Hero",
            description="A brave soul.",
            core_motivation="Save the world.",
            attributes={"age": 25, "class": "warrior"},
        )
        char = tmp_db.get_character("Hero")
        assert char is not None
        assert char["name"] == "Hero"
        assert char["description"] == "A brave soul."
        assert char["attributes"]["age"] == 25

    def test_upsert_character_updates_existing(self, tmp_db: Database) -> None:
        tmp_db.upsert_character(name="Hero", description="Old desc.")
        tmp_db.upsert_character(name="Hero", description="New desc.")
        char = tmp_db.get_character("Hero")
        assert char is not None
        assert char["description"] == "New desc."

    def test_get_nonexistent_character_returns_none(self, tmp_db: Database) -> None:
        assert tmp_db.get_character("Nobody") is None

    def test_list_characters(self, tmp_db: Database) -> None:
        tmp_db.upsert_character(name="Alice")
        tmp_db.upsert_character(name="Bob")
        chars = tmp_db.list_characters()
        names = [c["name"] for c in chars]
        assert "Alice" in names
        assert "Bob" in names

    def test_list_characters_filtered_by_status(self, tmp_db: Database) -> None:
        tmp_db.upsert_character(name="Active", status="active")
        tmp_db.upsert_character(name="Dead", status="deceased")
        active = tmp_db.list_characters(status="active")
        assert all(c["status"] == "active" for c in active)

    def test_character_attributes_json(self, tmp_db: Database) -> None:
        """JSON attributes round-trip correctly."""
        attrs = {"skills": ["swords", "magic"], "level": 5}
        tmp_db.upsert_character(name="Mage", attributes=attrs)
        char = tmp_db.get_character("Mage")
        assert char is not None
        assert char["attributes"]["skills"] == ["swords", "magic"]
        assert char["attributes"]["level"] == 5

    def test_character_isolated_by_book_id(self, tmp_db: Database) -> None:
        second_book = tmp_db.create_book(name="副本A")
        tmp_db.upsert_character(name="Hero", description="默认书", book_id=1)
        tmp_db.upsert_character(name="Hero", description="副本书", book_id=second_book)

        default_char = tmp_db.get_character("Hero", book_id=1)
        second_char = tmp_db.get_character("Hero", book_id=second_book)

        assert default_char is not None
        assert second_char is not None
        assert default_char["description"] == "默认书"
        assert second_char["description"] == "副本书"


class TestWorldRuleCRUD:
    """CRUD tests for the world_rules table."""

    def test_upsert_and_get_rule(self, tmp_db: Database) -> None:
        tmp_db.upsert_world_rule("no_flying", "Nobody can fly.", is_immutable=True)
        rule = tmp_db.get_world_rule("no_flying")
        assert rule is not None
        assert rule["description"] == "Nobody can fly."
        assert rule["is_immutable"] == 1

    def test_list_immutable_only(self, tmp_db: Database) -> None:
        tmp_db.upsert_world_rule("r1", "Immutable rule.", is_immutable=True)
        tmp_db.upsert_world_rule("r2", "Mutable rule.", is_immutable=False)
        immutable = tmp_db.list_world_rules(immutable_only=True)
        assert all(r["is_immutable"] == 1 for r in immutable)
        assert any(r["rule_key"] == "r1" for r in immutable)
        assert not any(r["rule_key"] == "r2" for r in immutable)

    def test_world_rule_isolated_by_book_id(self, tmp_db: Database) -> None:
        second_book = tmp_db.create_book(name="副本B")
        tmp_db.upsert_world_rule("gravity", "重力恒定", book_id=1)
        tmp_db.upsert_world_rule("gravity", "重力可变", book_id=second_book)

        default_rule = tmp_db.get_world_rule("gravity", book_id=1)
        second_rule = tmp_db.get_world_rule("gravity", book_id=second_book)

        assert default_rule is not None
        assert second_rule is not None
        assert default_rule["description"] == "重力恒定"
        assert second_rule["description"] == "重力可变"


class TestTimelineCRUD:
    """CRUD tests for the timeline table."""

    def test_upsert_and_list_events(self, tmp_db: Database) -> None:
        tmp_db.upsert_timeline_event(
            "event_1",
            "The battle of the plains.",
            chapter_number=3,
            characters_involved=["Hero", "Villain"],
            timestamp_in_world="Year 100",
        )
        events = tmp_db.list_timeline_events()
        assert len(events) == 1
        assert events[0]["event_key"] == "event_1"
        assert "Hero" in events[0]["characters_involved"]

    def test_timeline_json_columns(self, tmp_db: Database) -> None:
        """characters_involved JSON column round-trips correctly."""
        involved = ["Alice", "Bob", "Carol"]
        tmp_db.upsert_timeline_event("e2", "Group event.", characters_involved=involved)
        events = tmp_db.list_timeline_events()
        assert events[0]["characters_involved"] == involved


class TestStagingChanges:
    """Tests for the staging_changes table."""

    def test_add_and_get_staging_change(self, tmp_db: Database) -> None:
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="NewChar",
            proposed_data={"name": "NewChar", "description": "A new character."},
            source_chapter=1,
        )
        change = tmp_db.get_staging_change(change_id)
        assert change is not None
        assert change["entity_key"] == "NewChar"
        assert change["proposed_data"]["name"] == "NewChar"
        assert change["status"] == "pending"

    def test_update_staging_status(self, tmp_db: Database) -> None:
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="world_rule",
            entity_key="new_rule",
            proposed_data={"rule_key": "new_rule", "description": "Test."},
        )
        tmp_db.update_staging_status(change_id, "approved")
        change = tmp_db.get_staging_change(change_id)
        assert change is not None
        assert change["status"] == "approved"

    def test_update_staging_rejection_reason(self, tmp_db: Database) -> None:
        change_id = tmp_db.add_staging_change(
            change_type="upsert",
            entity_type="character",
            entity_key="Villain",
            proposed_data={"name": "Villain"},
        )
        tmp_db.update_staging_status(change_id, "rejected", rejection_reason="Contradicts canon.")
        change = tmp_db.get_staging_change(change_id)
        assert change is not None
        assert change["rejection_reason"] == "Contradicts canon."

    def test_list_staging_changes_by_status(self, tmp_db: Database) -> None:
        tmp_db.add_staging_change("upsert", "character", "A", {"name": "A"})
        tmp_db.add_staging_change("upsert", "character", "B", {"name": "B"})
        pending = tmp_db.list_staging_changes(status="pending")
        assert len(pending) == 2


class TestChapterCRUD:
    """CRUD tests for the chapters table."""

    def test_upsert_and_get_chapter(self, tmp_db: Database) -> None:
        tmp_db.upsert_chapter(
            chapter_number=1,
            content="Once upon a time...",
            title="The Beginning",
            plan={"key_events": ["Hero departs"]},
            word_count=4,
        )
        chapter = tmp_db.get_chapter(1)
        assert chapter is not None
        assert chapter["title"] == "The Beginning"
        assert chapter["content"] == "Once upon a time..."
        assert chapter["plan"]["key_events"] == ["Hero departs"]

    def test_upsert_chapter_updates_existing(self, tmp_db: Database) -> None:
        tmp_db.upsert_chapter(1, "v1 content")
        tmp_db.upsert_chapter(1, "v2 content", title="Updated")
        chapter = tmp_db.get_chapter(1)
        assert chapter is not None
        assert chapter["content"] == "v2 content"

    def test_list_chapters_ordered(self, tmp_db: Database) -> None:
        tmp_db.upsert_chapter(3, "Chapter 3")
        tmp_db.upsert_chapter(1, "Chapter 1")
        tmp_db.upsert_chapter(2, "Chapter 2")
        chapters = tmp_db.list_chapters()
        nums = [c["chapter_number"] for c in chapters]
        assert nums == [1, 2, 3]


class TestChapterSummaryCRUD:
    """CRUD tests for the chapter_summaries table."""

    def test_upsert_and_get_summary(self, tmp_db: Database) -> None:
        tmp_db.upsert_chapter(1, "Chapter content.")
        tmp_db.upsert_chapter_summary(
            chapter_number=1,
            summary="The hero begins their journey.",
            key_events=["Departure"],
            characters_featured=["Hero"],
            new_facts_introduced=["The world is round."],
        )
        summary = tmp_db.get_chapter_summary(1)
        assert summary is not None
        assert summary["summary"] == "The hero begins their journey."
        assert "Departure" in summary["key_events"]
        assert "Hero" in summary["characters_featured"]
        assert "The world is round." in summary["new_facts_introduced"]

    def test_list_summaries_ordered(self, tmp_db: Database) -> None:
        tmp_db.upsert_chapter(1, "c1")
        tmp_db.upsert_chapter(2, "c2")
        tmp_db.upsert_chapter_summary(2, "Summary 2.")
        tmp_db.upsert_chapter_summary(1, "Summary 1.")
        summaries = tmp_db.list_chapter_summaries()
        nums = [s["chapter_number"] for s in summaries]
        assert nums == [1, 2]


class TestForeshadowingCRUD:
    """CRUD tests for the foreshadowing table."""

    def test_foreshadowing_isolated_by_book_id(self, tmp_db: Database) -> None:
        second_book = tmp_db.create_book(name="副本C")
        tmp_db.upsert_foreshadowing("hint_1", "默认伏笔", book_id=1)
        tmp_db.upsert_foreshadowing("hint_1", "副本伏笔", book_id=second_book)

        default_hints = tmp_db.list_foreshadowing(book_id=1)
        second_hints = tmp_db.list_foreshadowing(book_id=second_book)

        assert len(default_hints) == 1
        assert len(second_hints) == 1
        assert default_hints[0]["description"] == "默认伏笔"
        assert second_hints[0]["description"] == "副本伏笔"
