import unittest
from unittest.mock import patch

from tools import daily_run


class DailyRunTests(unittest.TestCase):
    @patch("tools.daily_run.process_jobs")
    @patch("tools.daily_run.fetch", return_value=[])
    def test_does_not_process_historical_catalog_when_no_new_jobs(self, fetch, process_jobs) -> None:
        daily_run.main()

        fetch.assert_called_once()
        process_jobs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
