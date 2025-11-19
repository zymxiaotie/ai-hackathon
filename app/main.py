# app/main.py   ← 100% WORKING FASTAPI SERVER
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sqlite3
from modules.report_generator import generate_report

app = FastAPI(
    title="Digital Tender Quantity Surveyor AI Agent",
    description="Live Interactive Tender Report – GECO AI Hackathon PoC",
    version="1.0"
)

DB_PATH = "tender_intel.db"

@app.get("/", response_class=HTMLResponse)
async def root():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    html = generate_report(tender_id=1, conn=conn)
    conn.close()
    return html

@app.get("/health")
async def health():
    return {"status": "Digital Tender QS AI Agent is LIVE and READY!", "tender": "HDB/2025/REN/001"}

@app.get("/api/run-matcher")
async def run_matcher():
    from modules.qualification_matcher import match_qualification_criteria
    conn = sqlite3.connect(DB_PATH)
    match_qualification_criteria(tender_id=1, conn=conn)
    conn.close()
    return {"status": "Eligibility matcher ran successfully"}