"""Upload ingestion: validation, duplicate detection, background processing."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

from config import settings
from errors import InvalidInputError, PdfIngestionError
from pdf_processing.pipeline import process_paper
from pdf_processing.storage import find_by_hash, next_paper_id, save_paper, save_source, sha256_bytes

from .jobs import Job, jobs

logger = logging.getLogger(__name__)
_PDF_MAGIC = b"%PDF-"


def register_upload(filename: str, content: bytes) -> Job:
    """Validate an upload and register a job. Duplicates (same SHA-256) are not re-ingested."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise InvalidInputError("Only PDF uploads are supported.")
    if not content:
        raise InvalidInputError("The uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise InvalidInputError(f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB upload limit.")
    if not content.lstrip()[:1024].startswith(_PDF_MAGIC) and _PDF_MAGIC not in content[:1024]:
        raise InvalidInputError("The file does not look like a PDF.")
    digest = sha256_bytes(content)
    existing = find_by_hash(digest)
    if existing:
        return jobs.create(str(existing["paper_id"]), filename, status="duplicate", stage="duplicate", progress=100,
                           duplicate_of=str(existing["paper_id"]))
    paper_id = next_paper_id()
    # Reserve the id immediately so concurrent uploads in the same request batch cannot collide.
    save_source(paper_id, filename, content)
    job = jobs.create(paper_id, filename)
    _pending[job.job_id] = (digest, content)
    return job


_pending: dict[str, tuple[str, bytes]] = {}


def run_ingestion(job_id: str) -> None:
    """Process a registered job (intended to run in a background thread)."""
    job = jobs.get(job_id)
    entry = _pending.pop(job_id, None)
    if job is None or entry is None:
        return
    digest, content = entry
    jobs.update(job_id, status="processing", stage="starting", progress=5)
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        paper = process_paper(tmp_path, job.paper_id, filename=job.filename, content_sha256=digest,
                              progress=lambda stage, pct: jobs.update(job_id, stage=stage, progress=pct))
        save_paper(paper)
        jobs.update(job_id, status="completed", stage="done", progress=100)
    except PdfIngestionError as exc:
        jobs.update(job_id, status="failed", stage="failed", error=exc.public_message)
        _discard_reserved(job.paper_id)
    except Exception as exc:  # unexpected: log details, expose a generic message
        logger.exception("Ingestion failed for %s", job.filename)
        message = exc.public_message if hasattr(exc, "public_message") else "Processing failed unexpectedly. See server logs."
        jobs.update(job_id, status="failed", stage="failed", error=message)
        _discard_reserved(job.paper_id)
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)


def _discard_reserved(paper_id: Optional[str]) -> None:
    if paper_id:
        from pdf_processing.storage import load_paper, storage_dir

        if load_paper(paper_id) is None:  # never delete a successfully stored paper
            for target in storage_dir().glob(f"{paper_id}.*"):
                target.unlink(missing_ok=True)
