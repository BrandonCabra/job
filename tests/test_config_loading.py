import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import fetch_jobs


class ConfigLoadingTests(unittest.TestCase):
    @patch("tools.fetch_jobs.fetch_and_store", return_value=[])
    def test_project_env_overrides_stale_shell_values(self, fetch_and_store) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "JSEARCH_LOCATION=Colombia\nJOB_SOURCES=jsearch\nJOB_RSS_FEEDS=\n",
                encoding="utf-8",
            )
            with patch.object(fetch_jobs, "__file__", str(root / "tools" / "fetch_jobs.py")):
                with patch.dict(
                    os.environ,
                    {"JSEARCH_LOCATION": "Spain", "JOB_SOURCES": "jsearch,rss"},
                    clear=False,
                ):
                    fetch_jobs.fetch()

        self.assertEqual(fetch_and_store.call_args.args[2], "Colombia")
        self.assertEqual(fetch_and_store.call_args.args[4], [])


if __name__ == "__main__":
    unittest.main()
