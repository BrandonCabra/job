import os
import unittest
from unittest.mock import Mock, patch

from tools.sources.rapidapi_jobs import search_rapidapi_jobs


class RapidApiSourceTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "JSEARCH_API_KEY": "test-key",
            "FACEBOOK_RAPIDAPI_HOST": "facebook.example",
            "FACEBOOK_RAPIDAPI_ENDPOINT": "search",
            "FACEBOOK_RAPIDAPI_RESPONSE_PATH": "results",
            "FACEBOOK_RAPIDAPI_PARAMS_JSON": '{"country":"co"}',
        },
    )
    @patch("requests.get")
    def test_normalizes_configured_response(self, get: Mock) -> None:
        get.return_value.ok = True
        get.return_value.json.return_value = {
            "results": [{"id": "1", "title": "Junior Developer", "company": "Acme"}]
        }

        jobs = search_rapidapi_jobs("FACEBOOK", ["developer"], "Colombia", 5)

        self.assertEqual(jobs[0].title, "Junior Developer")
        self.assertEqual(jobs[0].source, "facebook")
        self.assertEqual(get.call_args.kwargs["params"]["country"], "co")


if __name__ == "__main__":
    unittest.main()
