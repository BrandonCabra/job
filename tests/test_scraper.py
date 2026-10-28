import tempfile
import unittest
from pathlib import Path

from tools.models import Job
from tools.scraper import merge_jobs, save_jobs, load_local_jobs


class ScraperTests(unittest.TestCase):
    def test_merge_deduplicates_by_external_id_and_preserves_existing(self) -> None:
        existing = [Job("Data Engineer", "Acme", "old", "https://jobs/1", external_id="1")]
        incoming = [
            Job("Data Engineer", "Acme", "new description", "https://jobs/1", external_id="1"),
            Job("QA Tester", "Quality", "testing", "https://jobs/2", external_id="2"),
        ]

        merged = merge_jobs(existing, incoming, limit=50)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].description, "old")

    def test_jobs_json_round_trip_preserves_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.json"
            job = Job("Software Developer", "Acme", "Java", "https://jobs/1", source="jsearch", external_id="x")
            save_jobs(path, [job])

            loaded = load_local_jobs(path)

        self.assertEqual(loaded[0].external_id, "x")
        self.assertEqual(loaded[0].source, "jsearch")

    def test_merge_applies_catalog_limit(self) -> None:
        incoming = [
            Job(f"Software Developer {index}", "Company", "Python", f"https://jobs/{index}", external_id=str(index))
            for index in range(60)
        ]

        self.assertEqual(len(merge_jobs([], incoming, limit=50)), 50)


if __name__ == "__main__":
    unittest.main()
