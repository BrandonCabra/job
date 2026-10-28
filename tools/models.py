from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    title: str
    company: str
    description: str
    url: str
    location: str = ""
    source: str = "local"
    external_id: str = ""
    published_at: str = ""
    scraped_at: str = ""
    status: str = "new"


@dataclass
class Evaluation:
    score: int
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    rationale: str = ""
    selected_cv_path: str = ""
    selection_method: str = ""
    selection_confidence: float | None = None


@dataclass
class ApplicationRecord:
    job: Job
    score: int
    status: str
    step: str
    cv_path: str = ""
    cover_letter_path: str = ""
    details: dict[str, Any] = field(default_factory=dict)
