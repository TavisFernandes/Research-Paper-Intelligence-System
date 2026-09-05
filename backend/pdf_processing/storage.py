import json
import os
from pathlib import Path
from typing import Dict, Optional


def storage_dir() -> Path:
    directory = Path(os.environ.get("PAPER_STORAGE_DIR", Path(__file__).parents[1] / "data"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_paper(paper: Dict[str, object]) -> None:
    target = storage_dir() / f"{paper['paper_id']}.json"
    target.write_text(json.dumps(paper, indent=2), encoding="utf-8")


def save_source(paper_id: str, filename: str, content: bytes) -> None:
    suffix = Path(filename).suffix.lower() or ".pdf"
    (storage_dir() / f"{paper_id}{suffix}").write_bytes(content)


def load_source(paper_id: str, filename: str) -> Optional[Path]:
    suffix = Path(filename).suffix.lower() or ".pdf"
    source = storage_dir() / f"{paper_id}{suffix}"
    return source if source.exists() else None


def load_paper(paper_id: str) -> Optional[Dict[str, object]]:
    target = storage_dir() / f"{paper_id}.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
