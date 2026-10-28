import os
import unittest
from unittest.mock import Mock, patch

from tools.scraper import search_jsearch


class ScraperApiTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "JSEARCH_API_KEY": "test-key",
            "JSEARCH_HOST": "jsearch-mega.p.rapidapi.com",
            "JSEARCH_ENDPOINT": "search",
            "JSEARCH_QUERY_SUFFIX": "junior",
        },
    )
    @patch("requests.get")
    def test_uses_configured_rapidapi_host(self, get: Mock) -> None:
        get.return_value.ok = True
        get.return_value.json.return_value = {"data": []}

        search_jsearch("Data Engineer", "Colombia")

        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://jsearch-mega.p.rapidapi.com/search")
        self.assertEqual(kwargs["headers"]["X-RapidAPI-Host"], "jsearch-mega.p.rapidapi.com")
        self.assertEqual(kwargs["params"]["country"], "us")
        self.assertEqual(kwargs["params"]["query"], "Data Engineer junior Colombia")
        self.assertEqual(kwargs["params"]["date_posted"], "all")
        self.assertEqual(kwargs["params"]["language"], "en")

    @patch.dict(os.environ, {"JSEARCH_API_KEY": "test-key"})
    @patch("requests.get")
    def test_exposes_provider_error(self, get: Mock) -> None:
        get.return_value.ok = False
        get.return_value.status_code = 404
        get.return_value.json.return_value = {"message": "Endpoint does not exist"}

        with self.assertRaisesRegex(RuntimeError, "Endpoint does not exist"):
            search_jsearch("Data Engineer")


if __name__ == "__main__":
    unittest.main()
