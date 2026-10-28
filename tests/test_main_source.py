import os
import unittest
from unittest.mock import patch

from tools.models import Job
from tools import scraper
import main


class MainSourceTests(unittest.TestCase):
    @patch("main.evaluate")
    @patch("main.log_application")
    @patch("main.search_jobs")
    def test_local_source_does_not_query_jsearch(self, search_jobs, log_application, evaluate) -> None:
        evaluate.return_value.score = 0
        evaluate.return_value.matched_skills = []
        evaluate.return_value.missing_skills = []
        evaluate.return_value.rationale = ""
        evaluate.return_value.selected_cv_path = ""
        evaluate.return_value.selection_method = "local"
        evaluate.return_value.selection_confidence = 1.0
        job = Job("Junior Developer", "Acme", "Python", "https://example.test/job")

        with patch.dict(os.environ, {"JOB_SOURCE": "local", "MIN_COMPATIBILITY": "70"}):
            with patch.object(scraper, "load_local_jobs", return_value=[job]):
                main.run()

        search_jobs.assert_called_once()
        self.assertEqual(search_jobs.call_args.args[0], "local")


if __name__ == "__main__":
    unittest.main()
