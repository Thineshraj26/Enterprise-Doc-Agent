import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey, func, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector

# Updated port to 5433 to avoid port 5432 host conflicts
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:adminpassword@localhost:5433/enterprise_agent",
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"
    id = Column(String(64), primary_key=True)  # SHA-256 hash
    filename = Column(String(255), nullable=False)
    classification = Column(
        String(50), default="internal"
    )  # public, internal, restricted
    allowed_roles = Column(JSON, nullable=False)  # e.g., ["finance_lead", "auditor"]
    created_at = Column(DateTime, server_default=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String(100), primary_key=True)  # doc_id + chunk_index
    doc_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"))
    page_number = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)  # 384 dims for BGE-small
    allowed_roles = Column(JSON, nullable=False)  # Inherited for fast pre-filtering


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False)
    user_id = Column(String(64), nullable=False)
    user_role = Column(String(64), nullable=False)
    query = Column(Text, nullable=False)
    accessed_chunk_ids = Column(JSON, nullable=False)
    response_generated = Column(Text, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())


def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database and pgvector extension initialized.")