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


@dataclass
class Evaluation:
    score: int
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class ApplicationRecord:
    job: Job
    score: int
    status: str
    step: str
    cv_path: str = ""
    cover_letter_path: str = ""
    details: dict[str, Any] = field(default_factory=dict)
