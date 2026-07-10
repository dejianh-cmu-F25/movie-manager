import tempfile
import unittest
from pathlib import Path

from ass_subtitle import english_only_text, inspect, transform


HEADER = """[Script Info]
Title: Test 中文 metadata
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


class AssSubtitleTests(unittest.TestCase):
    def test_removes_chinese_line_and_retains_english(self):
        source = HEADER + (
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好\\NHello!\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,只有中文。\n"
        )
        result, stats = transform(source, english_only=True)
        self.assertIn("Hello!", result)
        self.assertNotIn("你好", result)
        self.assertNotIn("只有中文", result)
        self.assertIn("Title: Test 中文 metadata", result)
        self.assertEqual(stats["dialogue_removed"], 1)

    def test_retains_english_from_mixed_segment(self):
        self.assertEqual(english_only_text("Hello 你好， world!"), "Hello world!")

    def test_reads_utf16_and_reports_chinese(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.ass"
            path.write_text(HEADER + "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,你好\n", encoding="utf-16")
            report = inspect(path)
            self.assertEqual(report["encoding"], "utf-16")
            self.assertEqual(report["events_with_chinese"], 1)


if __name__ == "__main__":
    unittest.main()
