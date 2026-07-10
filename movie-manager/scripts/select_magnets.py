#!/usr/bin/env python3
"""Resolve magnet links for selected Movie Manager candidates.

Input is a search result JSON object containing a ``candidates`` array.
Selections may be candidate IDs, such as ``mjf_001``, or 1-based display
positions, such as ``1``.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

USER_AGENT = "MovieManagerSkill/0.1 (+local personal Codex skill)"

try:
    import certifi  # type: ignore
except ImportError:  # pragma: no cover - optional runtime improvement
    certifi = None


class SelectionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def fetch(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            data = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return data.decode(encoding, errors="replace")
    except urllib.error.HTTPError as error:
        raise SelectionError("source_unavailable", f"Download page returned HTTP {error.code}: {url}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise SelectionError("source_unavailable", f"Download page unavailable: {url}") from error


def resolve_magnet(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("magnet:"):
        return value
    text = fetch(value)
    match = re.search(r"magnet:\?xt=urn:[^\"'<>\\s]+", text)
    return unescape(match.group(0)) if match else None


def load_payload(path: Path) -> dict[str, Any]:
    text = sys.stdin.read() if path == Path("-") else path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise SelectionError("invalid_input", "Input must be an object with a candidates array")
    return payload


def choose(candidates: list[dict[str, Any]], selections: list[str]) -> list[dict[str, Any]]:
    by_id = {str(candidate.get("id")): candidate for candidate in candidates if candidate.get("id")}
    selected: list[dict[str, Any]] = []
    for selection in selections:
        candidate: dict[str, Any] | None = None
        if selection in by_id:
            candidate = by_id[selection]
        elif selection.isdigit():
            index = int(selection) - 1
            if 0 <= index < len(candidates):
                candidate = candidates[index]
        if candidate is None:
            raise SelectionError("invalid_selection", f"Unknown selection: {selection}")
        if candidate not in selected:
            selected.append(candidate)
    return selected


def open_magnets(script: Path, magnets: list[str]) -> None:
    subprocess.run(["osascript", str(script), *magnets], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Search result JSON file, or - for stdin")
    parser.add_argument("selection", nargs="+", help="Candidate IDs or 1-based positions")
    parser.add_argument("--open", action="store_true", help="Open selected magnets with AppleScript")
    parser.add_argument("--script", type=Path, default=Path(__file__).with_name("open_magnets.applescript"))
    args = parser.parse_args()

    try:
        payload = load_payload(args.input)
        selected = choose(payload["candidates"], args.selection)
        output = []
        for candidate in selected:
            magnet = candidate.get("magnet_url") or resolve_magnet(candidate.get("download_url"))
            if not magnet:
                raise SelectionError("no_magnet", f"No magnet found for {candidate.get('id') or candidate.get('title')}")
            item = dict(candidate)
            item["magnet_url"] = magnet
            output.append(item)
        if args.open:
            open_magnets(args.script, [item["magnet_url"] for item in output])
        print(json.dumps({"ok": True, "selected": output}, ensure_ascii=False, indent=2))
        return 0
    except (SelectionError, subprocess.CalledProcessError) as error:
        code = getattr(error, "code", "open_failed")
        message = getattr(error, "message", str(error))
        print(json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
