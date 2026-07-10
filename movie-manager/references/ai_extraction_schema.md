# AI extraction schema

Use this schema when extracting candidates from any provider page. The extractor should return JSON only:

```json
{
  "provider": "provider-name",
  "query": "user query",
  "candidates": [
    {
      "id": "",
      "source": "provider-name",
      "title": "Chinese or local title",
      "alternate_title": "English/original title if present",
      "imdb_id": "tt0000000",
      "year": 2022,
      "season": 1,
      "episode": null,
      "complete_season": true,
      "resolution": "2160p",
      "codec": "HEVC",
      "release_group": "NTb",
      "release": "full release label",
      "embedded_subtitles": false,
      "size": "22.33 GB",
      "detail_url": "https://...",
      "download_url": "https://... or magnet:...",
      "magnet_url": "magnet:?xt=urn:btih:...",
      "score": 0,
      "match_reasons": []
    }
  ]
}
```

Extraction rules:

- Preserve the provider's text; do not invent missing fields.
- Normalize booleans and numbers when clear.
- Use `complete_season: true` for 合集, COMPLETE, season packs, or full-season bundles.
- Use `episode: null` for complete-season candidates.
- Extract size exactly as shown, such as `49GB`, `22.33 GB`, or `760 MiB`.
- Prefer direct `magnet_url` when visible. If only a detail/download page is visible, put it in `download_url`.
- Leave `id` empty; the deterministic sorter assigns opaque IDs.

After extraction, run:

```bash
python3 scripts/sort_candidates.py extracted.json
```

Codex should present the sorted candidates in chat and ask the user to choose IDs. After the user chooses, Codex can run:

```bash
osascript scripts/open_magnets.applescript '<magnet-1>' '<magnet-2>'
```
