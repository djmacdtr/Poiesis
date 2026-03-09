"""Run service preflight validation tests."""

from __future__ import annotations

from poiesis.api.services import run_service
from poiesis.api.services.run_service import _validate_llm_key_prerequisites
from poiesis.api.task_registry import TaskInfo


class _Cfg:
    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model


class _Config:
    def __init__(self, llm: _Cfg, planner_llm: _Cfg) -> None:
        self.llm = llm
        self.planner_llm = planner_llm
        self.database = type("_Db", (), {"path": "poiesis.db"})()


def _make_fake_runtime_config() -> _Config:
    return _Config(
        llm=_Cfg("siliconflow", "Qwen/Qwen3-8B"),
        planner_llm=_Cfg("siliconflow", "Qwen/Qwen3-8B"),
    )


class _FakeLoop:
    def __init__(
        self,
        writer_provider: str,
        writer_model: str,
        planner_provider: str,
        planner_model: str,
        keys: dict[str, str | None],
    ) -> None:
        self._config = _Config(
            llm=_Cfg(writer_provider, writer_model),
            planner_llm=_Cfg(planner_provider, planner_model),
        )
        self._keys = keys

    def _load_key_from_db(self, key_name: str) -> str | None:
        return self._keys.get(key_name)


def test_preflight_passes_when_required_keys_exist() -> None:
    loop = _FakeLoop(
        writer_provider="siliconflow",
        writer_model="Qwen/Qwen2.5-72B-Instruct",
        planner_provider="openai",
        planner_model="gpt-4o",
        keys={
            "SILICONFLOW_API_KEY": "sf-key",
            "OPENAI_API_KEY": "oa-key",
        },
    )

    _validate_llm_key_prerequisites(loop)


def test_preflight_raises_clear_error_when_key_missing() -> None:
    loop = _FakeLoop(
        writer_provider="siliconflow",
        writer_model="Qwen/Qwen2.5-72B-Instruct",
        planner_provider="openai",
        planner_model="gpt-4o",
        keys={
            "SILICONFLOW_API_KEY": "sf-key",
            "OPENAI_API_KEY": None,
        },
    )

    try:
        _validate_llm_key_prerequisites(loop)
        assert False, "Expected ValueError for missing OPENAI_API_KEY"
    except ValueError as exc:
        message = str(exc)
        assert "模型配置校验失败" in message
        assert "规划模型（openai / gpt-4o）缺少 OPENAI_API_KEY" in message
        assert "系统设置" in message


def test_run_in_background_streams_preview_and_marks_completed(monkeypatch) -> None:
    class _FakeDB:
        def __init__(self) -> None:
            self._saved_chapters: set[int] = set()

        def list_chapters(self, book_id: int = 1):
            return []

        def mark_saved(self, chapter_number: int) -> None:
            self._saved_chapters.add(chapter_number)

        def get_chapter(self, chapter_number: int, book_id: int = 1):
            if chapter_number in self._saved_chapters:
                return {"chapter_number": chapter_number}
            return None

    class _FakeRunLoop:
        def __init__(self, config_path: str, book_id: int = 1) -> None:
            self._db = _FakeDB()
            self._config = _make_fake_runtime_config()

        def load_world_seed(self) -> None:
            return None

        def _load_key_from_db(self, key_name: str) -> str:
            return "sf-key"

        def _generate_chapter(
            self, chapter_number: int, on_writer_delta=None, on_stage=None
        ) -> None:
            if on_writer_delta is not None:
                on_writer_delta("第一段")
                on_writer_delta("第二段")
            self._db.mark_saved(chapter_number)

    monkeypatch.setattr("poiesis.run_loop.RunLoop", _FakeRunLoop)
    monkeypatch.setattr(run_service, "_validate_llm_key_prerequisites", lambda loop: None)

    task = TaskInfo(task_id="t-stream", total_chapters=1)
    run_service._run_in_background(task, config_path="config.yaml", chapter_count=1, book_id=1)

    assert task.status == "completed"
    assert task.current_chapter == 1
    assert task.preview_text == "第一段第二段"
    assert any("第 1 章完成" in line for line in task.logs)


def test_run_in_background_fails_when_chapter_not_persisted(monkeypatch) -> None:
    class _FakeDB:
        def list_chapters(self, book_id: int = 1):
            return []

        def get_chapter(self, chapter_number: int, book_id: int = 1):
            return None

    class _FakeRunLoop:
        def __init__(self, config_path: str, book_id: int = 1) -> None:
            self._db = _FakeDB()
            self._config = _make_fake_runtime_config()

        def load_world_seed(self) -> None:
            return None

        def _load_key_from_db(self, key_name: str) -> str:
            return "sf-key"

        def _generate_chapter(
            self, chapter_number: int, on_writer_delta=None, on_stage=None
        ) -> None:
            if on_writer_delta is not None:
                on_writer_delta("正文")

    monkeypatch.setattr("poiesis.run_loop.RunLoop", _FakeRunLoop)
    monkeypatch.setattr(run_service, "_validate_llm_key_prerequisites", lambda loop: None)

    task = TaskInfo(task_id="t-missing", total_chapters=1)
    run_service._run_in_background(task, config_path="config.yaml", chapter_count=1, book_id=1)

    assert task.status == "failed"
    assert task.current_chapter == 0
    assert task.error is not None
    assert "未成功写入数据库" in task.error


def test_start_run_passes_book_id_to_background_thread(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _DummyThread:
        def __init__(self, target, args, daemon: bool, name: str) -> None:
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon
            captured["name"] = name

        def start(self) -> None:
            captured["started"] = True

    def _fake_create(total_chapters: int) -> TaskInfo:
        return TaskInfo(task_id="t-book", total_chapters=total_chapters)

    monkeypatch.setattr(run_service.threading, "Thread", _DummyThread)
    monkeypatch.setattr(run_service.registry, "create", _fake_create)

    result = run_service.start_run(config_path="config.yaml", chapter_count=2, book_id=7)

    assert result["task_id"] == "t-book"
    assert captured.get("started") is True
    assert captured.get("daemon") is True
    assert captured.get("args") is not None
    args = captured["args"]
    assert isinstance(args, tuple)
    assert len(args) == 4
    assert args[1] == "config.yaml"
    assert args[2] == 2
    assert args[3] == 7
