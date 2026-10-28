import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.crm_logger import log_application
from tools.models import ApplicationRecord, Job


class CrmLoggerTests(unittest.TestCase):
    def test_csv_contains_document_audit_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "base.md"
            pdf = root / "adapted.pdf"
            source.write_text("# CV\n", encoding="utf-8")
            pdf.write_bytes(b"%PDF-test")
            record = ApplicationRecord(
                Job("Junior Developer", "Acme", "Python", "https://example.test/job"),
                86,
                "Pendiente",
                "Revisar",
                str(root / "adapted.md"),
                "",
                {"selected_cv": str(source), "pdf_path": str(pdf)},
            )

            with patch.dict("os.environ", {"NOTION_ENABLED": "false"}):
                log_application(record, str(root / "applications.csv"))

            with (root / "applications.csv").open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["company"], "Acme")
            self.assertEqual(len(row["source_cv_sha256"]), 64)
            self.assertEqual(len(row["pdf_sha256"]), 64)
            self.assertEqual(row["pdf_path"], str(pdf))
            self.assertTrue(row["pdf_url"].startswith("file://"))


if __name__ == "__main__":
    unittest.main()
