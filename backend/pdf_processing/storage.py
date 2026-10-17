<<<<<<< HEAD
"""Local JSON/PDF storage for processed papers (atomic writes, validated identifiers)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Optional

from config import settings
from errors import InvalidInputError

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_paper_id(paper_id: str) -> str:
    """Reject identifiers that could escape the storage directory."""
    if not isinstance(paper_id, str) or not _ID_RE.match(paper_id):
        raise InvalidInputError("Invalid paper id.")
    return paper_id


def storage_dir() -> Path:
    configured = os.environ.get("PAPER_STORAGE_DIR") or settings.storage_dir
    directory = Path(configured) if configured else Path(__file__).resolve().parents[1] / "data"
=======
import json
import os
from pathlib import Path
from typing import Dict, Optional


def storage_dir() -> Path:
    directory = Path(os.environ.get("PAPER_STORAGE_DIR", Path(__file__).parents[1] / "data"))
>>>>>>> origin/main
    directory.mkdir(parents=True, exist_ok=True)
    return directory


<<<<<<< HEAD
def _atomic_write(target: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_paper(paper: Dict[str, object]) -> None:
    paper_id = validate_paper_id(str(paper["paper_id"]))
    _atomic_write(storage_dir() / f"{paper_id}.json", json.dumps(paper, indent=2).encode("utf-8"))


def save_source(paper_id: str, filename: str, content: bytes) -> None:
    validate_paper_id(paper_id)
    suffix = Path(filename).suffix.lower() or ".pdf"
    _atomic_write(storage_dir() / f"{paper_id}{suffix}", content)


def load_source(paper_id: str, filename: str) -> Optional[Path]:
    validate_paper_id(paper_id)
=======
def save_paper(paper: Dict[str, object]) -> None:
    target = storage_dir() / f"{paper['paper_id']}.json"
    target.write_text(json.dumps(paper, indent=2), encoding="utf-8")


def save_source(paper_id: str, filename: str, content: bytes) -> None:
    suffix = Path(filename).suffix.lower() or ".pdf"
    (storage_dir() / f"{paper_id}{suffix}").write_bytes(content)


def load_source(paper_id: str, filename: str) -> Optional[Path]:
>>>>>>> origin/main
    suffix = Path(filename).suffix.lower() or ".pdf"
    source = storage_dir() / f"{paper_id}{suffix}"
    return source if source.exists() else None


def load_paper(paper_id: str) -> Optional[Dict[str, object]]:
<<<<<<< HEAD
    validate_paper_id(paper_id)
    target = storage_dir() / f"{paper_id}.json"
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
=======
    target = storage_dir() / f"{paper_id}.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
>>>>>>> origin/main


def list_papers() -> list[Dict[str, object]]:
    papers = []
<<<<<<< HEAD
    for target in storage_dir().glob("*.json"):
        if target.name.startswith("."):
            continue
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and data.get("paper_id"):
            papers.append(data)
    return sorted(papers, key=lambda paper: str(paper.get("paper_id", "")))


def find_by_hash(content_hash: str) -> Optional[Dict[str, object]]:
    """Return an already-ingested paper with the same file hash (duplicate detection)."""
    for paper in list_papers():
        if paper.get("content_sha256") == content_hash:
            return paper
    return None


def next_paper_id() -> str:
    existing = {str(item.get("paper_id")) for item in list_papers()}
    # Also skip ids reserved by an in-flight upload (source file saved, JSON not yet written).
    existing |= {path.stem for path in storage_dir().glob("P*.*") if not path.name.startswith(".")}
    index = 1
    while f"P{index:03d}" in existing:
        index += 1
    return f"P{index:03d}"


def delete_paper(paper_id: str) -> bool:
    validate_paper_id(paper_id)
    if load_paper(paper_id) is None:
=======
    for target in storage_dir().glob("P-*.json"):
        try:
            papers.append(json.loads(target.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(papers, key=lambda paper: str(paper.get("paper_id", "")))


def delete_paper(paper_id: str) -> bool:
    paper = load_paper(paper_id)
    if not paper:
>>>>>>> origin/main
        return False
    for target in storage_dir().glob(f"{paper_id}.*"):
        target.unlink(missing_ok=True)
    return True
