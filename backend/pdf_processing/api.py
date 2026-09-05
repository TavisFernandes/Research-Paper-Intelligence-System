from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile

from .pipeline import generate_paper_id, process_paper
from .storage import load_paper, load_source, save_paper, save_source

app = FastAPI(title="Research Paper PDF Processing API", version="0.1.0")


@app.post("/api/papers/upload")
async def upload_paper(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    paper_id = generate_paper_id()
    content = await file.read()
    save_source(paper_id, file.filename, content)
    suffix = Path(file.filename).suffix
    with NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        paper = process_paper(temporary_path, paper_id=paper_id)
        paper["filename"] = file.filename
        save_paper(paper)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {"paper_id": paper_id, "filename": file.filename, "total_pages": paper["total_pages"]}


@app.post("/api/papers/process/{paper_id}")
async def process_uploaded_paper(paper_id: str):
    existing = load_paper(paper_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    source = load_source(paper_id, str(existing["filename"]))
    if source is None:
        raise HTTPException(status_code=404, detail="Original PDF is not available")
    processed = process_paper(source, paper_id=paper_id)
    processed["filename"] = existing["filename"]
    save_paper(processed)
    return processed


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str):
    paper = load_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper
