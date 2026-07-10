from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


QUALITY_ORDER = {
    "2160": 2160,
    "2160p": 2160,
    "4k": 2160,
    "1080": 1080,
    "1080p": 1080,
    "720": 720,
    "720p": 720,
    "480": 480,
    "480p": 480,
}


class CandidateError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Candidate:
    id: str
    source: str
    title: str = "Unknown"
    alternate_title: str | None = None
    imdb_id: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    complete_season: bool = False
    resolution: str | None = None
    codec: str | None = None
    release_group: str | None = None
    release: str | None = None
    embedded_subtitles: bool = False
    size: str | None = None
    detail_url: str = ""
    download_url: str = ""
    magnet_url: str | None = None
    score: int = 0
    match_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_quality(value: Any) -> str:
    text = str(value or "2160p").strip().lower()
    if text in {"", "best", "max", "highest", "high"}:
        return "highest"
    return text.rstrip("p") if text.endswith("p") else text


def normalize_release_mode(value: Any, wanted_episode: int | None) -> str:
    text = str(value or "").strip().lower()
    if wanted_episode is not None and text in {"", "auto"}:
        return "episode"
    if text in {"", "auto", "complete", "season", "合集", "full", "collection"}:
        return "complete"
    if text in {"episode", "single", "单集"}:
        return "episode"
    return "complete"


def resolution_score(value: str | None) -> int:
    if not value:
        return 0
    return QUALITY_ORDER.get(value.strip().lower(), 0)


def size_score(value: str | None) -> float:
    if not value:
        return 0.0
    match = re.search(r"([\d.]+)\s*(GiB|MiB|GB|MB)", value, re.IGNORECASE)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = match.group(2).lower()
    if unit in {"gb", "gib"}:
        return amount * 1024
    return amount


def parse_max_size(value: Any) -> float | None:
    if value is None:
        return size_score("50GB")
    text = str(value).strip()
    if not text or text.lower() in {"none", "unlimited", "off", "no-limit"}:
        return None
    match = re.fullmatch(r"([\d.]+)\s*([GgMm](?:i?[Bb])?)?", text)
    if not match:
        raise CandidateError("invalid_preference", f"Invalid max size: {value!r}")
    amount = match.group(1)
    unit = (match.group(2) or "GB").lower()
    if unit in {"g", "gb", "gib"}:
        normalized = f"{amount}GB"
    elif unit in {"m", "mb", "mib"}:
        normalized = f"{amount}MB"
    else:
        normalized = f"{amount}GB"
    return size_score(normalized)


def parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def filter_by_max_size(candidates: list[Candidate], preferences: dict[str, Any]) -> list[Candidate]:
    maximum = parse_max_size(preferences.get("max_size"))
    if maximum is None:
        return candidates
    return [
        candidate
        for candidate in candidates
        if not candidate.size or size_score(candidate.size) <= maximum
    ]


def sort_candidates(candidates: list[Candidate], preferences: dict[str, Any]) -> list[Candidate]:
    mode = normalize_release_mode(preferences.get("release_mode"), parse_int(preferences.get("episode")))
    if mode == "complete" and parse_int(preferences.get("episode")) is None:
        return sorted(
            candidates,
            key=lambda item: (
                resolution_score(item.resolution),
                item.season is not None,
                -(item.season or 10**9),
                size_score(item.size),
                item.score,
            ),
            reverse=True,
        )
    return sorted(
        candidates,
        key=lambda item: (item.score, resolution_score(item.resolution), size_score(item.size)),
        reverse=True,
    )


def assign_candidate_ids(candidates: list[Candidate], limit: int | None = None) -> list[Candidate]:
    ranked = candidates if limit is None else candidates[:limit]
    for index, candidate in enumerate(ranked, start=1):
        prefix = re.sub(r"[^a-z0-9]+", "_", (candidate.source or "movie").lower()).strip("_") or "movie"
        if prefix == "mjf2020":
            prefix = "mjf"
        candidate.id = f"{prefix}_{index:03d}"
    return ranked


def rank_candidates(candidates: list[Candidate], preferences: dict[str, Any], limit: int | None = None) -> list[Candidate]:
    return assign_candidate_ids(sort_candidates(candidates, preferences), limit)


def collapse_variants(candidates: list[Candidate], preferences: dict[str, Any]) -> list[Candidate]:
    mode = normalize_release_mode(preferences.get("release_mode"), parse_int(preferences.get("episode")))
    if mode != "complete":
        return candidates
    groups: dict[tuple[str, int | None, int | None, bool], list[Candidate]] = {}
    passthrough: list[Candidate] = []
    for candidate in candidates:
        if not candidate.complete_season:
            passthrough.append(candidate)
            continue
        key = (candidate.detail_url, candidate.season, candidate.episode, candidate.complete_season)
        groups.setdefault(key, []).append(candidate)
    selected: list[Candidate] = []
    for group in groups.values():
        selected.append(max(
            group,
            key=lambda candidate: (
                size_score(candidate.size),
                resolution_score(candidate.resolution),
                candidate.score,
            ),
        ))
    return selected if selected else passthrough


def to_jsonable(candidates: list[Candidate]) -> list[dict[str, Any]]:
    return [candidate.to_dict() for candidate in candidates]
