import hashlib
import os
import io
from pypdf import PdfReader
from docx import Document as DocxDocument
from fastembed import TextEmbedding
from app.database import SessionLocal, Document, DocumentChunk

# Initialize embedding model with a larger batch size for faster throughput
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def compute_sha256_bytes(file_bytes: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    return hasher.hexdigest()


def extract_text_by_format(file_bytes: bytes, filename: str) -> list[tuple[int, str]]:
    """Fast in-memory text extraction per page/section."""
    ext = os.path.splitext(filename)[1].lower()
    pages_data = []

    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages_data.append((idx + 1, text.strip()))

    elif ext == ".docx":
        doc = DocxDocument(io.BytesIO(file_bytes))
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        if full_text:
            pages_data.append((1, full_text))

    elif ext in [".txt", ".md", ".csv", ".json"]:
        text = file_bytes.decode("utf-8", errors="ignore")
        if text.strip():
            pages_data.append((1, text))

    else:
        raise ValueError(f"Unsupported file format: {ext}")

    return pages_data


def ingest_uploaded_file(
    file_bytes: bytes,
    filename: str,
    allowed_roles: list[str],
    classification: str = "internal",
    # Tuned window: larger windows mean fewer total embeddings and faster processing
    window_words: int = 350,
    overlap_words: int = 30,
    batch_size: int = 64,
) -> dict:
    doc_id = compute_sha256_bytes(file_bytes)
    db = SessionLocal()

    try:
        # 1. Idempotency Check
        existing = db.query(Document).filter(Document.id == doc_id).first()
        if existing:
            return {
                "status": "already_exists",
                "doc_id": doc_id,
                "message": f"Document '{filename}' is already indexed."
            }

        extracted_pages = extract_text_by_format(file_bytes, filename)
        if not extracted_pages:
            return {
                "status": "empty",
                "doc_id": doc_id,
                "message": f"No readable text found in '{filename}'."
            }

        texts_to_embed = []
        chunk_metadata = []

        step = max(1, window_words - overlap_words)
        for page_num, page_text in extracted_pages:
            words = page_text.split()
            # If page text is compact (typical lecture slide), keep it as a single chunk
            if len(words) <= window_words:
                content = " ".join(words)
                chunk_idx = len(chunk_metadata)
                chunk_id = f"{doc_id[:12]}_p{page_num}_c{chunk_idx}"
                texts_to_embed.append(content)
                chunk_metadata.append((chunk_id, page_num, chunk_idx, content))
            else:
                for i in range(0, len(words), step):
                    chunk_words = words[i : i + window_words]
                    if not chunk_words:
                        continue
                    content = " ".join(chunk_words)
                    chunk_idx = len(chunk_metadata)
                    chunk_id = f"{doc_id[:12]}_p{page_num}_c{chunk_idx}"
                    texts_to_embed.append(content)
                    chunk_metadata.append((chunk_id, page_num, chunk_idx, content))

        # 2. Batch embedding via ONNX runtime
        embeddings = list(embedding_model.embed(texts_to_embed, batch_size=batch_size))

        # 3. Insert Document and flush for foreign key dependency
        new_doc = Document(
            id=doc_id,
            filename=filename,
            classification=classification,
            allowed_roles=allowed_roles,
        )
        db.add(new_doc)
        db.flush()

        # 4. Insert chunks
        chunks_to_insert = [
            DocumentChunk(
                id=c_id,
                doc_id=doc_id,
                page_number=p_num,
                chunk_index=c_idx,
                content=content,
                embedding=emb.tolist(),
                allowed_roles=allowed_roles,
            )
            for (c_id, p_num, c_idx, content), emb in zip(chunk_metadata, embeddings)
        ]

        db.add_all(chunks_to_insert)
        db.commit()

        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": filename,
            "chunks_count": len(chunks_to_insert)
        }

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()