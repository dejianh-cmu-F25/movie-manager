#!/usr/bin/env python3
"""Search 美剧粉 and return structured movie/TV release candidates as JSON.

This script is intentionally read-only: it fetches and parses pages, but never
downloads media and never chooses a candidate automatically.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from candidates import (
    Candidate,
    CandidateError,
    assign_candidate_ids,
    collapse_variants,
    filter_by_max_size,
    normalize_quality,
    normalize_release_mode,
    parse_int,
    rank_candidates,
    resolution_score,
    to_jsonable,
)

DEFAULT_BASE_URL = "https://www.mjf2020.com"
USER_AGENT = "MovieManagerSkill/0.1 (+local personal Codex skill)"

try:
    import certifi  # type: ignore
except ImportError:  # pragma: no cover - optional runtime improvement
    certifi = None


class SearchError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Anchor:
    href: str
    text: str


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[Anchor] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._href = attrs_dict.get("href") or ""
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = clean_text(" ".join(self._parts))
            if self._href and text:
                self.anchors.append(Anchor(self._href, text))
            self._href = None
            self._parts = []


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def strip_tags(html: str) -> str:
    parser = TextParser()
    parser.feed(html)
    return clean_text(" ".join(parser.parts))


def fetch(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            data = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return data.decode(encoding, errors="replace")
    except urllib.error.HTTPError as error:
        raise SearchError("source_unavailable", f"美剧粉 returned HTTP {error.code}: {url}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise SearchError("source_unavailable", f"美剧粉 unavailable: {url}") from error


def find_token(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return clean_text(match.group(1)) if match else None


def parse_anchors(html: str) -> list[Anchor]:
    parser = LinkParser()
    parser.feed(html)
    return parser.anchors


def parse_search_results(html: str, base_url: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for anchor in parse_anchors(html):
        href = urllib.parse.urljoin(base_url, anchor.href)
        if "/jianjie/" not in href or href in seen:
            continue
        seen.add(href)
        results.append({"title": anchor.text, "url": href})
    return results


def page_title(html: str) -> str:
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if h1:
        return strip_tags(h1.group(1))
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title:
        return re.split(r"[-_|]", strip_tags(title.group(1)), 1)[0].strip() or "Unknown"
    return "Unknown"


def anchor_contexts(html: str, detail_url: str) -> list[tuple[str, str, str]]:
    contexts: list[tuple[str, str, str]] = []
    pattern = re.compile(r"<a\b[^>]*href=[\"']?([^\"'>\s]+)[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
    blocks = re.split(r"<hr\b[^>]*>", html, flags=re.IGNORECASE)
    seen: set[tuple[str, str, str]] = set()
    for block in blocks:
        if not re.search(r"href=[\"']?(?:https?://[^\"'>\s]+)?/(?:bt|xiazai)/", block, re.IGNORECASE):
            continue
        for match in pattern.finditer(block):
            href = urllib.parse.urljoin(detail_url, unescape(match.group(1)))
            if "/bt/" not in href and "/xiazai/" not in href and not href.startswith(("magnet:", "ed2k:", "thunder:")):
                continue
            label = strip_tags(match.group(2))
            context = strip_tags(block)
            key = (href, label, context)
            if key not in seen:
                seen.add(key)
                contexts.append(key)
    if contexts:
        return contexts
    for match in pattern.finditer(html):
        href = urllib.parse.urljoin(detail_url, unescape(match.group(1)))
        label = strip_tags(match.group(2))
        window = html[max(0, match.start() - 280): min(len(html), match.end() + 280)]
        context = strip_tags(window)
        contexts.append((href, label, context))
    return contexts


def parse_detail(html: str, detail_url: str, preferences: dict[str, Any]) -> list[Candidate]:
    text = strip_tags(html)
    title = page_title(html)
    alternate_title = find_token(text, r"英文名字[:：]\s*([^级别类型]+?)\s+(?:级别|类型)[:：]")
    imdb_id = find_token(text, r"IMDB[:：]\s*(tt\d+)")
    year = parse_int(find_token(text, r"(?:首播|年份|上映)[:：]\s*(\d{4})"))
    wanted_season = parse_int(preferences.get("season"))
    wanted_episode = parse_int(preferences.get("episode"))
    wanted_year = parse_int(preferences.get("year"))
    wanted_quality = normalize_quality(preferences.get("quality"))
    release_mode = normalize_release_mode(preferences.get("release_mode"), wanted_episode)

    candidates: list[Candidate] = []
    for href, label, context in anchor_contexts(html, detail_url):
        local = label or context
        fallback = context
        season = parse_int(
            find_token(local, r"S(\d{1,2})")
            or find_token(local, r"第(\d{1,2})季")
            or find_token(fallback, r"S(\d{1,2})")
            or find_token(fallback, r"第(\d{1,2})季")
        )
        episode = parse_int(
            find_token(local, r"E(\d{1,3})")
            or find_token(local, r"第\d{1,2}季[- ]*第(\d{1,3})集")
            or find_token(fallback, r"E(\d{1,3})")
            or find_token(fallback, r"第\d{1,2}季[- ]*第(\d{1,3})集")
        )
        resolution = find_token(local, r"\b(2160p?|1080p?|720p?|480p?)\b") or find_token(fallback, r"\b(2160p?|1080p?|720p?|480p?)\b")
        codec = find_token(local, r"\b(x26[45]|h[._ ]?26[45]|HEVC|AV1)\b") or find_token(fallback, r"\b(x26[45]|h[._ ]?26[45]|HEVC|AV1)\b")
        size = find_token(local, r"([\d.]+\s*(?:GiB|MiB|GB|MB))") or find_token(fallback, r"([\d.]+\s*(?:GiB|MiB|GB|MB))")
        release_group = find_token(local, r"-([A-Za-z0-9.]+)(?:\s|\[|\(|$)") or find_token(fallback, r"-([A-Za-z0-9.]+)(?:\s|\[|\(|$)")
        resource_like = (
            href.startswith(("magnet:", "ed2k:", "thunder:"))
            or "/xiazai/" in href
            or bool(season or episode or resolution)
        )
        if not resource_like:
            continue

        score = 0
        reasons: list[str] = []
        if wanted_year and year == wanted_year:
            score += 1000
            reasons.append("year match")
        if wanted_season is not None and season == wanted_season:
            score += 4000
            reasons.append("season match")
        if wanted_episode is not None and episode == wanted_episode:
            score += 8000
            reasons.append("episode match")
        candidate_quality = resolution_score(resolution)
        if wanted_quality == "highest":
            score += candidate_quality // 10
            if candidate_quality:
                reasons.append("highest quality preference")
        elif resolution and normalize_quality(resolution) == wanted_quality:
            score += 500
            reasons.append("quality match")
        complete_source = local or fallback
        complete_season = "合集" in complete_source or "COMPLETE" in complete_source.upper()
        if complete_season:
            episode = None
        if release_mode == "complete" and complete_season:
            score += 3000
            reasons.append("complete season preference")
        elif release_mode == "episode" and not complete_season:
            score += 1000
            reasons.append("single episode preference")
        if complete_season:
            reasons.append("complete season")

        candidates.append(Candidate(
            id="",
            source="mjf2020",
            title=title,
            alternate_title=alternate_title,
            imdb_id=imdb_id,
            year=year,
            season=season,
            episode=episode,
            complete_season=complete_season,
            resolution=resolution,
            codec=codec,
            release_group=release_group,
            release=label or context[:100],
            embedded_subtitles="内嵌中文字幕" in context or "中字" in context,
            size=size,
            detail_url=detail_url,
            download_url=href,
            score=score,
            match_reasons=reasons,
        ))
    return candidates


def search(query: str, preferences: dict[str, Any], base_url: str, max_pages: int, limit: int) -> list[Candidate]:
    search_url = f"{base_url.rstrip('/')}/ss/?s={urllib.parse.quote(query)}"
    search_html = fetch(search_url)
    pages = parse_search_results(search_html, base_url)
    if not pages:
        raise SearchError("no_match", f"No 美剧粉 detail pages found for {query!r}")

    candidates: list[Candidate] = []
    complete_mode = (
        normalize_release_mode(preferences.get("release_mode"), parse_int(preferences.get("episode"))) == "complete"
        and parse_int(preferences.get("episode")) is None
    )
    for page in pages[:max_pages]:
        detail_html = fetch(page["url"])
        parsed = filter_by_max_size(parse_detail(detail_html, page["url"], preferences), preferences)
        page_candidates = collapse_variants(parsed, preferences)
        candidates.extend(page_candidates)

    if complete_mode and any(candidate.complete_season for candidate in candidates):
        candidates = [candidate for candidate in candidates if candidate.complete_season]

    if not candidates:
        raise SearchError("no_match", f"No release candidates found for {query!r}")

    return rank_candidates(candidates, preferences, limit)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Movie or TV title to search")
    parser.add_argument("--year", type=int)
    parser.add_argument("--season", type=int)
    parser.add_argument("--episode", type=int)
    parser.add_argument("--quality", default="2160p", help="Preferred quality, e.g. 1080p; default: 2160p")
    parser.add_argument("--max-size", default="50G", help="Maximum candidate size; default: 50G; use unlimited to disable")
    parser.add_argument("--release-mode", choices=["auto", "complete", "episode"], default="complete", help="Prefer complete seasons/collections by default; use episode for single episodes")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--limit", type=int, default=50, help="Maximum candidates to print")
    parser.add_argument("--fixture-detail", type=Path, help="Parse a saved detail HTML fixture instead of live search")
    parser.add_argument("--detail-url", default=DEFAULT_BASE_URL + "/fixture/jianjie/0.html")
    args = parser.parse_args()

    preferences = {
        "year": args.year,
        "season": args.season,
        "episode": args.episode,
        "quality": args.quality,
        "max_size": args.max_size,
        "release_mode": args.release_mode,
    }
    try:
        if args.fixture_detail:
            html = args.fixture_detail.read_text(encoding="utf-8")
            parsed = filter_by_max_size(parse_detail(html, args.detail_url, preferences), preferences)
            candidates = rank_candidates(collapse_variants(parsed, preferences), preferences, args.limit)
        else:
            candidates = search(args.query, preferences, args.base_url, args.max_pages, args.limit)
        print(json.dumps({
            "ok": True,
            "source": "mjf2020",
            "query": args.query,
            "candidates": to_jsonable(candidates),
        }, ensure_ascii=False, indent=2))
        return 0
    except (SearchError, CandidateError) as error:
        print(json.dumps({
            "ok": False,
            "error": {"code": error.code, "message": error.message},
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
