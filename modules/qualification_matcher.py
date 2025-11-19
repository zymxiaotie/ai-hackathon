# modules/qualification_matcher.py
import psycopg2
from datetime import date
from typing import List, Dict

def match_qualification_criteria(tender_id: int, conn, use_semantic_fallback: bool = False) -> List[Dict]:
    """
    Main matcher – updates DB + returns summary.
    Rule-based first, semantic fallback optional (for future RAG).
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT criteria_id, criteria_type, criteria_description, criteria_value
        FROM tender_qualification_criteria
        WHERE tender_id = %s AND (is_met IS NULL OR requires_recheck)
        ORDER BY criteria_id
    """, (tender_id,))
    criteria = cur.fetchall()

    results = []
    for crit in criteria:
        crit_id, ctype, desc, value = crit
        result = {"criteria_id": crit_id, "is_met": False, "notes": "Not checked"}

        if ctype == "LICENSE":
            result = check_license(desc, conn)
        elif ctype == "CERTIFICATION":
            result = check_certification(desc, conn)
        elif ctype == "EXPERIENCE":
            result = check_experience(value or desc, conn)
        elif ctype == "FINANCIAL":
            result = check_financial(value or desc, conn)
        elif ctype == "COMPLIANCE":
            result = {"is_met": False, "notes": "Manual verification required (e.g. MOM permits)"}
        else:
            result = {"is_met": False, "notes": "Unknown criteria type"}

        # Update DB
        cur.execute("""
            UPDATE tender_qualification_criteria
            SET is_met = %s, notes = %s, checked_date = NOW(), requires_recheck = FALSE
            WHERE criteria_id = %s
        """, (result["is_met"], result["notes"], crit_id))
        
        result["criteria_id"] = crit_id
        result["type"] = ctype
        result["description"] = desc
        results.append(result)

    conn.commit()
    cur.close()
    return results


# ---------- Individual Checkers ----------
def check_license(description: str, conn) -> Dict:
    cur = conn.cursor()
    cur.execute("""
        SELECT license_grade, expiry_date FROM company_licenses
        WHERE license_type ILIKE %s OR license_category ILIKE %s
    """, (f"%{description}%", f"%{description}%"))
    row = cur.fetchone()
    if row and (row[1] is None or row[1] >= date.today()):
        return {"is_met": True, "notes": f"Valid {row[0]} until {row[1]}"}
    return {"is_met": False, "notes": "Required license not found or expired"}


def check_certification(description: str, conn) -> Dict:
    cur = conn.cursor()
    cur.execute("""
        SELECT certification_name, expiry_date FROM company_certifications
        WHERE certification_name ILIKE %s
    """, (f"%{description}%",))
    row = cur.fetchone()
    if row and (row[1] is None or row[1] >= date.today()):
        return {"is_met": True, "notes": f"Valid {row[0]}"}
    return {"is_met": False, "notes": "Certification missing or expired"}


def check_experience(requirement: str, conn) -> Dict:
    import re
    match = re.search(r'(\d+)\s*projects?.*?(\d+[\d,.]*\s*M)', requirement, re.I)
    if not match:
        return {"is_met": False, "notes": "Could not parse experience requirement"}
    
    min_projects = int(match.group(1))
    min_value = float(match.group(2).replace('M', '').replace(',', '').strip()) * 1_000_000

    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(contract_value),0)
        FROM company_projects
        WHERE completion_date >= CURRENT_DATE - INTERVAL '5 years'
          AND contract_value >= %s
    """, (min_value,))
    count, total = cur.fetchone()
    
    if count >= min_projects:
        return {"is_met": True, "notes": f"{count} qualifying projects found"}
    else:
        return {"is_met": False, "notes": f"Only {count} projects ≥ ${min_value/1e6}M in last 5 years"}


def check_financial(requirement: str, conn) -> Dict:
    import re
    match = re.search(r'(\d+[\d,.]*\s*M)', requirement, re.I)
    if not match:
        return {"is_met": False, "notes": "Could not parse financial requirement"}
    
    min_turnover = float(match.group(1).replace('M', '').replace(',', '').strip()) * 1_000_000

    cur = conn.cursor()
    cur.execute("""
        SELECT annual_turnover FROM company_financials
        ORDER BY financial_year DESC LIMIT 1
    """)
    row = cur.fetchone()
    if row and row[0] >= min_turnover:
        return {"is_met": True, "notes": f"FY turnover ${row[0]/1e6}M ≥ required"}
    return {"is_met": False, "notes": "Annual turnover below threshold"}