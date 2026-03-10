"""世界状态领域模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from poiesis.domain.world.repository import WorldRepository

if TYPE_CHECKING:
    from poiesis.db.database import Database


class WorldModel:
    """维护 canon / staging / archive 以及后续可扩展的故事状态。"""

    def __init__(self) -> None:
        self.canon: dict[str, Any] = {
            "characters": {},
            "world_rules": {},
            "timeline": {},
            "foreshadowing": {},
        }
        self.staging: list[dict[str, Any]] = []
        self.archive: list[dict[str, Any]] = []
        self.story_state: dict[str, Any] = {}
        self.loop_state: list[dict[str, Any]] = []
        # WorldModel 只持有当前使用的仓储实例，便于把持久化协调继续隔离在领域对象外。
        self._repository: WorldRepository | None = None

    def list_loops(self) -> list[dict[str, Any]]:
        """返回当前内存中的 loop 列表。"""
        return list(self.loop_state)

    def get_loop(self, loop_id: str) -> dict[str, Any] | None:
        """按 loop_id 查询单条线索状态。"""
        for item in self.loop_state:
            if item.get("loop_id") == loop_id:
                return item
        return None

    def active_loop_ids(self) -> list[str]:
        """返回当前仍需关注的剧情线索 ID。"""
        return [
            str(item.get("loop_id"))
            for item in self.loop_state
            if item.get("status") not in {"resolved", "dropped"}
        ]

    def upsert_loop(self, loop: dict[str, Any]) -> None:
        """同步更新内存中的 loop 状态。"""
        existing = self.get_loop(str(loop.get("loop_id") or ""))
        if existing is None:
            self.loop_state.append(dict(loop))
            return
        existing.update(loop)

    def set_story_state(self, story_state: dict[str, Any]) -> None:
        """替换当前故事状态摘要。"""
        self.story_state = dict(story_state)

    def load_from_db(
        self,
        db: Database,
        book_id: int = 1,
        repository: WorldRepository | None = None,
    ) -> None:
        """通过仓储层装载世界状态。"""
        repo = repository or WorldRepository()
        self._repository = repo
        snapshot = repo.load_world_state(db, book_id=book_id)
        self.canon = dict(snapshot.get("canon") or self.canon)
        self.staging = list(snapshot.get("staging") or [])
        self.archive = list(snapshot.get("archive") or [])
        self.story_state = dict(snapshot.get("story_state") or {})
        self.loop_state = list(snapshot.get("loop_state") or [])

    def propose_change(self, change: dict[str, Any]) -> None:
        """把候选变更加入 staging 层。"""
        required = {"change_type", "entity_type", "entity_key", "proposed_data"}
        missing = required - change.keys()
        if missing:
            raise ValueError(f"Change dict missing required keys: {missing}")
        self.staging.append(change)

    def approve_change(self, change_id: int, db: Database) -> None:
        """批准一条 staging 变更并同步更新内存 canon。"""
        repo = self._repository or WorldRepository()
        change = repo.get_staging_change(db, change_id)
        if change is None:
            raise ValueError(f"Staging change {change_id} not found")
        if change["status"] != "pending":
            raise ValueError(
                f"Cannot approve change {change_id}: status is '{change['status']}'"
            )

        repo.mark_staging_approved(db, change_id)
        self._apply_to_canon(change)
        self.staging = [s for s in self.staging if s.get("id") != change_id]

    def reject_change(self, change_id: int, reason: str, db: Database) -> None:
        """拒绝一条 staging 变更并归档。"""
        repo = self._repository or WorldRepository()
        change = repo.get_staging_change(db, change_id)
        if change is None:
            raise ValueError(f"Staging change {change_id} not found")
        if change["status"] != "pending":
            raise ValueError(
                f"Cannot reject change {change_id}: status is '{change['status']}'"
            )

        updated = repo.mark_staging_rejected(db, change_id, reason)
        self.archive.append(updated or change)
        self.staging = [s for s in self.staging if s.get("id") != change_id]

    def _apply_to_canon(self, change: dict[str, Any]) -> None:
        """把批准后的变更应用到内存中的 canon。"""
        entity_type: str = change["entity_type"]
        entity_key: str = change["entity_key"]
        data: dict[str, Any] = change["proposed_data"]

        layer_map = {
            "character": "characters",
            "world_rule": "world_rules",
            "timeline_event": "timeline",
            "foreshadowing": "foreshadowing",
        }
        layer = layer_map.get(entity_type)
        if layer is None:
            return

        if change["change_type"] == "delete":
            self.canon[layer].pop(entity_key, None)
        else:
            existing = self.canon[layer].get(entity_key, {})
            existing.update(data)
            self.canon[layer][entity_key] = existing

    def get_immutable_rules(self) -> list[dict[str, Any]]:
        """返回全部不可变规则。"""
        return [r for r in self.canon["world_rules"].values() if r.get("is_immutable")]

    def world_context_summary(self, max_rules: int = 20, language: str = "zh-CN") -> str:
        """构建供 prompt 使用的世界上下文摘要。"""
        lines: list[str] = []
        zh_mode = language.lower().startswith("zh")

        rule_title = "=== 世界规则 ===" if zh_mode else "=== World Rules ==="
        chars_title = "\n=== 角色设定 ===" if zh_mode else "\n=== Characters ==="
        timeline_title = "\n=== 时间线 ===" if zh_mode else "\n=== Timeline ==="
        hint_title = "\n=== 待回收伏笔 ===" if zh_mode else "\n=== Pending Foreshadowing ==="
        story_title = "\n=== 当前故事状态 ===" if zh_mode else "\n=== Story State ==="
        loop_title = "\n=== 剧情线索 ===" if zh_mode else "\n=== Narrative Loops ==="
        immutable_tag = "【不可变】" if zh_mode else " [IMMUTABLE]"
        motivation_label = "动机" if zh_mode else "motivation"
        unknown_label = "未知" if zh_mode else "unknown"

        rules = list(self.canon["world_rules"].values())[:max_rules]
        if rules:
            lines.append(rule_title)
            for rule in rules:
                immutable = immutable_tag if rule.get("is_immutable") else ""
                lines.append(f"- {rule.get('rule_key', '')}{immutable}: {rule.get('description', '')}")

        chars = list(self.canon["characters"].values())
        if chars:
            lines.append(chars_title)
            for char in chars:
                lines.append(
                    f"- {char.get('name', '')}: {char.get('description', '')} "
                    f"({motivation_label}: {char.get('core_motivation', unknown_label)})"
                )

        events = list(self.canon["timeline"].values())
        if events:
            lines.append(timeline_title)
            for event in events:
                lines.append(
                    f"- [{event.get('timestamp_in_world', '?')}] {event.get('description', '')}"
                )

        hints = [h for h in self.canon["foreshadowing"].values() if h.get("status") == "pending"]
        if hints:
            lines.append(hint_title)
            for hint in hints:
                lines.append(f"- {hint.get('hint_key', '')}: {hint.get('description', '')}")

        if self.story_state:
            lines.append(story_title)
            lines.append(
                f"- {'最近已发布章节' if zh_mode else 'Last published chapter'}: "
                f"{self.story_state.get('last_published_chapter', 0)}"
            )
            lines.append(
                f"- {'当前活动章节' if zh_mode else 'Active chapter'}: "
                f"{self.story_state.get('active_chapter', 1)}"
            )
            recent_scene_refs = list(self.story_state.get("recent_scene_refs") or [])
            if recent_scene_refs:
                label = "最近场景" if zh_mode else "Recent scenes"
                lines.append(f"- {label}: {', '.join(str(item) for item in recent_scene_refs)}")

        active_loops = [
            loop
            for loop in self.loop_state
            if loop.get("status") not in {"resolved", "dropped"}
        ]
        if active_loops:
            lines.append(loop_title)
            for loop in active_loops[:10]:
                due = loop.get("due_window") or unknown_label
                lines.append(
                    f"- {loop.get('loop_id', '')}: {loop.get('title', '')} "
                    f"[{loop.get('status', '')}] ({'回收窗口' if zh_mode else 'due'}: {due})"
                )

        return "\n".join(lines)
