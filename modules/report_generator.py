# modules/report_generator.py   ← FIXED FOR SQLITE
import sqlite3
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import os
from modules.completeness_checker import get_document_stats, get_missing_documents

# Jinja setup
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../templates")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def generate_report(tender_id: int, conn, output_path: str = None) -> str:
    cur = conn.cursor()

    # 1. Tender master data - FIXED: ? instead of %s
    cur.execute("SELECT * FROM tenders WHERE tender_id = ?", (tender_id,))
    tender = cur.fetchone()
    if not tender:
        raise ValueError("Tender not found")

    columns = [desc[0] for desc in cur.description]
    tender_dict = dict(zip(columns, tender))

    # 2. Stats & missing docs
    stats = get_document_stats(tender_id, conn)
    missing_docs = get_missing_documents(tender_id, conn)

    # 3. Eligibility criteria - FIXED: ?
    cur.execute("""
        SELECT criteria_type, criteria_description, is_met, notes, source,
               (SELECT addendum_number FROM tender_addenda ta 
                WHERE ta.addendum_id = tqc.introduced_by_addendum_id)
        FROM tender_qualification_criteria tqc
        WHERE tqc.tender_id = ?
        ORDER BY tqc.added_date
    """, (tender_id,))
    criteria = cur.fetchall()

    # 4. Addenda - FIXED: ?
    cur.execute("""
        SELECT addendum_number, title, summary, received_date
        FROM tender_addenda WHERE tender_id = ? ORDER BY received_date
    """, (tender_id,))
    addenda = cur.fetchall()

    # 5. Recommendation logic
    met_criteria = sum(1 for c in criteria if c[2] == 1)  # SQLite uses 1/0 for BOOLEAN
    all_met = met_criteria == len(criteria)
    no_missing_mandatory = len(missing_docs) == 0
    recommend_go = all_met and no_missing_mandatory

    # Days until deadline
    deadline_str = tender_dict["submission_deadline"]
    deadline_date = datetime.strptime(deadline_str.split()[0], "%Y-%m-%d")
    days_until_deadline = (deadline_date - datetime.now()).days

    context = {
        "tender": tender_dict,
        "stats": stats,
        "missing_docs": missing_docs,
        "criteria": criteria,
        "addenda": addenda,
        "recommend_go": recommend_go,
        "days_until_deadline": days_until_deadline,
        "generated_at": datetime.now().strftime("%d %b %Y, %I:%M %p")
    }

    template = env.get_template("interactive_report.html")
    html = template.render(**context)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return html