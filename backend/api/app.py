from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from models import AnswerRequest, CompareRequest, HealthResponse, SearchRequest, SummaryRequest
from pdf_processing.pipeline import generate_paper_id, process_paper
from pdf_processing.storage import delete_paper, list_papers, load_paper, save_paper, save_source
from embeddings import embedder
from vector_store import vector_store
from rag import answer_question
from summarization.led import summarize
from comparison import compare_papers, research_insights

app = FastAPI(title="Research Paper Intelligence API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.allow_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def _paper_or_404(paper_id: str) -> dict:
    paper = load_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    return paper


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(vector_store=vector_store.backend, embedding_backend=embedder.backend, llm_backend=answer_question.__module__.split(".")[0], details={"index": settings.redis_index})


@app.get("/api/papers")
def papers() -> list[dict]:
    return [{key: paper.get(key) for key in ("paper_id", "filename", "total_pages", "analysis", "indexing")} for paper in list_papers()]


@app.post("/api/papers/upload")
async def upload_paper(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF uploads are supported")
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "File exceeds the configured upload limit")
    paper_id = generate_paper_id({str(item.get("paper_id")) for item in list_papers()})
    suffix = Path(file.filename).suffix
    with NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(content)
        temp_path = Path(temp.name)
    try:
        paper = process_paper(temp_path, paper_id)
    finally:
        temp_path.unlink(missing_ok=True)
    paper["filename"] = file.filename
    save_source(paper_id, file.filename, content)
    save_paper(paper)
    return paper


@app.post("/api/papers/process/{paper_id}")
def process_existing(paper_id: str) -> dict:
    return _paper_or_404(paper_id)


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str) -> dict:
    return _paper_or_404(paper_id)


@app.delete("/api/papers/{paper_id}")
def remove_paper(paper_id: str) -> dict:
    if not delete_paper(paper_id):
        raise HTTPException(404, "Paper not found")
    vector_store.delete_paper(paper_id)
    return {"deleted": paper_id}


@app.post("/api/search")
def search(request: SearchRequest) -> dict:
    hits = vector_store.search(embedder.encode(request.query), request.limit, request.paper_ids, request.section_name)
    return {"query": request.query, "results": hits}


@app.post("/api/qa")
def question_answering(request: AnswerRequest) -> dict:
    return answer_question(request.query, request.paper_ids, request.section_name, request.limit)


@app.post("/api/summarize")
def summary(request: SummaryRequest) -> dict:
    paper = _paper_or_404(request.paper_id)
    sections = paper.get("sections", [])
    text = "\n".join(item["text"] for item in sections if not request.section_name or item["section_name"] == request.section_name)
    return {"paper_id": request.paper_id, "section_name": request.section_name, **summarize(text, request.max_sentences)}


@app.post("/api/compare")
def compare(request: CompareRequest) -> dict:
    left, right = (_paper_or_404(identifier) for identifier in request.paper_ids[:2])
    return compare_papers(left, right)


@app.post("/api/insights")
def insights(request: CompareRequest) -> dict:
    return research_insights([_paper_or_404(identifier) for identifier in request.paper_ids])
