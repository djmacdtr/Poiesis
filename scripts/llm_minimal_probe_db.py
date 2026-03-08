"""Minimal SiliconFlow/OpenAI-compatible probe using DB-backed config.

Purpose:
- Verify provider/model/key resolution from system_config.
- Verify whether response is truly missing or just timing out.
- Print both content and reasoning_content for diagnosis.

Usage examples:
  python scripts/llm_minimal_probe_db.py
  python scripts/llm_minimal_probe_db.py --stream --timeout 300 --max-tokens 180
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from openai import OpenAI

from poiesis.config import Config, load_config
from poiesis.db.database import Database


def _read_db_config(db: Database, key: str) -> str | None:
    raw = db.get_system_config(key)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _resolve_db_path(db_arg: str | None) -> tuple[str, Config, str]:
    cfg_path = os.environ.get("POIESIS_CONFIG", "config.yaml")
    cfg = load_config(cfg_path)
    return (db_arg or cfg.database.path), cfg, cfg_path


def _resolve_runtime_settings(db_path: str, cfg: Config) -> dict[str, Any]:
    db = Database(db_path)
    db.initialize_schema()
    try:
        llm_provider = (_read_db_config(db, "llm_provider") or cfg.llm.provider).lower()
        llm_model = _read_db_config(db, "llm_model") or cfg.llm.model
        llm_base_url = cfg.llm.base_url

        # Import lazily so this script still runs if API package import chain changes.
        from poiesis.api.services.system_config_service import get_decrypted_key

        openai_key = get_decrypted_key(db, "OPENAI_API_KEY")
        siliconflow_key = get_decrypted_key(db, "SILICONFLOW_API_KEY")

        if llm_provider == "siliconflow":
            api_key = siliconflow_key
            base_url = llm_base_url or "https://api.siliconflow.cn/v1"
        elif llm_provider == "openai":
            api_key = openai_key or os.environ.get("OPENAI_API_KEY")
            base_url = llm_base_url
        else:
            raise RuntimeError(
                f"Unsupported provider for this probe: {llm_provider}. "
                "Use openai or siliconflow."
            )

        return {
            "provider": llm_provider,
            "model": llm_model,
            "base_url": base_url,
            "api_key": api_key,
            "has_siliconflow_key": bool(siliconflow_key),
            "db_path": db_path,
        }
    finally:
        db.close()


def _extract_message_fields(resp: Any) -> tuple[str, str]:
    msg = resp.choices[0].message
    content = (getattr(msg, "content", None) or "").strip()
    reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
    return content, reasoning


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal DB-backed LLM probe")
    parser.add_argument(
        "--db",
        default=None,
        help="SQLite DB path. If omitted, uses database.path from POIESIS_CONFIG/config.yaml",
    )
    parser.add_argument("--timeout", type=float, default=300.0, help="HTTP timeout seconds")
    parser.add_argument("--max-tokens", type=int, default=180, help="max_tokens")
    parser.add_argument("--temperature", type=float, default=0.7, help="temperature")
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model override for A/B speed comparison",
    )
    parser.add_argument("--stream", action="store_true", help="Use stream mode")
    parser.add_argument(
        "--prompt",
        default="Write a vivid fantasy scene in about 100 Chinese characters. Output prose only.",
        help="Prompt text",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path, cfg, cfg_path = _resolve_db_path(args.db)
    settings = _resolve_runtime_settings(db_path, cfg)

    provider = settings["provider"]
    model = args.model or settings["model"]
    base_url = settings["base_url"]
    api_key = settings["api_key"]

    print(f"provider={provider}")
    print(f"model={model}")
    print(f"base_url={base_url}")
    print(f"config_path={cfg_path}")
    print(f"db_path={settings['db_path']}")
    print(f"has_siliconflow_key={settings['has_siliconflow_key']}")

    if not api_key:
        print("ERROR: resolved api_key is empty", file=sys.stderr)
        return 2

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=args.timeout)

    messages = [{"role": "user", "content": args.prompt}]

    # Provider-specific optional fields can be rejected by older OpenAI SDK versions.
    extra: dict[str, Any] = {}

    start = time.time()

    if args.stream:
        print("STREAM_BEGIN")
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                stream=True,
                **extra,
            )
        except TypeError:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                stream=True,
            )

        chunks: list[str] = []
        first_chunk_sec: float | None = None
        for event in stream:
            if not getattr(event, "choices", None):
                continue
            delta = event.choices[0].delta
            content = getattr(delta, "content", None)
            reasoning = getattr(delta, "reasoning_content", None)

            text_piece = content or reasoning or ""
            if text_piece:
                if first_chunk_sec is None:
                    first_chunk_sec = time.time() - start
                chunks.append(text_piece)
                print(text_piece, end="", flush=True)

        elapsed = time.time() - start
        print("\nSTREAM_END")
        print(f"FIRST_CHUNK_SEC={first_chunk_sec if first_chunk_sec is not None else -1:.3f}")
        print(f"ELAPSED_SEC={elapsed:.3f}")
        print(f"TEXT_LEN={len(''.join(chunks))}")
        return 0

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            **extra,
        )
    except TypeError:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    elapsed = time.time() - start

    content, reasoning = _extract_message_fields(resp)
    combined = content if content else reasoning

    print(f"ELAPSED_SEC={elapsed:.3f}")
    print(f"CONTENT_LEN={len(content)}")
    print(f"REASONING_LEN={len(reasoning)}")
    print("TEXT_BEGIN")
    print(combined)
    print("TEXT_END")

    # Emit a compact JSON blob for machine parsing if needed.
    print("META_JSON=" + json.dumps({
        "provider": provider,
        "model": model,
        "elapsed_sec": elapsed,
        "content_len": len(content),
        "reasoning_len": len(reasoning),
    }, ensure_ascii=True))

    return 0 if combined else 3


if __name__ == "__main__":
    raise SystemExit(main())
