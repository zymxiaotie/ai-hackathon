# create_local_db.py
# Run this once: python create_local_db.py
# Generates tender_intel.db with all data from the mockup

import sqlite3
from datetime import datetime, timedelta
import os

DB_PATH = "tender_intel.db"
print("🚀 Creating local Tender Intelligence DB...")

# Remove old DB if exists
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("🗑️  Removed old database")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Enable foreign keys
cur.execute("PRAGMA foreign_keys = ON;")

# =============================================
# 1. FULL SCHEMA (SQLite compatible)
# =============================================

schema_sql = """
-- tenders
CREATE TABLE tenders (
    tender_id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_title                 TEXT NOT NULL,
    tender_reference_number      TEXT NOT NULL UNIQUE,
    issuing_authority            TEXT,
    submission_deadline          TEXT NOT NULL,
    clarification_closing_date   TEXT,
    tender_validity_period       TEXT,
    submission_portal_url        TEXT,
    submission_mode              TEXT,
    number_of_copies_required    INTEGER,
    required_signatory_authority TEXT,
    submission_instructions      TEXT,
    project_name                 TEXT,
    site_location                TEXT,
    project_start_date           TEXT,
    project_completion_date     TEXT,
    contract_type                TEXT,
    scope_of_works               TEXT,
    liquidated_damages           TEXT,
    performance_bond_percentage  REAL,
    retention_percentage         REAL,
    defects_liability_period     TEXT,
    warranty_period              TEXT,
    document_source              TEXT,
    processing_status            TEXT DEFAULT 'completed',
    processed_date               TEXT DEFAULT CURRENT_TIMESTAMP,
    created_date                 TEXT DEFAULT CURRENT_TIMESTAMP,
    last_updated                 TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Required Documents
CREATE TABLE tender_required_documents (
    requirement_doc_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id                INTEGER NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    document_name            TEXT NOT NULL,
    document_category        TEXT,
    is_mandatory             INTEGER DEFAULT 1,
    is_received              INTEGER DEFAULT 0,
    description              TEXT,
    source                   TEXT DEFAULT 'original',
    introduced_by_addendum_id INTEGER,
    added_date               TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Received Documents
CREATE TABLE tender_received_documents (
    received_doc_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id         INTEGER NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    document_name     TEXT NOT NULL,
    file_path         TEXT,
    file_size_kb      INTEGER,
    received_date     TEXT DEFAULT CURRENT_TIMESTAMP,
    ured_by       TEXT
);

-- Qualification Criteria
CREATE TABLE tender_qualification_criteria (
    criteria_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id                 INTEGER NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    criteria_type             TEXT NOT NULL,
    criteria_description      TEXT NOT NULL,
    criteria_value            TEXT,
    is_met                    INTEGER,
    notes                     TEXT,
    checked_date              TEXT,
    source                    TEXT DEFAULT 'original',
    introduced_by_addendum_id INTEGER,
    requires_recheck          INTEGER DEFAULT 0,
    added_date                TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Addenda
CREATE TABLE tender_addenda (
    addendum_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id        INTEGER NOT NULL REFERENCES tenders(tender_id) ON DELETE CASCADE,
    addendum_number  INTEGER NOT NULL,
    addendum_type    TEXT,
    title            TEXT,
    summary          TEXT,
    email_source     TEXT,
    attachment_paths TEXT,
    received_date    TEXT NOT NULL,
    processed        INTEGER DEFAULT 0,
    processed_date   TEXT,
    UNIQUE(tender_id, addendum_number)
);

-- Company Profile
CREATE TABLE company_licenses (
    license_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    license_type     TEXT NOT NULL,
    license_grade    TEXT,
    license_category TEXT,
    issue_date       TEXT,
    expiry_date      TEXT,
    status           TEXT DEFAULT 'active'
);

CREATE TABLE company_certifications (
    certification_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    certification_name TEXT NOT NULL,
    certification_body TEXT,
    issue_date         TEXT,
    expiry_date        TEXT,
    certificate_number TEXT,
    status             TEXT DEFAULT 'active'
);

CREATE TABLE company_projects (
    project_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name        TEXT NOT NULL,
    contract_value      REAL,
    completion_date     TEXT,
    client_name         TEXT,
    project_type        TEXT,
    project_description TEXT,
    location            TEXT
);

CREATE TABLE company_financials (
    financial_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    financial_year    INTEGER NOT NULL,
    annual_turnover   REAL,
    paid_up_capital   REAL,
    net_worth         REAL,
    updated_date      TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

for statement in schema_sql.split(";\n"):
    if statement.strip():
        cur.execute(statement)

print("✅ Schema created")

# =============================================
# 2. INSERT SAMPLE DATA (Exact mockup match)
# =============================================

# Tender from mockup
cur.execute("""
INSERT INTO tenders (
    tender_title, tender_reference_number, issuing_authority,
    submission_deadline, clarification_closing_date,
    project_name, site_location, project_start_date, project_completion_date,
    contract_type, liquidated_damages, performance_bond_percentage,
    retention_percentage, defects_liability_period
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""", (
    "HDB Renovation at Ang Mo Kio Block 123",
    "HDB/2025/REN/001",
    "Housing & Development Board",
    "2025-12-15 12:00:00",  # 7 days from today (Nov 18)
    "2025-12-08 17:00:00",
    "AMK Block 123 Upgrading Works",
    "Ang Mo Kio Avenue 3, Singapore",
    "2026-01-15",
    "2026-06-30",
    "PSSCOC (Public Sector Standard Conditions of Contract)",
    "$1,000 per day of delay",
    10.0,
    5.0,
    "12 months from completion"
))

tender_id = cur.lastrowid
print(f"✅ Tender created: {tender_id}")

# Required Documents
req_docs = [
    ("BOQ Template v2.0", "Financial", 1, 1, None, "original"),
    ("Method Statement", "Technical", 1, 1, None, "original"),
    ("Technical Specifications", "Technical", 1, 1, None, "original"),
    ("Safety Risk Assessment", "Safety", 1, 0, "Must be signed by WSH officer", "original"),
    ("Site Plan", "Technical", 1, 0, None, "original"),
]

for doc in req_docs:
    cur.execute("""
        INSERT INTO tender_required_documents 
        (tender_id, document_name, document_category, is_mandatory, is_received, description, source)
        VALUES (?,?,?,?,?,?,?)
    """, (tender_id, *doc))

# Received Documents (only some)
cur.executemany("""
    INSERT INTO tender_received_documents (tender_id, document_name, received_date)
    VALUES (?,?,?)
""", [
    (tender_id, "BOQ Template v2.0", "2025-11-10"),
    (tender_id, "Method Statement", "2025-11-12"),
    (tender_id, "Technical Specifications", "2025-11-10"),
])

# Qualification Criteria (matches mockup exactly)
criteria = [
    ("LICENSE", "BCA L6 License (General Building)", None, 1, "Company holds valid BCA L6. Expiry: 31-Dec-2026", "original"),
    ("CERTIFICATION", "ISO 9001:2015 Certification", None, 1, "Valid until 15-Aug-2026", "original"),
    ("EXPERIENCE", "Minimum 3 completed projects >$2M in last 5 years", "3 projects >$2M", 0, "Only 2 qualifying projects found: Tampines HDB ($2.5M, 2023), Jurong West CC ($3.1M, 2024)", "original"),
    ("FINANCIAL", "Minimum annual turnover of $5M", "$5M", 1, "FY2024: $7.2M", "original"),
    ("COMPLIANCE", "Valid MOM work permits for all foreign workers", None, 0, "Need to verify work permits. Company has 3 foreign workers.", "addendum"),
]

for c in criteria:
    cur.execute("""
        INSERT INTO tender_qualification_criteria 
        (tender_id, criteria_type, criteria_description, criteria_value, is_met, notes, source)
        VALUES (?,?,?,?,?,?,?)
    """, (tender_id, *c))

# Addendum #1
cur.execute("""
INSERT INTO tender_addenda 
(tender_id, addendum_number, title, summary, received_date)
VALUES (?,?,?,?,?)
""", (tender_id, 1, "Compliance Update", "BOQ template updated to v2.0, deadline extended, new MOM compliance requirement added", "2025-11-07"))

# Company Profile (so matcher works)
cur.executescript("""
INSERT INTO company_licenses (license_type, license_grade, expiry_date) VALUES
('BCA', 'L6', '2026-12-31');

INSERT INTO company_certifications (certification_name, expiry_date) VALUES
('ISO 9001:2015', '2026-08-15');

INSERT INTO company_projects (project_name, contract_value, completion_date) VALUES
('Tampines HDB Upgrading', 2500000, '2023-06-15'),
('Jurong West Community Club', 3100000, '2024-09-20');

INSERT INTO company_financials (financial_year, annual_turnover) VALUES
(2024, 7200000);
""")

conn.commit()
print("✅ Sample data inserted – matches interactive mockup perfectly!")

# Final check
cur.execute("SELECT COUNT(*) FROM tenders")
total = cur.fetchone()[0]
print(f"🎉 Local DB ready: {DB_PATH} ({total} tender loaded)")

print("""
Next steps:
1. Run: python -m modules.report_generator <tender_id>  → generates exact HTML report
2. Or open with DB Browser for SQLite to explore
""")

conn.close()