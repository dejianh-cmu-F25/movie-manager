---
name: movie-manager
description: Search 美剧粉 for movie and TV release candidates, present ID-based choices in Codex chat, trigger the user's macOS magnet handler with AppleScript after selection, search or prepare ASS subtitles, organize local media/subtitle files, transform ASS subtitles, and play unambiguous matches in VLC. Use whenever the user asks to find, prepare, edit, sync, inspect, organize, or play a movie or TV episode. This starter skill is script-first and does not run an MCP service.
---

# Movie Manager

Use this as a script-first Codex skill. Keep the conversation as the user interface. Run bundled scripts only when they help produce deterministic search or subtitle results.

There is intentionally no active MCP server in v1. Do not look for `movie_manager` MCP tools. Future MCP work should wrap the proven scripts rather than changing the user workflow.

## Media search

Canonical search flow:

1. Fetch the provider search/detail pages.
2. Extract normalized candidates with fixed fields: ID, title, season, episode, resolution, size, release, detail URL, download URL, and magnet URL when available.
3. Sort candidates with the shared ranking rules.
4. Present a numbered/ID-based choice list to the user.
5. After the user chooses IDs, take the corresponding magnet links and run AppleScript to open them with macOS's registered magnet handler. On this macOS setup, wait for Quark's `资源解析` window and automatically click `高速下载` for each selected magnet.

Current 美剧粉 implementation:

- `scripts/search_mjf2020.py` is the 美剧粉-specific extractor. It performs steps 1 and 2 internally, then reuses the shared candidate sorting logic.
- For future providers, use AI extraction to produce the same normalized candidate JSON, then run `scripts/sort_candidates.py`.
- Do not automatically choose a result. Ask the user to choose one or more IDs, or provide feedback for a refined search.
- If the scraper reports `source_unavailable`, `layout_changed`, or `no_match`, explain the failure and offer direct page ingestion as the fallback.

Searching does not authorize opening magnet links. By default, present choices only in Codex chat. After the user selects IDs, the AppleScript helper opens only those magnet links and confirms Quark's `高速下载` action. This requires Accessibility and Screen Recording permission for the ChatGPT app.

## Multi-provider extraction model

Keep provider scraping and candidate ranking separate. For 美剧粉, `scripts/search_mjf2020.py` performs both extraction and sorting. For future provider pages, use AI extraction to produce the normalized schema in `references/ai_extraction_schema.md`, then run `scripts/sort_candidates.py` to apply the same quality, season, and size ordering.

The normalized fields are: ID, source, title, alternate title, IMDb ID, year, season, episode, complete-season flag, resolution, codec, release group, release label, embedded-subtitle flag, size, detail URL, download URL, magnet URL, score, and match reasons.

After sorting, Codex should present the candidates directly in chat and ask the user to choose IDs. When the selected candidates contain magnet links, Codex can open them with:

```bash
osascript scripts/open_magnets.applescript '<magnet-1>' '<magnet-2>'
```

The helper handles magnets sequentially. For each magnet it waits up to 20 seconds for Quark's `资源解析` window, validates the window size, clicks the blue `高速下载` button using a window-relative native mouse event, and verifies that the dialog closes before continuing. Treat any timeout or unexpected window size as a failure; do not retry by clicking arbitrary coordinates.

If the candidates only contain provider download/detail URLs, resolve magnets only after the user chooses IDs:

```bash
python3 scripts/select_magnets.py search-results.json 1 2 5
python3 scripts/select_magnets.py search-results.json 1 2 5 --open
```

## User preferences

- Video quality preference defaults to `2160p`.
- If the user says they prefer `4k`, `2160p`, `1080p`, `720p`, or another specific quality, pass it with `--quality`.
- If no quality is mentioned, omit `--quality` or pass `--quality 2160p`.
- Maximum size preference defaults to `50G`. For each season, show only the largest candidate under this limit. Pass `--max-size 50G`; use `--max-size unlimited` only if the user explicitly removes the limit.
- Release preference defaults to `complete`, meaning searches should prefer 合集 / complete-season candidates over single episodes.
- Default complete-season results show one candidate per season: the largest candidate under the max-size limit. Results are then sorted by quality preference first, then season number ascending, then size descending.
- If the user asks for a specific episode, pass `--episode <N>` and `--release-mode episode`.
- If the user explicitly asks for 单集 / single episode, pass `--release-mode episode`.
- Treat the preference as ranking guidance, not automatic selection; still present candidates for confirmation.

Example:

```bash
python3 scripts/search_mjf2020.py "Brooklyn Nine-Nine" --season 6 --quality 2160p --max-size 50G --release-mode complete
```

## Subtitle workflow

- Search or inspect ASS subtitles only after the user has chosen the media release.
- Prefer ASS subtitles that match title/year/season/episode first, then release tokens, runtime, and frame rate when available.
- V1 accepts `.ass` subtitles only. Do not download archives or convert SRT, VTT, or SSA unless the user explicitly changes the scope.
- Preserve subtitle content by default. English-only filtering, timing shifts, style changes, and manual edits require an explicit user request.

## Playback and subtitles

- Use `scripts/ass_subtitle.py inspect <file.ass>` before editing.
- Use `scripts/ass_subtitle.py transform <input.ass> <output.ass>` for UTF-8 normalization.
- Add `--english-only` only when the user explicitly requests removing Chinese dialogue.
- Keep originals recoverable; write transformed subtitles to a new path.
- Launch VLC directly only when the intended media/subtitle pair is unambiguous. Otherwise present choices.
