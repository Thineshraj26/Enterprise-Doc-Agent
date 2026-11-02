import os
import re
import time
import uuid
from dotenv import load_dotenv
from fastembed import TextEmbedding
from google import genai
from google.genai import types
from google.genai.errors import APIError
from sqlalchemy import text

from app.database import AuditLog, SessionLocal

load_dotenv()

# Pre-load local ONNX embedding model (384 dimensions)
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Models prioritized based on active rate limits (gemini-3.8-flash daily cap avoided)
CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "models/gemini-2.5-flash",
    "models/gemini-flash-latest",
]


def verify_grounding(answer: str, retrieved_chunk_ids: set[str]) -> bool:
    """Verifies that all citations in the response match actual retrieved chunk IDs."""
    citations_found = set(re.findall(r"\[([^\]]+)\]", answer))
    if not citations_found:
        return False
    return citations_found.issubset(retrieved_chunk_ids)


def call_gemini_fast(prompt: str, system_instruction: str) -> str:
    """Invokes Gemini across candidate models with immediate failover on quota exhaustion."""
    last_error = None

    for model_name in CANDIDATE_MODELS:
        try:
            print(f"[Engine] Invoking model '{model_name}'...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.0,
                ),
            )
            if response and response.text and response.text.strip():
                print(f"[Engine] -> Success from '{model_name}'.")
                return response.text.strip()
        except APIError as e:
            last_error = f"{e.code} {e.message}"
            print(f"[Engine] APIError on '{model_name}': {last_error}")

            # Immediate failover if daily limit exceeded or model endpoint missing
            if "per day limit exceeded" in e.message.lower() or e.code in [404, 429]:
                continue

            # Transient 503 spike backoff
            if e.code == 503:
                time.sleep(1.0)
                continue

        except Exception as e:
            last_error = str(e)
            print(f"[Engine] Unexpected exception on '{model_name}': {last_error}")
            continue

    if last_error:
        return f"Error during Gemini generation: {last_error}"

    return "Insufficient authorized information."


def query_agent(
    user_id: str,
    user_role: str,
    question: str,
    top_k: int = 3,
    distance_threshold: float = 0.50,
) -> dict:
    request_id = str(uuid.uuid4())
    db = SessionLocal()

    try:
        # 1. Local Query Embedding (single-pass vector generation)
        query_vector = list(embedding_model.embed([question]))[0].tolist()

        # 2. Strict Pre-Filtering RBAC query with cosine distance cutoff
        raw_sql = text("""
            SELECT id, doc_id, page_number, content, (embedding <=> :vec) AS distance
            FROM document_chunks
            WHERE allowed_roles::jsonb ? :role
              AND (embedding <=> :vec) < :threshold
            ORDER BY distance ASC
            LIMIT :limit;
        """)

        results = db.execute(
            raw_sql,
            {
                "vec": str(query_vector),
                "role": user_role,
                "threshold": distance_threshold,
                "limit": top_k,
            },
        ).fetchall()

        # RBAC / Relevance Guard: Return early if no authorized chunks pass distance threshold
        if not results:
            response_payload = {
                "request_id": request_id,
                "answer": "No authorized documentation found matching your security context.",
                "citations": [],
                "is_grounded": True,
            }
            audit = AuditLog(
                request_id=request_id,
                user_id=user_id,
                user_role=user_role,
                query=question,
                accessed_chunk_ids=[],
                response_generated=response_payload["answer"],
            )
            db.add(audit)
            db.commit()
            return response_payload

        retrieved_chunks = [
            {"id": row[0], "doc_id": row[1], "page": row[2], "content": row[3]}
            for row in results
        ]
        retrieved_ids = {c["id"] for c in retrieved_chunks}

        # 3. Ground Truth Context Assembly
        context_str = "\n\n".join(
            [f"ID [{c['id']}] (Page {c['page']}):\n{c['content']}" for c in retrieved_chunks]
        )

        system_instruction = (
            "You are an enterprise document analyst. Answer the user question by extracting "
            "and synthesizing all factual answers directly from the provided context chunks.\n"
            "Rules:\n"
            "1. Answer using any substantive information present in the context chunks, ignoring non-informational agenda/outline slides.\n"
            "2. Present the answer clearly using structured bullet points.\n"
            "3. At the end of every sentence or bullet point, you MUST cite the exact source chunk ID in square brackets, e.g. [chunk_id].\n"
            "4. Do NOT extrapolate, hallucinate, or assume facts not explicitly stated in the chunks.\n"
            "5. Only respond 'Insufficient authorized information.' if none of the provided chunks mention or define the requested topic."
        )

        prompt = f"""Context:
{context_str}

Question: {question}
Answer:"""

        # 4. Low-latency LLM Inference with instant daily quota failover
        raw_answer = call_gemini_fast(
            prompt=prompt,
            system_instruction=system_instruction,
        )

        # 5. Deterministic Grounding Verification
        is_grounded = verify_grounding(raw_answer, retrieved_ids)

        # 6. Immutable Audit Trail Persistence
        audit = AuditLog(
            request_id=request_id,
            user_id=user_id,
            user_role=user_role,
            query=question,
            accessed_chunk_ids=list(retrieved_ids),
            response_generated=raw_answer,
        )
        db.add(audit)
        db.commit()

        return {
            "request_id": request_id,
            "answer": raw_answer,
            "citations": retrieved_chunks,
            "is_grounded": is_grounded,
        }

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()