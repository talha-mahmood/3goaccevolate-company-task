from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

class Job(BaseModel):
    job_title: str
    company: str
    experience: Optional[str] = None
    jobNature: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    apply_link: HttpUrl
    source: str  # Which platform this job was found on
    description: Optional[str] = None  # Full job description (used for relevance matching)
    relevance_score: Optional[float] = None  # Score calculated by LLM

class JobResponse(BaseModel):
    relevant_jobs: List[Job]
