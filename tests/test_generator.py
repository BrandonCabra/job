import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.generator import _experience_lines, generate_documents
from tools.models import Evaluation, Job


class GeneratorTests(unittest.TestCase):
    def test_reads_middle_dot_bullets(self) -> None:
        cv = "EXPERIENCIA\n· Usar Python y SQL.\n- Usar Docker.\n"

        bullets = _experience_lines(cv, ["python"])

        self.assertEqual(bullets, ["· Usar Python y SQL."])

    def test_generates_markdown_and_pdf_from_selected_cv(self) -> None:
        cv = (
            "BRANDON CABRA\nBogotá, Colombia\nemail@example.com\n\n"
            "PERFIL PROFESIONAL\nDesarrollador de software.\n\n"
            "EXPERIENCIA PROFESIONAL\n"
            "Empresa Test — Backend Developer\n"
            "· Construir APIs REST con Java y MySQL.\n\n"
            "EDUCACIÓN\nIngeniería de Software — En curso\n"
        )
        job = Job("Backend Developer", "Test Co", "Java, APIs REST y MySQL.", "https://example.com")
        evaluation = Evaluation(
            score=100,
            matched_skills=["java", "apis rest", "mysql"],
            selected_cv_path="selected.md",
        )

        with tempfile.TemporaryDirectory() as directory:
            cv_path = Path(directory) / "selected.md"
            cv_path.write_text(cv, encoding="utf-8")
            with (
                patch("tools.generator._rewrite_profile", side_effect=lambda job, cv, profile, evaluation: profile),
                patch("tools.generator._rewrite_bullets", side_effect=lambda job, cv, bullets, evaluation: bullets),
            ):
                generated_cv, _ = generate_documents(job, str(cv_path), evaluation, directory)

            output = Path(generated_cv)
            generated_text = output.read_text(encoding="utf-8")
            self.assertIn("## Experiencia Profesional", generated_text)
            self.assertIn("· Construir APIs REST con Java y MySQL.", generated_text)
            self.assertIn("## Educación", generated_text)
            self.assertTrue(output.with_suffix(".pdf").exists())
            self.assertTrue(output.with_suffix(".html").exists())
            self.assertIn("font-family: Arial", output.with_suffix(".html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
