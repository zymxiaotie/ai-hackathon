# Complete Database Architecture
## Tender Intelligence System with n8n Orchestration

**Version:** 2.0  
**Last Updated:** November 2025  
**Owner:** Automated Reporting & Matcher Module Team

---

## Architecture Overview

The system uses **polyglot persistence** with n8n workflow orchestration:
- **SQL Database** (SQLite/PostgreSQL): Structured tender data, company profile, processing state
- **Vector Database** (ChromaDB/Pinecone): Full document chunks for semantic search
- **n8n**: Workflow orchestration and event-driven coordination

**Golden Thread:** `tender_id` links all data across SQL, Vector DB, and workflow logs.

---

## Database Design

### Group 1: Tender Master Data (SQL)

#### `tenders` - Master tender registry
```sql
CREATE TABLE tenders (
  tender_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tender_title VARCHAR(500) NOT NULL,
  tender_reference_number VARCHAR(100) NOT NULL UNIQUE,
  issuing_authority VARCHAR(200),
  
  -- Key Dates
  submission_deadline DATETIME NOT NULL,
  clarification_closing_date DATETIME,
  tender_validity_period VARCHAR(100),
  
  -- Submission Details
  submission_portal_url VARCHAR(500),
  submission_mode VARCHAR(100), -- Online/Physical/Both
  number_of_copies_required INTEGER,
  required_signatory_authority VARCHAR(200),
  submission_instructions TEXT,
  
  -- Project Details
  project_name VARCHAR(300),
  site_location VARCHAR(300),
  project_start_date DATE,
  project_completion_date DATE,
  contract_type VARCHAR(100), -- PSSCOC/FIDIC/etc
  scope_of_works TEXT,
  
  -- Contract Terms
  liquidated_damages VARCHAR(200),
  performance_bond_percentage DECIMAL(5,2),
  retention_percentage DECIMAL(5,2),
  defects_liability_period VARCHAR(100),
  warranty_period VARCHAR(100),
  
  -- Metadata
  document_source VARCHAR(500), -- S3/cloud path to original PDF
  processing_status VARCHAR(50) DEFAULT 'pending', -- pending/processing/completed/failed
  processed_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tender_ref ON tenders(tender_reference_number);
CREATE INDEX idx_submission_deadline ON tenders(submission_deadline);
CREATE INDEX idx_processing_status ON tenders(processing_status);
```

#### `tender_required_documents` - What client demands
```sql
CREATE TABLE tender_required_documents (
  requirement_doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tender_id INTEGER NOT NULL,
  document_name VARCHAR(300) NOT NULL, -- "BOQ", "Method Statement", etc
  document_category VARCHAR(100), -- Technical/Financial/Admin
  is_mandatory BOOLEAN DEFAULT TRUE,
  is_received BOOLEAN DEFAULT FALSE,
  description TEXT,
  
  -- Addendum tracking
  source VARCHAR(50) DEFAULT 'original', -- original/addendum/clarification
  introduced_by_addendum_id INTEGER,
  added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
  FOREIGN KEY (introduced_by_addendum_id) REFERENCES tender_addenda(addendum_id)
);

CREATE INDEX idx_tender_req_docs ON tender_required_documents(tender_id);
```

#### `tender_received_documents` - What we actually got
```sql
CREATE TABLE tender_received_documents (
  received_doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tender_id INTEGER NOT NULL,
  document_name VARCHAR(300) NOT NULL,
  file_path VARCHAR(500),
  file_size_kb INTEGER,
  received_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  uploaded_by VARCHAR(200),
  
  FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX idx_tender_recv_docs ON tender_received_documents(tender_id);
```

**Completeness Check Query:**
```sql
-- Shows missing mandatory documents
SELECT trd.document_name, trd.document_category, trd.is_mandatory
FROM tender_required_documents trd
LEFT JOIN tender_received_documents recv 
  ON trd.tender_id = recv.tender_id 
  AND trd.document_name = recv.document_name
WHERE trd.tender_id = ?
  AND recv.received_doc_id IS NULL
  AND trd.is_mandatory = TRUE;
```

---

### Group 2: Qualification Tracking (SQL + Vector)

#### `tender_qualification_criteria` - Eligibility requirements
```sql
CREATE TABLE tender_qualification_criteria (
  criteria_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tender_id INTEGER NOT NULL,
  
  -- Requirement Details
  criteria_type VARCHAR(50) NOT NULL, -- LICENSE/EXPERIENCE/FINANCIAL/CERTIFICATION/COMPLIANCE
  criteria_description TEXT NOT NULL,
  criteria_value VARCHAR(200), -- For numeric requirements: "$5M", "3 projects"
  
  -- Matching Results
  is_met BOOLEAN, -- NULL=not checked, TRUE=met, FALSE=not met
  notes TEXT, -- Explanation from Matcher module
  checked_date DATETIME,
  
  -- Tracking
  source VARCHAR(50) DEFAULT 'original', -- original/addendum/clarification
  introduced_by_addendum_id INTEGER,
  added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  requires_recheck BOOLEAN DEFAULT FALSE, -- Flag for re-running matcher
  
  FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
  FOREIGN KEY (introduced_by_addendum_id) REFERENCES tender_addenda(addendum_id)
);

CREATE INDEX idx_tender_criteria ON tender_qualification_criteria(tender_id);
CREATE INDEX idx_requires_recheck ON tender_qualification_criteria(requires_recheck);
```

**Eligibility Status Query:**
```sql
-- Summary for report generation
SELECT 
  criteria_type,
  criteria_description,
  is_met,
  notes,
  source,
  introduced_by_addendum_id
FROM tender_qualification_criteria
WHERE tender_id = ?
ORDER BY added_date ASC;
```

#### Vector Database: `tender_document_chunks`

Stores full tender document for semantic search (not SQL):

```python
# ChromaDB/Pinecone structure
{
  "chunk_id": "tender_123_chunk_5",
  "tender_id": 123,  # Links back to SQL
  "chunk_text": "The contractor shall possess BCA License Grade L6...",
  "embedding": [0.123, -0.456, ...],  # Vector embedding
  "metadata": {
    "page_number": 12,
    "section": "Qualification Requirements",
    "document_version": "original"
  }
}
```

**Use case:** When qualification is disputable, query vector DB for context:
```python
# Semantic search for clarification
results = vector_db.query(
    query_text="BCA license requirements",
    filter={"tender_id": 123},
    n_results=5
)
```

---

### Group 3: Addenda & Change Management (SQL)

#### `tender_addenda` - Addendum/clarification events
```sql
CREATE TABLE tender_addenda (
  addendum_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tender_id INTEGER NOT NULL,
  
  -- Addendum Details
  addendum_number INTEGER NOT NULL, -- 1, 2, 3...
  addendum_type VARCHAR(50), -- Addendum/Clarification/Corrigendum
  title VARCHAR(300),
  summary TEXT,
  
  -- Source
  email_source VARCHAR(500), -- Email ID or URL
  attachment_paths TEXT, -- JSON array of file paths
  received_date DATETIME NOT NULL,
  
  -- Processing
  processed BOOLEAN DEFAULT FALSE,
  processed_date DATETIME,
  
  FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
  UNIQUE(tender_id, addendum_number)
);

CREATE INDEX idx_tender_addenda ON tender_addenda(tender_id);
```

#### `addendum_changes` - Field-level audit trail
```sql
CREATE TABLE addendum_changes (
  change_id INTEGER PRIMARY KEY AUTOINCREMENT,
  addendum_id INTEGER NOT NULL,
  
  -- What changed
  affected_table VARCHAR(100) NOT NULL, -- tenders/tender_qualification_criteria/etc
  affected_record_id INTEGER NOT NULL,
  field_name VARCHAR(100) NOT NULL,
  old_value TEXT,
  new_value TEXT,
  
  change_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (addendum_id) REFERENCES tender_addenda(addendum_id) ON DELETE CASCADE
);

CREATE INDEX idx_addendum_changes ON addendum_changes(addendum_id);
```

**Audit Query:**
```sql
-- Show all changes from Addendum #2
SELECT 
  ac.affected_table,
  ac.field_name,
  ac.old_value,
  ac.new_value,
  ta.addendum_number,
  ta.title
FROM addendum_changes ac
JOIN tender_addenda ta ON ac.addendum_id = ta.addendum_id
WHERE ta.tender_id = ? AND ta.addendum_number = 2;
```

#### `tender_document_versions` - Document version control
```sql
CREATE TABLE tender_document_versions (
  document_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tender_id INTEGER NOT NULL,
  
  -- Document Details
  document_name VARCHAR(300) NOT NULL, -- "BOQ Template"
  version_number VARCHAR(50) NOT NULL, -- "1.0", "2.0", "Rev A"
  file_path VARCHAR(500) NOT NULL,
  file_size_kb INTEGER,
  
  -- Version Control
  is_current BOOLEAN DEFAULT TRUE,
  superseded_by INTEGER, -- FK to newer version
  introduced_by_addendum_id INTEGER,
  
  uploaded_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
  FOREIGN KEY (superseded_by) REFERENCES tender_document_versions(document_version_id),
  FOREIGN KEY (introduced_by_addendum_id) REFERENCES tender_addenda(addendum_id)
);

CREATE INDEX idx_doc_versions ON tender_document_versions(tender_id);
CREATE INDEX idx_current_docs ON tender_document_versions(tender_id, is_current);
```

**Version History Query:**
```sql
-- Show document evolution
SELECT 
  document_name,
  version_number,
  is_current,
  introduced_by_addendum_id,
  uploaded_date
FROM tender_document_versions
WHERE tender_id = ? AND document_name = 'BOQ Template'
ORDER BY uploaded_date ASC;
```

---

### Group 4: Company Profile (SQL + Vector)

#### SQL: Structured company data

**`company_licenses`**
```sql
CREATE TABLE company_licenses (
  license_id INTEGER PRIMARY KEY AUTOINCREMENT,
  license_type VARCHAR(100) NOT NULL, -- BCA/HDB/LTA
  license_grade VARCHAR(50), -- L6/CW01/etc
  license_category VARCHAR(200), -- General Building/Civil Engineering
  issue_date DATE,
  expiry_date DATE,
  status VARCHAR(50) DEFAULT 'active' -- active/expired/suspended
);
```

**`company_certifications`**
```sql
CREATE TABLE company_certifications (
  certification_id INTEGER PRIMARY KEY AUTOINCREMENT,
  certification_name VARCHAR(200) NOT NULL, -- ISO 9001:2015
  certification_body VARCHAR(200),
  issue_date DATE,
  expiry_date DATE,
  certificate_number VARCHAR(100),
  status VARCHAR(50) DEFAULT 'active'
);
```

**`company_projects`**
```sql
CREATE TABLE company_projects (
  project_id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_name VARCHAR(300) NOT NULL,
  contract_value DECIMAL(15,2),
  completion_date DATE,
  client_name VARCHAR(200),
  project_type VARCHAR(100), -- Renovation/New Construction/Civil Works
  project_description TEXT,
  location VARCHAR(300)
);
```

**`company_financials`**
```sql
CREATE TABLE company_financials (
  financial_id INTEGER PRIMARY KEY AUTOINCREMENT,
  financial_year INTEGER NOT NULL,
  annual_turnover DECIMAL(15,2),
  paid_up_capital DECIMAL(15,2),
  net_worth DECIMAL(15,2),
  updated_date DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Vector Database: `company_capabilities_chunks`

```python
# Semantic search on company experience
{
  "chunk_id": "company_capability_3",
  "capability_text": "Successfully completed heritage conservation works at National Museum, including structural retrofitting and facade restoration...",
  "embedding": [0.789, -0.234, ...],
  "metadata": {
    "project_id": 45,
    "capability_category": "Heritage & Conservation"
  }
}
```

**Matcher uses this when:** Tender requires "experience in heritage restoration" but company profile says "conservation works" - semantic match needed.

---

### Group 5: Processing Coordination (SQL)

#### `processing_log` - n8n orchestration tracking
```sql
CREATE TABLE processing_log (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tender_id INTEGER NOT NULL,
  
  -- Workflow Details
  module_name VARCHAR(100) NOT NULL, -- parser/matcher/reporter/email
  workflow_execution_id VARCHAR(200), -- n8n execution ID
  status VARCHAR(50) NOT NULL, -- started/completed/failed
  
  -- Timing
  started_at DATETIME NOT NULL,
  completed_at DATETIME,
  duration_seconds INTEGER,
  
  -- Results
  output_data TEXT, -- JSON of results
  error_message TEXT,
  
  FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
);

CREATE INDEX idx_processing_log ON processing_log(tender_id, module_name);
```

---

## n8n Workflow Coordination

### Workflow 1: New Tender Processing

```
┌─────────────────────────────────────────┐
│ EMAIL TRIGGER: New tender email         │
│ - Extracts: tender_reference_number     │
│ - Downloads: PDF attachments            │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ SQL: INSERT tenders                      │
│ - Status: 'pending'                      │
│ - Returns: tender_id = 123               │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ HTTP REQUEST: Document Parser API       │
│ POST /parse                              │
│ Body: {tender_id: 123, pdf_path: "..."} │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ PARSER EXTRACTS:                         │
│ 1. Tender metadata → SQL: tenders        │
│ 2. Required docs → tender_required_docs  │
│ 3. Qualification → tender_qualification  │
│ 4. Full text chunks → Vector DB          │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ COMPLETENESS CHECK                       │
│ SQL: LEFT JOIN required vs received     │
│ Flag: missing_mandatory_docs             │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ HTTP REQUEST: Matcher API                │
│ POST /matcher/api/check-eligibility      │
│ Body: {tender_id: 123, requirements:[]}  │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ MATCHER LOGIC:                           │
│ For each criteria:                       │
│ 1. Check SQL (licenses, projects, $$$)   │
│ 2. If ambiguous → Vector DB semantic     │
│ 3. Update: is_met, notes                 │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ HTTP REQUEST: Report Generator API       │
│ POST /report/generate                    │
│ Body: {tender_id: 123}                   │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ GENERATE REPORT:                         │
│ 1. Query SQL: tender + criteria + docs   │
│ 2. Render Jinja2 template                │
│ 3. Send email via SMTP                   │
│ 4. Update: processing_status=completed   │
└─────────────────────────────────────────┘
```

### Workflow 2: Addendum Processing

```
┌─────────────────────────────────────────┐
│ EMAIL TRIGGER: Addendum email            │
│ - Subject contains: "Addendum" or        │
│   "Clarification" + tender_ref           │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ SQL: Find tender_id from reference       │
│ INSERT tender_addenda                    │
│ - Returns: addendum_id = 456             │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ HTTP REQUEST: Document Parser API        │
│ POST /parse-addendum                     │
│ Body: {addendum_id: 456, pdf_path: "..."│
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ PARSER CLASSIFIES (Rule-based):         │
│                                          │
│ If contains "submit", "provide":         │
│   → INSERT tender_required_documents     │
│                                          │
│ If contains "must have", "certified":    │
│   → INSERT tender_qualification_criteria │
│     (set requires_recheck=TRUE)          │
│                                          │
│ If "updated", "revised":                 │
│   → INSERT tender_document_versions      │
│   → UPDATE old version (is_current=FALSE)│
│                                          │
│ Field changes:                           │
│   → INSERT addendum_changes              │
│   → UPDATE original table                │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ CONDITIONAL: Check requires_recheck      │
│ SQL: SELECT COUNT(*) WHERE               │
│      requires_recheck=TRUE               │
└────────────────┬────────────────────────┘
                 ↓ (if > 0)
┌─────────────────────────────────────────┐
│ HTTP REQUEST: Matcher API                │
│ - Only checks NEW criteria               │
│ - Updates is_met + notes                 │
│ - Sets requires_recheck=FALSE            │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ HTTP REQUEST: Report Generator           │
│ - Generates UPDATED report               │
│ - Highlights addendum changes            │
│ - Email subject: "⚠️ ADDENDUM #1"       │
└─────────────────────────────────────────┘
```

---

## Matcher Module Logic

### Rule-Based Classification (MVP)

```python
def classify_requirement(criteria_description: str):
    """
    Determines if requirement is:
    - qualification_criterion (capability check)
    - required_document (submission needed)
    - both
    """
    lower_desc = criteria_description.lower()
    
    doc_keywords = ["submit", "provide", "attach", "include", 
                    "enclose", "upload", "deliver"]
    qual_keywords = ["must have", "must possess", "minimum", 
                     "certified", "licensed", "experience in"]
    
    is_document = any(kw in lower_desc for kw in doc_keywords)
    is_qualification = any(kw in lower_desc for kw in qual_keywords)
    
    if is_document and is_qualification:
        return "both"
    elif is_document:
        return "required_document"
    elif is_qualification:
        return "qualification_criterion"
    else:
        return "qualification_criterion"  # Default
```

### Matching Logic Flow

```python
def check_eligibility(tender_id, requirements):
    results = []
    
    for req in requirements:
        if req.criteria_type == "LICENSE":
            result = check_license(req.criteria_description)
            
        elif req.criteria_type == "EXPERIENCE":
            result = check_experience(req.criteria_value)
            
        elif req.criteria_type == "FINANCIAL":
            result = check_financials(req.criteria_value)
            
        elif req.criteria_type == "CERTIFICATION":
            result = check_certification(req.criteria_description)
            
        else:  # COMPLIANCE or unclear
            # Fall back to semantic search
            result = check_semantic_match(req.criteria_description)
        
        results.append({
            "requirement_id": req.criteria_id,
            "is_met": result.is_met,
            "notes": result.explanation
        })
    
    return results
```

---

## Report Generation

### Tender Overview Report Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>Tender Overview Report</title>
</head>
<body>
  <h1>Tender Overview Report</h1>
  
  <!-- Tender Information -->
  <section>
    <h2>Tender Information</h2>
    <table>
      <tr><td>Title:</td><td>{{ tender.title }}</td></tr>
      <tr><td>Reference:</td><td>{{ tender.reference_number }}</td></tr>
      <tr><td>Issuing Authority:</td><td>{{ tender.issuing_authority }}</td></tr>
      <tr><td>Submission Deadline:</td><td class="urgent">{{ tender.submission_deadline }}</td></tr>
    </table>
  </section>
  
  <!-- Eligibility Status -->
  <section>
    <h2>Eligibility Status</h2>
    <table>
      <thead>
        <tr>
          <th>Requirement</th>
          <th>Status</th>
          <th>Notes</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {% for criteria in qualification_criteria %}
        <tr>
          <td>{{ criteria.description }}</td>
          <td>
            {% if criteria.is_met %}
              <span class="status-met">✓ MET</span>
            {% else %}
              <span class="status-not-met">✗ NOT MET</span>
            {% endif %}
          </td>
          <td>{{ criteria.notes }}</td>
          <td>
            {% if criteria.source == 'addendum' %}
              <span class="badge-addendum">Addendum #{{ criteria.addendum_number }}</span>
            {% else %}
              Original
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </section>
  
  <!-- Document Completeness -->
  <section>
    <h2>Document Completeness</h2>
    {% if missing_documents %}
    <div class="alert-warning">
      <strong>⚠️ Missing Documents:</strong>
      <ul>
        {% for doc in missing_documents %}
        <li>{{ doc.document_name }} ({{ doc.category }})</li>
        {% endfor %}
      </ul>
    </div>
    {% else %}
    <div class="alert-success">
      ✓ All required documents received
    </div>
    {% endif %}
  </section>
  
  <!-- Addenda Summary -->
  {% if addenda %}
  <section>
    <h2>Addenda & Clarifications</h2>
    {% for addendum in addenda %}
    <div class="addendum-box">
      <strong>Addendum #{{ addendum.number }}</strong> ({{ addendum.received_date }})
      <p>{{ addendum.summary }}</p>
    </div>
    {% endfor %}
  </section>
  {% endif %}
  
  <!-- Recommendation -->
  <section>
    <h2>Bid Recommendation</h2>
    {% if all_requirements_met and no_missing_docs %}
    <div class="recommendation-go">
      <strong>✓ RECOMMENDED TO BID</strong>
      <p>Company meets all eligibility criteria and document requirements.</p>
    </div>
    {% else %}
    <div class="recommendation-no-go">
      <strong>✗ NOT RECOMMENDED TO BID</strong>
      <p>Company does not meet all requirements. Review carefully before proceeding.</p>
    </div>
    {% endif %}
  </section>
</body>
</html>
```

---

## Key Design Decisions

### 1. **Dual Storage Strategy**
- **SQL:** Structured data, exact matching, reporting, dashboards
- **Vector DB:** Full documents, semantic search, disputable cases

### 2. **tender_id as Golden Thread**
- Every table references tender_id
- Enables cross-database queries
- Simplifies n8n orchestration

### 3. **Addenda = Both Event + Effects**
- `tender_addenda`: The event (what happened)
- `addendum_changes`: The effects (what changed)
- `tender_qualification_criteria.source`: Tracks origin

### 4. **Dual-Nature Requirements**
- Same addendum requirement can create:
  - Qualification criterion (can we bid?)
  - Required document (what to submit?)
- Parser classifies via rule-based keywords

### 5. **requires_recheck Flag**
- Addenda trigger selective re-matching
- Don't re-run entire matcher, only new criteria
- Improves performance and cost

---

## Next Steps

1. **Implement SQL schema** in SQLite for MVP
2. **Setup n8n workflows** for tender + addendum processing
3. **Build Matcher module** with rule-based logic
4. **Create Jinja2 report template**
5. **Test end-to-end** with 3 sample tenders + addenda
6. **Migration path** to PostgreSQL + production Vector DB

---

**Questions or clarifications?** Review this with your team and identify any gaps before implementation.