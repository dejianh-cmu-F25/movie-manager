# Movie Manager starter workflow

This v1 project is a Codex skill with bundled scripts. It intentionally does not run a persistent MCP service. When the workflow becomes stable, an MCP server can wrap the same scripts and preserve the same confirmation behavior.

## Flow

1. User asks to search a movie or TV show.
2. Codex fetches the provider pages.
3. Codex extracts normalized candidates.
4. Codex sorts candidates with shared deterministic ranking.
5. Codex presents an ID-based choice list.
6. User chooses IDs.
7. Codex resolves magnet links for only the selected candidates.
8. The system magnet handler opens Quark. The helper waits for Quark's `资源解析` window and confirms `高速下载` for each selected task.

For 美剧粉, `scripts/search_mjf2020.py` currently combines page fetching and extraction in one provider-specific script. For future providers, Codex may use AI extraction to produce the same normalized candidate JSON, then pass it through `scripts/sort_candidates.py`.

## 美剧粉 search

The search script returns JSON with candidates. Each candidate should include as many of these fields as the page exposes:

- title and alternate title
- IMDb ID
- year
- season and episode
- resolution
- codec
- release group or release label
- embedded subtitle flag
- size
- detail URL
- magnet URL or transferable link when visible

Default to complete-season / 合集 search. Apply the max-size filter first; default max size is `50G`, and candidates larger than that are hidden unless the user explicitly changes or disables the limit. For each series/season, show only one candidate: the largest candidate under the max-size limit, using quality as a tiebreaker. Sort complete-season candidates globally by quality preference first, then season number ascending, then size descending. If an episode is specified, rank exact episode matches first and prefer single-episode candidates. Never auto-select.

Quality preference defaults to `2160p`. Examples:

- `highest` / `best` / `max`: prefer the highest detected resolution.
- `2160p` / `4k`: prefer 4K candidates.
- `1080p`: prefer 1080p candidates.
- `720p`: prefer 720p candidates.

Size preference defaults to `50G`. Examples:

- `50G` / `50GB`: hide candidates larger than 50GB.
- `unlimited`: disable max-size filtering when explicitly requested.

Present sorted candidates directly in Codex chat and wait for the user to choose IDs. Do not generate HTML selection pages in v1.

## Future provider search

For new search pages, use the same normalized candidate shape described in `references/ai_extraction_schema.md`.

1. Fetch or open the provider page.
2. Use AI extraction to convert visible search/detail results into normalized candidate JSON.
3. Run `scripts/sort_candidates.py` on that JSON.
4. Present the sorted IDs to the user in Codex chat.
5. When the user chooses candidates, run `scripts/select_magnets.py` to resolve selected magnet links.
6. To download them immediately, run `scripts/select_magnets.py <results.json> <ids...> --open`. It calls `scripts/open_magnets.applescript`, which opens each magnet sequentially and uses `scripts/confirm_quark_download.swift` to click Quark's `高速下载` button.

This keeps ranking deterministic while allowing extraction to adapt to different provider layouts.

Release preference examples:

- `complete`: prefer 合集 / complete-season candidates. This is the default.
- `episode`: prefer single-episode candidates. Use when the user names a specific episode or asks for 单集.

## Future MCP evolution

Later MCP tools should mirror the skill workflow:

- `search_media`
- `confirm_media`
- `search_subtitles`
- `confirm_subtitle`
- `prepare_library_item`
- `inspect_subtitle`
- `transform_subtitle`
- `play_media`

Keep the script-first implementation as the behavioral source of truth until the integrations are stable.
