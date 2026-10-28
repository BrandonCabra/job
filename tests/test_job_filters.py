import os
import unittest
from unittest.mock import Mock, patch

from tools.scraper import search_jsearch


class JobFilterTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "JSEARCH_API_KEY": "test-key",
            "JSEARCH_COUNTRY": "co",
            "JSEARCH_LANGUAGE": "es",
            "JSEARCH_EXCLUDE_SENIORITY": "senior,lead",
        },
    )
    @patch("requests.get")
    def test_filters_foreign_and_senior_results(self, get: Mock) -> None:
        get.return_value.ok = True
        get.return_value.json.return_value = {
            "data": [
                {
                    "job_id": "co-junior",
                    "job_title": "Data Engineer Junior",
                    "job_description": "Python y SQL",
                    "job_country": "co",
                    "job_location": "Bogotá, Colombia",
                },
                {
                    "job_id": "es-senior",
                    "job_title": "Data Engineer Senior",
                    "job_description": "Python y SQL",
                    "job_country": "es",
                    "job_location": "Madrid, España",
                },
            ]
        }

        jobs = search_jsearch("Data Engineer", "Colombia")

        self.assertEqual([job.external_id for job in jobs], ["co-junior"])
