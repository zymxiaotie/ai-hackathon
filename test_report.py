# test_report.py - POSTGRES VERSION
from modules.report_generator import generate_report
from modules.db_connection import get_postgres_connection

with get_postgres_connection() as conn:
    html = generate_report(tender_id=1, conn=conn, output_path="DEMO_REPORT_18Nov2025.html")
    print("✅ Report generated → DEMO_REPORT_18Nov2025.html")

########################################################  old code for mock db ########################################################
# import sqlite3
# from modules.report_generator import generate_report

# conn = sqlite3.connect("tender_intel.db")
# conn.row_factory = sqlite3.Row

# html = generate_report(tender_id=1, conn=conn, output_path="DEMO_REPORT_18Nov2025.html")
# print("✅ Report generated → DEMO_REPORT_18Nov2025.html")
# conn.close()