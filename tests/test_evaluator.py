import unittest
from pathlib import Path
from unittest.mock import patch

from tools.evaluator import evaluate
from tools.models import Job


ROOT = Path(__file__).parents[1]
CV_PATH = str(ROOT / "data" / "master_cv.md")


def job(title: str, description: str) -> Job:
    return Job(title=title, company="Empresa de prueba", description=description, url="https://example.com")


class EvaluatorSelectionTests(unittest.TestCase):
    def test_data_engineer_offer_selects_data_profile(self) -> None:
        offer = job(
            "Data Engineer",
            "Python, SQL, ETL, pipelines de datos y Microsoft Fabric para una plataforma analítica.",
        )

        with patch("tools.evaluator._llm_selection", side_effect=RuntimeError("Ollama apagado")):
            evaluation = evaluate(offer, CV_PATH)

        self.assertEqual(Path(evaluation.selected_cv_path).name, "BrandonCabra_CV_DATA ENGINEER.md")
        self.assertEqual(evaluation.selection_method, "local-fallback")
        self.assertGreaterEqual(evaluation.score, 70)

    def test_qa_offer_selects_qa_profile(self) -> None:
        offer = job(
            "QA Tester",
            "Pruebas funcionales y exploratorias, casos de prueba, accesibilidad web, Jira y criterios de aceptación.",
        )

        with patch("tools.evaluator._llm_selection", side_effect=RuntimeError("Ollama apagado")):
            evaluation = evaluate(offer, CV_PATH)

        self.assertEqual(Path(evaluation.selected_cv_path).name, "BrandonCabra_CV_ANALISTA_QA.md")
        self.assertEqual(evaluation.selection_method, "local-fallback")

    def test_devops_offer_selects_devops_profile(self) -> None:
        offer = job(
            "DevOps Engineer",
            "Buscamos experiencia en Docker, AWS, CI/CD, GitHub Actions y automatización de despliegues.",
        )

        with patch("tools.evaluator._llm_selection", side_effect=RuntimeError("Ollama apagado")):
            evaluation = evaluate(offer, CV_PATH)

        self.assertEqual(
            Path(evaluation.selected_cv_path).name,
            "BrandonCabra_CV_DEVOPS ENGINEER.md",
        )

    def test_cloud_offer_selects_cloud_profile(self) -> None:
        offer = job(
            "Cloud Engineer",
            "Administración de AWS, Docker, Azure, CI/CD y despliegue de aplicaciones en la nube.",
        )

        with patch("tools.evaluator._llm_selection", side_effect=RuntimeError("Ollama apagado")):
            evaluation = evaluate(offer, CV_PATH)

        self.assertEqual(
            Path(evaluation.selected_cv_path).name,
            "BrandonCabra_CV_CLOUD ENGINEER_CLOUD DEVELOPER.md",
        )

    def test_full_stack_offer_selects_full_stack_profile(self) -> None:
        offer = job(
            "Full Stack Developer",
            "Desarrollo con Java, JavaScript, APIs REST, MySQL, Docker y AWS.",
        )

        with patch("tools.evaluator._llm_selection", side_effect=RuntimeError("Ollama apagado")):
            evaluation = evaluate(offer, CV_PATH)

        self.assertEqual(
            Path(evaluation.selected_cv_path).name,
            "BrandonCabra_CV_FULL STACK DEVELOPER.md",
        )

    def test_unrelated_offer_does_not_get_accepted_by_default(self) -> None:
        offer = job(
            "Abogado corporativo",
            "Se requiere experiencia en litigios, contratos mercantiles, derecho societario y negociación.",
        )

        with patch("tools.evaluator._llm_selection", side_effect=RuntimeError("Ollama apagado")):
            evaluation = evaluate(offer, CV_PATH)

        self.assertEqual(evaluation.score, 0)
        self.assertEqual(evaluation.matched_skills, [])

    def test_valid_ollama_selection_is_used(self) -> None:
        offer = job("Data Engineer", "Python, SQL y Microsoft Fabric.")

        with patch(
            "tools.evaluator._llm_selection",
            return_value=("BrandonCabra_CV_DATA ENGINEER.md", 0.94),
        ):
            evaluation = evaluate(offer, CV_PATH)

        self.assertEqual(Path(evaluation.selected_cv_path).name, "BrandonCabra_CV_DATA ENGINEER.md")
        self.assertEqual(evaluation.selection_method, "ollama")
        self.assertEqual(evaluation.selection_confidence, 0.94)


if __name__ == "__main__":
    unittest.main()
