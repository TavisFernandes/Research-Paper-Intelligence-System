"""In-memory ingestion job registry (status/progress for uploads)."""
from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional
from uuid import uuid4

STATUSES = ("queued", "processing", "completed", "failed", "duplicate")


@dataclass
class Job:
    job_id: str
    paper_id: Optional[str]
    filename: str
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    error: Optional[str] = None
    duplicate_of: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class JobStore:
    def __init__(self, max_jobs: int = 500):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max = max_jobs

    def create(self, paper_id: Optional[str], filename: str, **kwargs) -> Job:
        job = Job(job_id=uuid4().hex[:12], paper_id=paper_id, filename=filename, **kwargs)
        with self._lock:
            self._jobs[job.job_id] = job
            if len(self._jobs) > self._max:
                for key in sorted(self._jobs, key=lambda k: self._jobs[k].created_at)[: len(self._jobs) - self._max]:
                    del self._jobs[key]
        return job

    def update(self, job_id: str, **changes) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                for key, value in changes.items():
                    setattr(job, key, value)
                job.updated_at = time.time()

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def for_paper(self, paper_id: str) -> Optional[Job]:
        with self._lock:
            matches: List[Job] = [j for j in self._jobs.values() if j.paper_id == paper_id]
        return max(matches, key=lambda j: j.created_at) if matches else None


jobs = JobStore()
