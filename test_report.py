# test_report.py - UPDATED VERSION
from modules.report_generator import generate_report
from modules.db_connection import get_postgres_connection

with get_postgres_connection() as conn:
    # First, check what tender IDs exist
    cur = conn.cursor()
    cur.execute("SELECT tender_id, tender_reference_number, tender_title FROM tenders LIMIT 5")
    tenders = cur.fetchall()
    
    if not tenders:
        print("❌ No tenders found in database!")
        print("The 'tenders' table is empty. You need to populate it with data first.")
    else:
        print(f"✅ Found {len(tenders)} tender(s):")
        for t in tenders:
            print(f"  - ID: {t['tender_id']}, Ref: {t['tender_reference_number']}, Title: {t['tender_title']}")
        
        # Use the first tender ID we found
        last_tender_id = tenders[-1]['tender_id']
        print(f"\n📄 Generating report for tender_id={last_tender_id}...")
        
        html = generate_report(
            tender_id=last_tender_id, 
            conn=conn, 
            output_path="DEMO_REPORT.html"
        )
        print("✅ Report generated → DEMO_REPORT.html")

########################################################  old code for mock db ########################################################
# import sqlite3
# from modules.report_generator import generate_report

# conn = sqlite3.connect("tender_intel.db")
# conn.row_factory = sqlite3.Row

# html = generate_report(tender_id=1, conn=conn, output_path="DEMO_REPORT_18Nov2025.html")
# print("✅ Report generated → DEMO_REPORT_18Nov2025.html")
# conn.close()