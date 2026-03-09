"""Anthropic client behavior tests."""

from __future__ import annotations

from poiesis.llm.anthropic_client import AnthropicClient


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessageResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeBlock(text)]


class _FakeStream:
    def __init__(self, chunks: list[str]) -> None:
        self.text_stream = chunks

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get_final_message(self) -> _FakeMessageResponse:
        return _FakeMessageResponse("".join(self.text_stream))


class _FakeMessagesAPI:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.stream_calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _FakeMessageResponse("完整响应")

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return _FakeStream(["流", "式", "输出"])


class _FakeAnthropicClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.messages = _FakeMessagesAPI()


def test_anthropic_client_reads_timeout_from_env(monkeypatch):
    captured: dict[str, object] = {}

    def fake_anthropic_ctor(**kwargs):
        captured.update(kwargs)
        return _FakeAnthropicClient(**kwargs)

    monkeypatch.setenv("POIESIS_LLM_TIMEOUT_SEC", "45")
    monkeypatch.setattr("poiesis.llm.anthropic_client.anthropic.Anthropic", fake_anthropic_ctor)

    AnthropicClient(model="claude-test")

    assert captured["timeout"] == 45.0


def test_anthropic_stream_complete_yields_incremental_chunks(monkeypatch):
    fake_client = _FakeAnthropicClient()

    def fake_anthropic_ctor(**kwargs):
        return fake_client

    monkeypatch.setattr("poiesis.llm.anthropic_client.anthropic.Anthropic", fake_anthropic_ctor)

    client = AnthropicClient(model="claude-test", api_key="anth-key", request_timeout=30)
    chunks = list(client.stream_complete("hello", system="sys"))

    assert chunks == ["流", "式", "输出"]
    assert len(fake_client.messages.stream_calls) == 1
    stream_kwargs = fake_client.messages.stream_calls[0]
    assert stream_kwargs["model"] == "claude-test"
    assert stream_kwargs["system"] == "sys"
    assert stream_kwargs["messages"] == [{"role": "user", "content": "hello"}]
