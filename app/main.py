import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc

from app.engine import query_agent
from app.database import SessionLocal, AuditLog, Document
from app.ingest import ingest_uploaded_file

# Set multi-threading for ONNX without thread-lock deadlocks on Windows
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

app = FastAPI(
    title="Enterprise Document Analysis Agent",
    description="Auditable, RBAC-enforced document QA engine with deterministic citations.",
    version="1.0.0"
)

# 4 workers ensure uploads do not block concurrent queries
executor = ThreadPoolExecutor(max_workers=4)

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: Optional[int] = Field(default=3, ge=1, le=10)

class Citation(BaseModel):
    id: str
    doc_id: Optional[str] = None
    page: Optional[int] = None
    content: Optional[str] = None

class QueryResponse(BaseModel):
    request_id: str
    answer: str
    citations: List[Citation] = []
    is_grounded: bool


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/v1/upload")
async def upload_document(
    file: UploadFile = File(...),
    roles: str = Form(..., description="Comma-separated roles, e.g. 'finance,cfo'"),
    classification: str = Form(default="internal"),
    x_user_role: str = Header(..., description="Uploader role")
):
    parsed_roles = [r.strip().lower() for r in roles.split(",") if r.strip()]
    if not parsed_roles:
        raise HTTPException(status_code=400, detail="At least one allowed role must be provided.")

    file_bytes = await file.read()
    loop = asyncio.get_running_loop()

    try:
        result = await loop.run_in_executor(
            executor,
            lambda: ingest_uploaded_file(
                file_bytes=file_bytes,
                filename=file.filename,
                allowed_roles=parsed_roles,
                classification=classification,
            )
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/api/v1/documents")
def list_documents(x_user_role: str = Header(...)):
    db = SessionLocal()
    try:
        all_docs = db.query(Document).order_by(desc(Document.created_at)).all()
        visible = [
            {
                "id": d.id,
                "filename": d.filename,
                "classification": d.classification,
                "allowed_roles": d.allowed_roles,
                "created_at": d.created_at.isoformat() if d.created_at else None
            }
            for d in all_docs
            if x_user_role.lower() in d.allowed_roles or x_user_role.lower() == "admin"
        ]
        return visible
    finally:
        db.close()


@app.post("/api/v1/analyze", response_model=QueryResponse)
async def analyze_document(
    request: QueryRequest,
    x_user_id: str = Header(...),
    x_user_role: str = Header(...)
):
    if not x_user_id or not x_user_role:
        raise HTTPException(status_code=401, detail="Missing identity headers")

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        executor,
        lambda: query_agent(
            user_id=x_user_id,
            user_role=x_user_role.lower(),
            question=request.question,
            top_k=request.top_k,
            distance_threshold=0.50,
        )
    )
    return result


@app.get("/api/v1/audit/logs")
def view_audit_logs(limit: int = Query(default=20, ge=1, le=100), x_user_role: str = Header(...)):
    if x_user_role.lower() not in ["auditor", "admin", "compliance"]:
        raise HTTPException(status_code=403, detail="Access denied: requires auditor privileges.")

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit).all()
        return [
            {
                "id": log.id,
                "request_id": log.request_id,
                "user_id": log.user_id,
                "user_role": log.user_role,
                "query": log.query,
                "accessed_chunk_ids": log.accessed_chunk_ids,
                "response_generated": log.response_generated,
                "timestamp": log.timestamp.isoformat()
            }
            for log in logs
        ]
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()