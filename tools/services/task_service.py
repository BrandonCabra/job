import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from tools.services.job_service import JobService
from tools.storage import create_task, get_task, load_tasks, update_task


_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job-agent")


class TaskService:
    def __init__(self, root: str | Path, job_service: JobService | None = None):
        self.root = Path(root)
        self.job_service = job_service or JobService(self.root)
        self.database = self.job_service.database

    def enqueue(self, task_type: str, job_id: str) -> str:
        task_id = uuid4().hex
        create_task(self.database, task_id, task_type, job_id)
        try:
            _EXECUTOR.submit(self._run, task_id, task_type, job_id)
        except RuntimeError as exc:
            update_task(self.database, task_id, "failed", error=str(exc))
            raise RuntimeError("No fue posible encolar la tarea") from exc
        return task_id

    def _run(self, task_id: str, task_type: str, job_id: str) -> None:
        try:
            update_task(self.database, task_id, "running")
            job = self.job_service.find(job_id)
            if job is None:
                raise ValueError("Oferta no encontrada")
            evaluation = self.job_service.evaluate(job)
            result = {
                "job_id": job_id,
                "score": evaluation.score,
                "matched_skills": evaluation.matched_skills,
                "missing_skills": evaluation.missing_skills,
                "selection_method": evaluation.selection_method,
            }
            if task_type == "documents":
                cv, letter = self.job_service.generate_documents(job, evaluation)
                result.update(
                    cv_path=cv,
                    cover_letter_path=letter,
                    pdf_path=str(Path(cv).with_suffix(".pdf")),
                )
            elif task_type != "evaluation":
                raise ValueError(f"Tipo de tarea no soportado: {task_type}")
            update_task(self.database, task_id, "completed", result=result)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            update_task(self.database, task_id, "failed", error=str(exc))

    def get(self, task_id: str):
        return get_task(self.database, task_id)

    def resume_pending(self) -> int:
        resumed = 0
        for row in load_tasks(self.database, limit=100):
            if row["status"] in {"queued", "running"}:
                try:
                    _EXECUTOR.submit(self._run, row["id"], row["task_type"], row["job_id"])
                except RuntimeError:
                    continue
                resumed += 1
        return resumed
