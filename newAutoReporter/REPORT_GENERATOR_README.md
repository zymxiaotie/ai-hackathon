# Tender Intelligence Report Generator

AI-powered report generation system for the Construction Tender Intelligence Assistant, using Bitdeer AI API for intelligent analysis and recommendations.

## 📋 Overview

This system automatically generates comprehensive, interactive HTML reports for construction tenders, providing:

- **Executive Summary** with AI-powered bid recommendations
- **Eligibility Analysis** distinguishing mandatory vs. optional criteria
- **Document Completeness Tracking** with automated alerts
- **Action Items** with automated system responses
- **Detailed Reasoning** explaining recommendations

## 🎯 Key Features

### 1. Intelligent Criteria Classification

The system automatically classifies qualification criteria into three severity levels:

- **MANDATORY** ⛔: Legal/regulatory requirements (e.g., BCA license, ISO9001, work permits)
  - Failing = automatic disqualification
  - No negotiation possible
  
- **IMPORTANT** ⚠️: Competitive requirements (e.g., performance bond, past projects)
  - Affects competitiveness
  - Management can decide to proceed or negotiate
  
- **OPTIONAL** ℹ️: Preferred but not critical
  - Improves bid quality if met

### 2. Completeness Calculation

The system calculates document completeness as:

```
Completeness = (Received Mandatory Docs / Total Mandatory Docs) × 100%
```

**Example:**
- 10 total documents required
- 8 are mandatory, 2 are optional
- 6 mandatory received, 1 optional received
- **Completeness = (6/8) × 100% = 75%**

This focuses on mandatory items critical for submission acceptance.

### 3. Automated System Actions

When issues are detected, the system automatically:

**For Missing Mandatory Documents:**
- Sends email alerts to Document Coordinator
- Logs in tracking dashboard with HIGH priority
- Schedules daily reminders
- Flags tender as "INCOMPLETE"
- Blocks submission workflow

**For Failed Mandatory Criteria:**
- Flags tender as "NON-VIABLE"
- Alerts management immediately
- Adds to disqualification report

**For Failed Important Criteria:**
- Escalates to Project Director/QS for decision
- Provides impact analysis
- Tracks decision in audit trail

### 4. Bid Recommendation Logic

```
IF mandatory_criteria_pass_rate < 100%:
    RECOMMENDATION = DISQUALIFIED
    
ELIF critical_issues AND mandatory_docs < 100%:
    RECOMMENDATION = NOT_RECOMMEND
    
ELIF critical_issues OR mandatory_docs < 100%:
    RECOMMENDATION = CONDITIONAL
    
ELIF important_pass_rate >= 80% AND mandatory_docs >= 90%:
    RECOMMENDATION = RECOMMEND
    
ELSE:
    RECOMMENDATION = CONDITIONAL
```

## 🚀 Quick Start

### Installation

```bash
# Install required packages
pip install --break-system-packages requests psycopg2-binary openai

# Set environment variables
export BITDEER_API_KEY="your-api-key-here"
export DB_HOST="localhost"
export DB_NAME="tender_intelligence"
export DB_USER="postgres"
export DB_PASSWORD="your-password"
```

### Usage

#### 1. Generate Report for Single Tender

```bash
# From database
python report_integration.py single --tender-id "123" --format html

# Test with sample data
python report_integration.py test
```

#### 2. Generate Reports for All Tenders

```bash
python report_integration.py batch --format both
```

#### 3. Programmatic Usage

```python
from report_integration import generate_tender_report

# Generate report
report_path = generate_tender_report(
    tender_id="123",
    output_format="html"
)

print(f"Report generated: {report_path}")
```

## 📁 File Structure

```
/home/claude/
├── report_generator.py           # Core report generation engine
├── html_report_generator.py      # HTML template generator
├── report_integration.py         # Database integration
└── README.md                      # This file

/mnt/user-data/outputs/tender_reports/
└── tender_report_*.html          # Generated reports
```

## 🔧 Integration with docparser.py

### Option 1: Add to Existing Pipeline

Add to `docparser.py` after tender processing:

```python
from report_integration import generate_tender_report

def process_tender_document(...):
    # ... existing processing code ...
    
    if tender_id:
        # Generate report automatically
        try:
            report_path = generate_tender_report(tender_id, "html")
            logger.info(f"Report generated: {report_path}")
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
    
    return tender_id
```

### Option 2: Scheduled Report Generation

Add to monitoring loop in `docparser.py`:

```python
def monitor_google_drive():
    # ... existing monitoring code ...
    
    # Generate reports for newly processed tenders
    if processed_count > 0:
        logger.info("Generating reports for processed tenders...")
        generate_reports_for_all_tenders("html")
```

### Option 3: On-Demand via Flask API

Add to `docparser.py` Flask API:

```python
@app.route("/generate-report/<tender_id>", methods=["POST"])
def api_generate_report(tender_id):
    try:
        report_path = generate_tender_report(tender_id, "html")
        return jsonify({
            "status": "success",
            "report_path": report_path
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

## 📊 Report Sections

### Section 1: Executive Summary
- Bid recommendation with confidence score
- Key metrics dashboard
- Calculation methodology
- Summary reasoning

### Section 2: Tender Overview
- Basic tender information
- Project details
- Contract terms

### Section 3: Eligibility Status
- Criteria classification (mandatory/important/optional)
- Pass/fail status
- Impact analysis
- Evidence and notes

### Section 4: Document Register
- Document completeness metrics
- Missing document alerts
- Automated system actions

### Section 5: Addenda Tracker
- Change tracking
- Version control
- Impact assessment

### Section 6: Next Actions
- Prioritized action items
- Ownership assignment
- Automated system responses
- Impact explanation

### Section 7: Detailed Reasoning
- AI-powered analysis
- Completeness calculation explanation
- Criteria impact breakdown
- System usefulness explanation

## 🤖 AI-Powered Features

The system uses Bitdeer AI (GPT model) for:

1. **Criteria Severity Determination**
   - Analyzes criterion description
   - Determines if mandatory, important, or optional
   - Considers legal/regulatory implications

2. **Executive Summary Generation**
   - Concise 2-3 sentence summary
   - Explains recommendation rationale
   - Highlights critical factors

3. **Detailed Reasoning**
   - 3-4 paragraph analysis
   - Explains completeness calculation
   - Distinguishes mandatory vs. important criteria
   - Describes system actions for missing documents
   - Explains value to SME decision-makers

## 📧 Email Integration (Future)

To integrate with email delivery:

```python
from report_integration import send_report_via_email

# Generate and send report
report_path = generate_tender_report("123", "html")

send_report_via_email(
    report_path=report_path,
    recipient_emails=[
        "qs@company.com",
        "manager@company.com"
    ]
)
```

## 🔍 Addressing Feedback

### "How is completeness calculated?"

✅ **NOW EXPLAINED IN REPORT:**
- Section 1 shows calculation: `(Received Mandatory / Total Mandatory) × 100%`
- Alert box explains focus on mandatory vs. optional documents
- Section 4 details which documents are mandatory and missing

### "What happens when documents are missing?"

✅ **NOW EXPLAINED IN REPORT:**
- Section 4 includes "Automated System Actions" box
- Lists specific actions: email alerts, dashboard logging, reminders, submission blocking
- Section 6 action items show automated responses

### "Why not recommend to bid?"

✅ **NOW EXPLAINED IN REPORT:**
- Section 1 provides AI-generated summary
- Section 7 gives detailed reasoning with:
  - Overall assessment
  - Completeness calculation explanation
  - Mandatory vs. important criteria distinction
  - Impact of failed criteria
  - System helpfulness

### "Distinguish mandatory vs. negotiable criteria"

✅ **NOW IMPLEMENTED:**
- `CriteriaSeverity` enum: MANDATORY, IMPORTANT, OPTIONAL
- `CriteriaAnalyzer` class classifies each criterion
- Color-coded badges in HTML report
- Separate handling in recommendation logic:
  - MANDATORY failure = automatic disqualification
  - IMPORTANT failure = management decision required

## 🎨 Report Styling

The interactive HTML reports feature:
- Collapsible sections
- Color-coded status indicators
- Responsive design
- Print-friendly layout
- Professional styling matching mockup

## 🐛 Troubleshooting

### Database Connection Issues

```python
# Check database connection
import psycopg2
conn = psycopg2.connect(**DB_CONFIG)
print("✅ Database connected")
```

### Bitdeer API Issues

```python
# Test API connection
from report_generator import call_bitdeer_ai

result = call_bitdeer_ai("Test prompt", "You are helpful")
print(f"API Response: {result}")
```

### Missing Dependencies

```bash
pip install --break-system-packages requests psycopg2-binary openai
```

## 📈 Future Enhancements

1. **Email Integration**
   - Automatic email delivery via n8n or SMTP
   - Scheduled report generation

2. **Dashboard Integration**
   - Real-time report viewing in web interface
   - Batch report generation UI

3. **Multi-language Support**
   - Generate reports in multiple languages
   - Configurable language settings

4. **Advanced Analytics**
   - Tender win/loss tracking
   - Historical performance analysis
   - Predictive modeling

## 📞 Support

For issues or questions:
1. Check this README
2. Review error logs
3. Test with sample data: `python report_integration.py test`

## 📄 License

Copyright © 2024 GECO ASIA Upskill Today
