import os
from pypdf import PageObject
from pypdf._writer import PdfWriter

os.makedirs("data/docs", exist_ok=True)

# Generate dummy text-bearing PDFs using ReportLab or basic text writes
# If reportlab is not installed, install it or run basic PyPDF creation:
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    def make_pdf(filename, title, body_lines):
        path = os.path.join("data/docs", filename)
        c = canvas.Canvas(path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 720, title)
        c.setFont("Helvetica", 11)
        y = 680
        for line in body_lines:
            c.drawString(72, y, line)
            y -= 20
        c.save()
        print(f"Created: {path}")

    make_pdf(
        "q4_financial_report.pdf",
        "Confidential Q4 Financial Performance",
        [
            "Operating margins expanded by 4.2% year-over-year.",
            "Total enterprise revenue reached $14.8M for the quarter.",
            "Authorized EBITDA guidance for next fiscal year is targeted at $3.2M.",
            "Restricted to authorized Finance and Executive teams only."
        ]
    )

    make_pdf(
        "cloud_architecture_spec.pdf",
        "Internal Cloud Infrastructure Architecture",
        [
            "Primary database runs PostgreSQL 17 with the pgvector extension on AWS RDS.",
            "The Kafka streaming pipeline processes a throughput of 25,000 events per second.",
            "Kubernetes clusters are autoscaled using Karpenter on m5.xlarge worker nodes.",
            "Restricted to Infrastructure and Engineering departments only."
        ]
    )

except ImportError:
    print("ReportLab not found. Install it quickly via: pip install reportlab")