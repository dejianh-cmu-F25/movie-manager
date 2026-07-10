#!/usr/bin/env python3
"""Sort normalized Movie Manager candidates from JSON.

Input JSON may be either:
  {"candidates": [...]} or [...]

This is provider-agnostic. AI extractors for future sites should emit the same
candidate fields, then pipe the result through this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from candidates import Candidate, collapse_variants, filter_by_max_size, rank_candidates, to_jsonable


def load_candidates(path: Path) -> tuple[dict[str, Any], list[Candidate]]:
    payload = json.loads(path.read_text(encoding="utf-8") if path != Path("-") else sys.stdin.read())
    wrapper = payload if isinstance(payload, dict) else {}
    rows = payload.get("candidates", []) if isinstance(payload, dict) else payload
    candidates: list[Candidate] = []
    for row in rows:
        value = dict(row)
        value.setdefault("id", "")
        value.setdefault("source", value.get("provider") or "unknown")
        allowed = {field: value[field] for field in Candidate.__dataclass_fields__ if field in value}
        candidates.append(Candidate(**allowed))
    return wrapper, candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input candidate JSON, or - for stdin")
    parser.add_argument("--quality", default="2160p")
    parser.add_argument("--max-size", default="50G")
    parser.add_argument("--release-mode", choices=["auto", "complete", "episode"], default="complete")
    parser.add_argument("--episode", type=int)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    wrapper, candidates = load_candidates(args.input)
    preferences = {
        "quality": args.quality,
        "max_size": args.max_size,
        "release_mode": args.release_mode,
        "episode": args.episode,
    }
    filtered = filter_by_max_size(candidates, preferences)
    collapsed = collapse_variants(filtered, preferences)
    ranked = rank_candidates(collapsed, preferences, args.limit)
    output = {**wrapper, "candidates": to_jsonable(ranked)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
