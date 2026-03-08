"""OpenAI-compatible client behavior tests."""

from __future__ import annotations

from poiesis.llm.openai_client import OpenAIClient


class _FakeDelta:
    def __init__(self, content: str | None = None, reasoning_content: str | None = None) -> None:
        self.content = content
        self.reasoning_content = reasoning_content


class _FakeChoice:
    def __init__(self, *, message=None, delta=None) -> None:
        self.message = message
        self.delta = delta


class _FakeMessage:
    def __init__(self, content: str | None = None, reasoning_content: str | None = None) -> None:
        self.content = content
        self.reasoning_content = reasoning_content


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message=message)]


class _FakeChunk:
    def __init__(self, delta: _FakeDelta) -> None:
        self.choices = [_FakeChoice(delta=delta)]


class _FakeCompletionsAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return [
                _FakeChunk(_FakeDelta(reasoning_content="推")),
                _FakeChunk(_FakeDelta(reasoning_content="理")),
            ]
        return _FakeResponse(_FakeMessage(content=None, reasoning_content="仅推理文本"))


class _FakeChatAPI:
    def __init__(self) -> None:
        self.completions = _FakeCompletionsAPI()


class _FakeOpenAIClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.chat = _FakeChatAPI()


def test_openai_complete_falls_back_to_reasoning_content(monkeypatch):
    fake_client = _FakeOpenAIClient()

    def fake_openai_ctor(**kwargs):
        return fake_client

    monkeypatch.setattr("poiesis.llm.openai_client.OpenAI", fake_openai_ctor)

    client = OpenAIClient(model="x", api_key="k", request_timeout=20)
    result = client.complete("hello")

    assert result == "仅推理文本"


def test_openai_stream_complete_falls_back_to_reasoning_content(monkeypatch):
    fake_client = _FakeOpenAIClient()

    def fake_openai_ctor(**kwargs):
        return fake_client

    monkeypatch.setattr("poiesis.llm.openai_client.OpenAI", fake_openai_ctor)

    client = OpenAIClient(model="x", api_key="k", request_timeout=20)
    chunks = list(client.stream_complete("hello"))

    assert chunks == ["推", "理"]
