import os
from pathlib import Path

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from tools.models import Job
from tools.crm_logger import export_applications_csv
from tools.services.job_service import JobService
from tools.services.task_service import TaskService
from tools.storage import (
    get_application,
    load_applications,
    load_jobs,
    migrate_csv,
    migrate_json,
    update_application_status,
)


ROOT = Path(__file__).resolve().parents[1]
DATABASE = Path(os.getenv("JOB_DB_PATH", ROOT / "data" / "jobs.db"))
if not DATABASE.is_absolute():
    DATABASE = ROOT / DATABASE
JSON_CATALOG = ROOT / "data" / "jobs.json"
SERVICE = JobService(ROOT)
TASKS = TaskService(ROOT, SERVICE)

app = FastAPI(
    title="Job Agent API",
    version="1.0.0",
    description="API local para consultar, evaluar y generar documentos de candidaturas.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("API_CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-API-Key"],
)


class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    description: str
    url: str
    location: str
    source: str
    published_at: str
    status: str

    @classmethod
    def from_job(cls, job: Job) -> "JobResponse":
        return cls(
            id=job.external_id,
            title=job.title,
            company=job.company,
            description=job.description,
            url=job.url,
            location=job.location,
            source=job.source,
            published_at=job.published_at,
            status=job.status,
        )


class EvaluationResponse(BaseModel):
    job_id: str
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    rationale: str
    selected_cv_path: str
    selection_method: str
    selection_confidence: float | None


class SearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=50, ge=1, le=50)


class DocumentsResponse(BaseModel):
    job_id: str
    cv_path: str
    cover_letter_path: str
    pdf_path: str


class TaskResponse(BaseModel):
    id: str
    task_type: str
    job_id: str
    status: str
    result: dict
    error: str
    created_at: str
    started_at: str | None
    completed_at: str | None

    @classmethod
    def from_row(cls, row) -> "TaskResponse":
        try:
            result = json.loads(row["result"] or "{}")
        except json.JSONDecodeError:
            result = {"raw": row["result"]}
        return cls(
            id=row["id"],
            task_type=row["task_type"],
            job_id=row["job_id"],
            status=row["status"],
            result=result,
            error=row["error"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )


class ApplicationResponse(BaseModel):
    id: int
    created_at: str
    job_id: str
    company: str
    title: str
    url: str
    score: int
    status: str
    step: str
    cv_path: str
    cover_letter_path: str
    details: dict

    @classmethod
    def from_row(cls, row) -> "ApplicationResponse":
        try:
            details = json.loads(row["details"] or "{}")
        except json.JSONDecodeError:
            details = {"legacy_details": row["details"]}
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            job_id=row["job_id"],
            company=row["company"],
            title=row["title"],
            url=row["url"],
            score=row["score"],
            status=row["status"],
            step=row["step"],
            cv_path=row["cv_path"],
            cover_letter_path=row["cover_letter_path"],
            details=details,
        )


class ApplicationStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=80)
    step: str | None = Field(default=None, max_length=120)


APPLICATION_STATUSES = {
    "Pendiente de confirmación",
    "Omitida",
    "Lista para automatización",
    "Enviada",
    "Rechazada",
}


@app.on_event("startup")
def initialize_storage() -> None:
    if not DATABASE.exists() and JSON_CATALOG.exists():
        migrate_json(JSON_CATALOG, DATABASE)
    migrate_csv(ROOT / "data" / "applications.csv", DATABASE)
    load_jobs(DATABASE, limit=1)
    TASKS.resume_pending()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/jobs", response_model=list[JobResponse])
def list_jobs(
    query: str | None = None,
    location: str | None = None,
    limit: int = 50,
) -> list[JobResponse]:
    limit = max(1, min(limit, 50))
    jobs = load_jobs(DATABASE, limit=50)
    query_lower = query.lower().strip() if query else ""
    location_lower = location.lower().strip() if location else ""
    filtered = [
        job for job in jobs
        if (not query_lower or query_lower in f"{job.title} {job.description}".lower())
        and (not location_lower or location_lower in job.location.lower())
    ]
    return [JobResponse.from_job(job) for job in filtered[:limit]]


@app.post("/api/v1/jobs/search", response_model=list[JobResponse])
def search_local_jobs(request: SearchRequest) -> list[JobResponse]:
    return list_jobs(request.query, request.location, request.limit)


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
def get_job_detail(job_id: str) -> JobResponse:
    job = SERVICE.find(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    return JobResponse.from_job(job)


@app.post("/api/v1/jobs/{job_id}/evaluate", response_model=EvaluationResponse)
def evaluate_job(job_id: str) -> EvaluationResponse:
    job = SERVICE.find(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    try:
        evaluation = SERVICE.evaluate(job)
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EvaluationResponse(
        job_id=job_id,
        score=evaluation.score,
        matched_skills=evaluation.matched_skills,
        missing_skills=evaluation.missing_skills,
        rationale=evaluation.rationale,
        selected_cv_path=evaluation.selected_cv_path,
        selection_method=evaluation.selection_method,
        selection_confidence=evaluation.selection_confidence,
    )


@app.post("/api/v1/jobs/{job_id}/documents", response_model=DocumentsResponse)
def generate_job_documents(job_id: str) -> DocumentsResponse:
    job = SERVICE.find(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    try:
        evaluation = SERVICE.evaluate(job)
        cv, letter = SERVICE.generate_documents(job, evaluation)
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DocumentsResponse(
        job_id=job_id,
        cv_path=cv,
        cover_letter_path=letter,
        pdf_path=str(Path(cv).with_suffix(".pdf")),
    )


@app.post("/api/v1/jobs/{job_id}/evaluate-task", response_model=TaskResponse, status_code=202)
def enqueue_evaluation(job_id: str) -> TaskResponse:
    if SERVICE.find(job_id) is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    task_id = TASKS.enqueue("evaluation", job_id)
    row = TASKS.get(task_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Tarea no encontrada tras encolarla")
    return TaskResponse.from_row(row)


@app.post("/api/v1/jobs/{job_id}/documents-task", response_model=TaskResponse, status_code=202)
def enqueue_documents(job_id: str) -> TaskResponse:
    if SERVICE.find(job_id) is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    task_id = TASKS.enqueue("documents", job_id)
    row = TASKS.get(task_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Tarea no encontrada tras encolarla")
    return TaskResponse.from_row(row)


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
def get_task_status(task_id: str) -> TaskResponse:
    row = TASKS.get(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return TaskResponse.from_row(row)


@app.get("/api/v1/documents/{document_name}")
def download_document(document_name: str) -> FileResponse:
    output_dir = (ROOT / "output").resolve()
    requested = (output_dir / document_name).resolve()
    if requested.parent != output_dir or not requested.is_file():
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return FileResponse(requested)


@app.get("/api/v1/applications", response_model=list[ApplicationResponse])
def list_applications(
    status: str | None = None,
    limit: int = 50,
) -> list[ApplicationResponse]:
    limit = max(1, min(limit, 100))
    rows = load_applications(DATABASE)
    if status:
        rows = [row for row in rows if row["status"].lower() == status.lower()]
    return [ApplicationResponse.from_row(row) for row in rows[:limit]]


@app.get("/api/v1/applications/{application_id}", response_model=ApplicationResponse)
def get_application_detail(application_id: int) -> ApplicationResponse:
    row = get_application(DATABASE, application_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Candidatura no encontrada")
    export_applications_csv(DATABASE, ROOT / "data" / "applications.csv")
    return ApplicationResponse.from_row(row)


@app.patch("/api/v1/applications/{application_id}", response_model=ApplicationResponse)
def change_application_status(
    application_id: int,
    update: ApplicationStatusUpdate,
) -> ApplicationResponse:
    if update.status not in APPLICATION_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Estado no permitido. Usa uno de: {', '.join(sorted(APPLICATION_STATUSES))}",
        )
    row = update_application_status(
        DATABASE,
        application_id,
        update.status,
        update.step,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Candidatura no encontrada")
    return ApplicationResponse.from_row(row)
