import tempfile
import unittest
from pathlib import Path

from tools.sources.computrabajo import parse_computrabajo_html
from tools.sources.linkedin_import import load_linkedin_import


class SourceAdapterTests(unittest.TestCase):
    def test_computrabajo_parser_normalizes_public_card(self) -> None:
        html = """
        <article class="box_offer">
          <h2><a href="/ofertas-de-trabajo/oferta-1">Data Engineer</a></h2>
          <div class="company">Acme</div>
          <div class="location">Bogotá</div>
          <div class="description">Python y SQL</div>
        </article>
        """
        jobs = parse_computrabajo_html(html, "https://co.computrabajo.com/trabajo", 5)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Data Engineer")
        self.assertEqual(jobs[0].source, "computrabajo")
        self.assertTrue(jobs[0].url.endswith("/ofertas-de-trabajo/oferta-1"))

    def test_linkedin_import_reads_csv_without_automating_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "linkedin.csv"
            path.write_text(
                "title,company,description,url,location\n"
                "Software Developer,Acme,Python,https://linkedin.example/1,Remote\n",
                encoding="utf-8",
            )

            jobs = load_linkedin_import(path)

        self.assertEqual(jobs[0].source, "linkedin-import")
        self.assertEqual(jobs[0].company, "Acme")


if __name__ == "__main__":
    unittest.main()
