from app.ingest import ingest_pdf

if __name__ == "__main__":
    print("--- Ingesting Finance Document ---")
    ingest_pdf(
        file_path="data/docs/q4_financial_report.pdf",
        allowed_roles=["finance", "cfo"],
        classification="restricted"
    )

    print("\n--- Ingesting Engineering Document ---")
    ingest_pdf(
        file_path="data/docs/cloud_architecture_spec.pdf",
        allowed_roles=["engineering", "admin"],
        classification="internal"
    )