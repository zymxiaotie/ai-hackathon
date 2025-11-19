# modules/completeness_checker.py - POSTGRES VERSION
from typing import List, Dict

def get_missing_documents(tender_id: int, conn) -> List[Dict]:
    query = """
        SELECT 
            trd.document_name,
            trd.document_category,
            trd.description,
            trd.source,
            ta.addendum_number
        FROM tender_required_documents trd
        LEFT JOIN tender_received_documents trc 
            ON trd.tender_id = trc.tender_id 
            AND TRIM(trd.document_name) = TRIM(trc.document_name)
        LEFT JOIN tender_addenda ta ON trd.introduced_by_addendum_id = ta.addendum_id
        WHERE trd.tender_id = %s
          AND trd.is_mandatory = TRUE
          AND trc.received_doc_id IS NULL
        ORDER BY trd.added_date;
    """
    cur = conn.cursor()
    cur.execute(query, (tender_id,))
    rows = cur.fetchall()
    cur.close()

    missing = []
    for row in rows:
        missing.append({
            "document_name": row['document_name'],
            "category": row['document_category'] or "Uncategorized",
            "description": row['description'],
            "source": f"Addendum #{row['addendum_number']}" if row['addendum_number'] else "Original",
        })
    return missing


def get_document_stats(tender_id: int, conn) -> Dict:
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE is_mandatory = TRUE) as mandatory_total,
            COUNT(*) FILTER (WHERE is_mandatory = TRUE AND is_received = TRUE) as mandatory_received,
            COUNT(*) as total_required,
            (SELECT COUNT(*) FROM tender_received_documents WHERE tender_id = %s) as total_received
        FROM tender_required_documents 
        WHERE tender_id = %s
    """, (tender_id, tender_id))
    row = cur.fetchone()
    cur.close()
    
    mandatory_met = f"{row['mandatory_received']}/{row['mandatory_total']}" if row['mandatory_total'] else "0/0"
    total_received = f"{row['total_received']}/{row['total_required']}"
    
    return {
        "mandatory_met": mandatory_met,
        "documents_received": total_received
    }

########################################################  old code for mock db ########################################################
# # modules/completeness_checker.py   ← FINAL SQLITE VERSION
# import sqlite3
# from typing import List, Dict

# def get_missing_documents(tender_id: int, conn) -> List[Dict]:
#     query = """
#         SELECT 
#             trd.document_name,
#             trd.document_category,
#             trd.description,
#             trd.source,
#             ta.addendum_number
#         FROM tender_required_documents trd
#         LEFT JOIN tender_received_documents trc 
#             ON trd.tender_id = trc.tender_id 
#             AND TRIM(trd.document_name) = TRIM(trc.document_name)
#         LEFT JOIN tender_addenda ta ON trd.introduced_by_addendum_id = ta.addendum_id
#         WHERE trd.tender_id = ?
#           AND trd.is_mandatory = 1
#           AND trc.received_doc_id IS NULL
#         ORDER BY trd.added_date;
#     """
#     cur = conn.cursor()
#     cur.execute(query, (tender_id,))
#     rows = cur.fetchall()
#     cur.close()

#     missing = []
#     for row in rows:
#         missing.append({
#             "document_name": row[0],
#             "category": row[1] or "Uncategorized",
#             "description": row[2],
#             "source": "Addendum #" + str(row[4]) if row[4] else "Original",
#         })
#     return missing


# def get_document_stats(tender_id: int, conn) -> Dict:
#     cur = conn.cursor()
#     cur.execute("""
#         SELECT 
#             COUNT(*) FILTER (WHERE is_mandatory = 1) as mandatory_total,
#             COUNT(*) FILTER (WHERE is_mandatory = 1 AND is_received = 1) as mandatory_received,
#             COUNT(*) as total_required,
#             (SELECT COUNT(*) FROM tender_received_documents WHERE tender_id = ?) as total_received
#         FROM tender_required_documents 
#         WHERE tender_id = ?
#     """, (tender_id, tender_id))
#     row = cur.fetchone()
#     cur.close()
    
#     mandatory_met = f"{row[1]}/{row[0]}" if row[0] else "0/0"
#     total_received = f"{row[3]}/{row[2]}"
    
#     return {
#         "mandatory_met": mandatory_met,
#         "documents_received": total_received
#     }