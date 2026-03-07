"""Run service preflight validation tests."""

from __future__ import annotations

from poiesis.api.services.run_service import _validate_llm_key_prerequisites


class _Cfg:
    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model


class _Config:
    def __init__(self, llm: _Cfg, planner_llm: _Cfg) -> None:
        self.llm = llm
        self.planner_llm = planner_llm


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
