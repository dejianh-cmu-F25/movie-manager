import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "search_mjf2020.py"


class SearchMjf2020Tests(unittest.TestCase):
    def run_fixture(self, html, *args):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "detail.html"
            fixture.write_text(html, encoding="utf-8")
            completed = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "Brooklyn Nine-Nine",
                    *args,
                    "--fixture-detail",
                    str(fixture),
                    "--detail-url",
                    "https://www.mjf2020.com/jianjie/123.html",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        return json.loads(completed.stdout)

    def test_parse_detail_fixture(self):
        html = """
        <html><body>
          <h1>神烦警探 Brooklyn Nine-Nine 第六季</h1>
          <p>英文名字: Brooklyn Nine-Nine 级别: 普通 IMDB: tt2467372 首播: 2019</p>
          <div>
            <a href="/xiazai/abc.html">第6季-第1集 1080P WEB-DL x264-NTb (1.20GB) 内嵌中文字幕</a>
          </div>
          <div>
            <a href="/xiazai/def.html">第6季-第2集 720P HDTV x264-GROUP (600MB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html, "--season", "6", "--episode", "1", "--quality", "1080p")
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload["candidates"]), 2)
        best = payload["candidates"][0]
        self.assertEqual(best["season"], 6)
        self.assertEqual(best["episode"], 1)
        self.assertEqual(best["resolution"], "1080P")
        self.assertIn("episode match", best["match_reasons"])
        self.assertEqual(best["imdb_id"], "tt2467372")

    def test_default_quality_prefers_2160p(self):
        html = """
        <html><body>
          <h1>神烦警探 Brooklyn Nine-Nine 第六季</h1>
          <p>英文名字: Brooklyn Nine-Nine 级别: 普通 IMDB: tt2467372 首播: 2019</p>
          <div>
            <a href="/xiazai/low.html">第6季-第1集 720P WEB-DL x264-GROUP (600MB)</a>
          </div>
          <div>
            <a href="/xiazai/high.html">第6季-第1集 2160P WEB-DL x265-GROUP (4.2GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html, "--season", "6", "--episode", "1")
        best = payload["candidates"][0]
        self.assertEqual(best["resolution"], "2160P")
        self.assertIn("quality match", best["match_reasons"])

    def test_specific_quality_preference_overrides_highest(self):
        html = """
        <html><body>
          <h1>神烦警探 Brooklyn Nine-Nine 第六季</h1>
          <p>英文名字: Brooklyn Nine-Nine 级别: 普通 IMDB: tt2467372 首播: 2019</p>
          <div>
            <a href="/xiazai/high.html">第6季-第1集 2160P WEB-DL x265-GROUP (4.2GB)</a>
          </div>
          <div>
            <a href="/xiazai/mid.html">第6季-第1集 1080P WEB-DL x264-GROUP (1.2GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html, "--season", "6", "--episode", "1", "--quality", "1080p")
        best = payload["candidates"][0]
        self.assertEqual(best["resolution"], "1080P")
        self.assertIn("quality match", best["match_reasons"])

    def test_default_release_mode_prefers_complete_season(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/episode.html">第9季-第7集 2160P WEB-DL x265-GROUP (2.2GB)</a>
          </div>
          <div>
            <a href="/xiazai/season.html">第9季合集- 1080P WEB-DL x265-GROUP (8.8GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html, "--season", "9")
        best = payload["candidates"][0]
        self.assertTrue(best["complete_season"])
        self.assertIn("complete season preference", best["match_reasons"])

    def test_episode_release_mode_prefers_single_episode(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/season.html">第9季合集- 2160P WEB-DL x265-GROUP (22GB)</a>
          </div>
          <div>
            <a href="/xiazai/episode.html">第9季-第7集 1080P WEB-DL x264-GROUP (1.2GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html, "--season", "9", "--episode", "7", "--release-mode", "episode")
        best = payload["candidates"][0]
        self.assertFalse(best["complete_season"])
        self.assertEqual(best["episode"], 7)
        self.assertIn("single episode preference", best["match_reasons"])

    def test_default_complete_results_sort_by_season_ascending(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s1.html">第1季合集- 2160P WEB-DL x265-GROUP (22GB)</a>
          </div>
          <div>
            <a href="/xiazai/s3.html">第3季合集- 1080P WEB-DL x264-GROUP (8GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2.html">第2季合集- 2160P WEB-DL x265-GROUP (18GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        seasons = [candidate["season"] for candidate in payload["candidates"][:3]]
        self.assertEqual(seasons, [1, 2, 3])

    def test_default_complete_results_sort_quality_before_season(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s3.html">第3季合集- 2160P WEB-DL x265-GROUP (30GB)</a>
          </div>
          <div>
            <a href="/xiazai/s1.html">第1季合集- 720P WEB-DL x264-GROUP (3GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2.html">第2季合集- 1080P WEB-DL x264-GROUP (8GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        seasons = [candidate["season"] for candidate in payload["candidates"][:3]]
        resolutions = [candidate["resolution"] for candidate in payload["candidates"][:3]]
        self.assertEqual(resolutions, ["2160P", "1080P", "720P"])
        self.assertEqual(seasons, [3, 2, 1])

    def test_default_complete_results_sort_season_inside_same_quality(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s3.html">第3季合集- 2160P WEB-DL x265-GROUP (30GB)</a>
          </div>
          <div>
            <a href="/xiazai/s1.html">第1季合集- 2160P WEB-DL x264-GROUP (3GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2.html">第2季合集- 2160P WEB-DL x264-GROUP (8GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        seasons = [candidate["season"] for candidate in payload["candidates"][:3]]
        self.assertEqual(seasons, [1, 2, 3])

    def test_default_complete_results_keep_largest_under_limit_per_season(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s2-low.html">第2季合集- 720P WEB-DL x264-GROUP (4GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2-high.html">第2季合集- 2160P WEB-DL x265-GROUP (22GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        candidates = payload["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["season"], 2)
        self.assertEqual(candidates[0]["size"], "22GB")

    def test_default_complete_results_keep_one_largest_same_quality_variant(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s2-small.html">第2季合集- 2160P WEB-DL x265-GROUP (8GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2-large.html">第2季合集- 2160P WEB-DL x265-GROUP (22GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        candidates = payload["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["size"], "22GB")
        self.assertTrue(candidates[0]["download_url"].endswith("/xiazai/s2-large.html"))

    def test_default_max_size_filters_candidates_over_50g(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s2-huge.html">第2季合集- 2160P WEB-DL x265-GROUP (80GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2-ok.html">第2季合集- 2160P WEB-DL x265-GROUP (22GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        candidates = payload["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["size"], "22GB")
        self.assertTrue(candidates[0]["download_url"].endswith("/xiazai/s2-ok.html"))

    def test_unlimited_max_size_keeps_large_candidates(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s2-huge.html">第2季合集- 2160P WEB-DL x265-GROUP (80GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2-ok.html">第2季合集- 2160P WEB-DL x265-GROUP (22GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html, "--max-size", "unlimited")
        candidates = payload["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["size"], "80GB")

    def test_largest_under_limit_beats_smaller_preferred_quality(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/s2-2160.html">第2季合集- 2160P WEB-DL x265-GROUP (22GB)</a>
          </div>
          <div>
            <a href="/xiazai/s2-1080.html">第2季合集- 1080P WEB-DL x264-GROUP (49GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        candidates = payload["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["size"], "49GB")
        self.assertEqual(candidates[0]["resolution"], "1080P")

    def test_default_complete_results_exclude_single_episodes_when_complete_exists(self):
        html = """
        <html><body>
          <h1>瑞克和莫蒂 Rick and Morty</h1>
          <p>英文名字: Rick and Morty 级别: 普通 IMDB: tt2861424 首播: 2013</p>
          <div>
            <a href="/xiazai/e7.html">第9季-第7集 2160P WEB-DL x265-GROUP (2GB)</a>
          </div>
          <div>
            <a href="/xiazai/s9.html">第9季合集- 1080P WEB-DL x264-GROUP (9GB)</a>
          </div>
        </body></html>
        """
        payload = self.run_fixture(html)
        self.assertEqual(len(payload["candidates"]), 1)
        self.assertTrue(payload["candidates"][0]["complete_season"])
        self.assertIsNone(payload["candidates"][0]["episode"])

if __name__ == "__main__":
    unittest.main()
