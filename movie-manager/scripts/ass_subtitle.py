#!/usr/bin/env python3
"""Inspect and safely transform Advanced SubStation Alpha subtitles."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CJK_RE = re.compile(
    "[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]"
)
CJK_PUNCT_RE = re.compile(r"[，。！？；：、‘’“”【】《》（）〈〉…—～]+")
LATIN_RE = re.compile(r"[A-Za-z]")
TAG_RE = re.compile(r"\{[^}]*\}")


def read_text(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    encodings = ("utf-16", "utf-8") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8",)
    for encoding in encodings:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    raise ValueError(f"Unsupported text encoding for {path}; convert from the known source encoding first")


def dialogue_parts(line: str) -> tuple[list[str], str] | None:
    if not line.lstrip().lower().startswith("dialogue:"):
        return None
    prefix, payload = line.split(":", 1)
    fields = payload.lstrip().split(",", 9)
    if len(fields) != 10:
        return None
    return [prefix + ": ", *fields[:9]], fields[9]


def english_only_text(text: str) -> str:
    kept: list[str] = []
    for segment in re.split(r"(\\N|\\n)", text):
        if segment in (r"\N", r"\n"):
            if kept and kept[-1] not in (r"\N", r"\n"):
                kept.append(segment)
            continue
        cleaned = CJK_RE.sub("", segment)
        cleaned = CJK_PUNCT_RE.sub("", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
        visible = TAG_RE.sub("", cleaned).strip()
        if LATIN_RE.search(visible):
            kept.append(cleaned)
    while kept and kept[-1] in (r"\N", r"\n"):
        kept.pop()
    return "".join(kept)


def transform(text: str, english_only: bool) -> tuple[str, dict[str, int]]:
    output: list[str] = []
    stats = {"dialogue_total": 0, "dialogue_written": 0, "dialogue_removed": 0}
    for line in text.splitlines():
        parsed = dialogue_parts(line)
        if not parsed:
            output.append(line)
            continue
        stats["dialogue_total"] += 1
        head, payload = parsed
        if english_only:
            payload = english_only_text(payload)
        if not TAG_RE.sub("", payload).strip():
            stats["dialogue_removed"] += 1
            continue
        output.append(head[0] + ",".join(head[1:]) + "," + payload)
        stats["dialogue_written"] += 1
    return "\n".join(output) + "\n", stats


def inspect(path: Path) -> dict[str, object]:
    text, encoding = read_text(path)
    dialogue = [line for line in text.splitlines() if dialogue_parts(line)]
    return {
        "path": str(path.resolve()),
        "encoding": encoding,
        "dialogue_events": len(dialogue),
        "events_with_chinese": sum(bool(CJK_RE.search(line)) for line in dialogue),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("input", type=Path)
    transform_parser = commands.add_parser("transform")
    transform_parser.add_argument("input", type=Path)
    transform_parser.add_argument("output", type=Path)
    transform_parser.add_argument("--english-only", action="store_true")
    args = parser.parse_args()

    if args.command == "inspect":
        print(json.dumps(inspect(args.input), ensure_ascii=False, indent=2))
        return 0

    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must differ; preserve the original")
    text, source_encoding = read_text(args.input)
    rendered, stats = transform(text, args.english_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(json.dumps({"source_encoding": source_encoding, "output_encoding": "utf-8", **stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
