"""
Integration Module for Tender Intelligence Report Generation
Connects docparser.py with the report generator
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, List
import psycopg2
from pathlib import Path

# Import report generator components
from report_generator import (
    TenderSummary,
    QualificationCriterion,
    DocumentStatus,
    CriteriaType,
    CriteriaSeverity,
    TenderReportGenerator
)
from html_report_generator import generate_html_report

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "tender_intelligence"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

# Output directory for reports
REPORT_OUTPUT_DIR = Path(os.getenv("REPORT_OUTPUT_DIR", "/mnt/user-data/outputs/tender_reports"))
REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# DATABASE INTEGRATION
# ============================================================================

def fetch_tender_data_from_db(tender_id: str) -> Optional[TenderSummary]:
    """
    Fetch complete tender data from database and convert to TenderSummary
    """
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Fetch tender basic info
        cur.execute("""
            SELECT 
                tender_id,
                tender_reference_number,
                tender_title,
                issuing_authority,
                submission_deadline,
                clarification_closing_date,
                project_name,
                site_location,
                contract_type,
                liquidated_damages,
                performance_bond_percentage,
                retention_percentage,
                defects_liability_period
            FROM tenders
            WHERE tender_id = %s
        """, (tender_id,))
        
        tender_row = cur.fetchone()
        
        if not tender_row:
            print(f"Tender {tender_id} not found in database")
            return None
        
        # Fetch qualification criteria
        cur.execute("""
            SELECT 
                criteria_id,
                criteria_type,
                criteria_description,
                is_met,
                confidence_score,
                notes,
                source
            FROM tender_qualification_criteria
            WHERE tender_id = %s
            ORDER BY 
                CASE 
                    WHEN criteria_type = 'LICENSE' THEN 1
                    WHEN criteria_type = 'CERTIFICATION' THEN 2
                    WHEN criteria_type = 'COMPLIANCE' THEN 3
                    WHEN criteria_type = 'FINANCIAL' THEN 4
                    WHEN criteria_type = 'EXPERIENCE' THEN 5
                    ELSE 6
                END
        """, (tender_id,))
        
        criteria_rows = cur.fetchall()
        criteria_list = []
        
        for row in criteria_rows:
            try:
                criterion = QualificationCriterion(
                    criteria_id=row[0],
                    criteria_type=CriteriaType(row[1]) if row[1] in [c.value for c in CriteriaType] else CriteriaType.TECHNICAL,
                    description=row[2] or "",
                    severity=CriteriaSeverity.OPTIONAL,  # Will be determined by analyzer
                    is_met=row[3] if row[3] is not None else False,
                    confidence_score=float(row[4]) if row[4] is not None else 0.0,
                    evidence="",  # Not stored in DB
                    notes=row[5] or "",
                    source=row[6] or "original"
                )
                criteria_list.append(criterion)
            except Exception as e:
                print(f"Error processing criterion {row[0]}: {e}")
                continue
        
        # Fetch required documents
        cur.execute("""
            SELECT 
                document_name,
                is_mandatory,
                document_category
            FROM tender_required_documents
            WHERE tender_id = %s
        """, (tender_id,))
        
        required_docs_rows = cur.fetchall()
        
        # Fetch received documents
        cur.execute("""
            SELECT 
                document_name
            FROM tender_received_documents
            WHERE tender_id = %s
        """, (tender_id,))
        
        received_docs = {row[0] for row in cur.fetchall()}
        
        # Build document status list
        documents = []
        for row in required_docs_rows:
            doc_name = row[0]
            is_mandatory = row[1] if row[1] is not None else True
            category = row[2] or "General"
            
            doc_status = DocumentStatus(
                doc_name=doc_name,
                is_mandatory=is_mandatory,
                is_received=doc_name in received_docs,
                category=category,
                notes=""
            )
            documents.append(doc_status)
        
        # Check for addenda
        cur.execute("""
            SELECT COUNT(*), MAX(received_date)
            FROM tender_addenda
            WHERE tender_id = %s
        """, (tender_id,))
        
        addenda_row = cur.fetchone()
        addenda_count = addenda_row[0] if addenda_row else 0
        last_addendum = addenda_row[1] if addenda_row and addenda_row[1] else None
        
        # Build TenderSummary
        summary = TenderSummary(
            tender_id=str(tender_row[0]),
            reference_number=tender_row[1],
            title=tender_row[2] or "No title",
            issuing_authority=tender_row[3] or "Unknown",
            submission_deadline=tender_row[4],
            clarification_deadline=tender_row[5],
            project_name=tender_row[6] or "",
            site_location=tender_row[7] or "",
            contract_type=tender_row[8] or "",
            liquidated_damages=tender_row[9] or "Not specified",
            performance_bond=f"{tender_row[10]}%" if tender_row[10] else "Not specified",
            retention=f"{tender_row[11]}%" if tender_row[11] else "Not specified",
            defects_liability_period=tender_row[12] or "Not specified",
            criteria=criteria_list,
            documents=documents,
            addenda_count=addenda_count,
            last_addendum_date=last_addendum
        )
        
        cur.close()
        conn.close()
        
        return summary
    
    except Exception as e:
        print(f"Error fetching tender data: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================================
# REPORT GENERATION PIPELINE
# ============================================================================

def generate_tender_report(tender_id: str, output_format: str = "html") -> Optional[str]:
    """
    Main function to generate complete tender report
    
    Args:
        tender_id: Database tender ID
        output_format: 'html', 'json', or 'both'
    
    Returns:
        Path to generated report file(s)
    """
    
    print(f"\n{'='*80}")
    print(f"GENERATING TENDER REPORT FOR: {tender_id}")
    print(f"{'='*80}\n")
    
    # Step 1: Fetch tender data
    print("Step 1: Fetching tender data from database...")
    summary = fetch_tender_data_from_db(tender_id)
    
    if not summary:
        print("❌ Failed to fetch tender data")
        return None
    
    print(f"✅ Loaded tender: {summary.reference_number}")
    print(f"   - {len(summary.criteria)} qualification criteria")
    print(f"   - {len(summary.documents)} required documents")
    
    # Step 2: Generate report analysis
    print("\nStep 2: Analyzing tender and generating recommendations...")
    generator = TenderReportGenerator()
    
    report = generator.generate_report(summary)
    
    print(f"✅ Analysis complete")
    print(f"   - Recommendation: {report['executive_summary']['recommendation'].upper()}")
    print(f"   - Score: {report['executive_summary']['score']}/100")
    print(f"   - Disqualifying issues: {len(report['issues_and_risks']['disqualifying_issues'])}")
    print(f"   - Critical issues: {len(report['issues_and_risks']['critical_issues'])}")
    print(f"   - Action items: {len(report['action_items'])}")
    
    # Step 3: Generate output files
    print("\nStep 3: Generating report files...")
    
    output_files = []
    base_filename = f"tender_report_{summary.reference_number.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Generate HTML report
    if output_format in ['html', 'both']:
        html_path = REPORT_OUTPUT_DIR / f"{base_filename}.html"
        generate_html_report(report, str(html_path))
        print(f"✅ HTML report: {html_path}")
        output_files.append(str(html_path))
    
    # Generate JSON report
    if output_format in ['json', 'both']:
        import json
        json_path = REPORT_OUTPUT_DIR / f"{base_filename}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"✅ JSON report: {json_path}")
        output_files.append(str(json_path))
    
    print(f"\n{'='*80}")
    print("REPORT GENERATION COMPLETE")
    print(f"{'='*80}\n")
    
    return output_files[0] if output_files else None

def generate_reports_for_all_tenders(output_format: str = "html"):
    """
    Generate reports for all tenders in database
    """
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT tender_id, tender_reference_number
            FROM tenders
            ORDER BY submission_deadline DESC
        """)
        
        tenders = cur.fetchall()
        
        cur.close()
        conn.close()
        
        print(f"\n{'='*80}")
        print(f"GENERATING REPORTS FOR {len(tenders)} TENDERS")
        print(f"{'='*80}\n")
        
        for tender_id, ref_number in tenders:
            print(f"\nProcessing: {ref_number}")
            try:
                generate_tender_report(str(tender_id), output_format)
            except Exception as e:
                print(f"❌ Error generating report for {ref_number}: {e}")
                continue
        
        print(f"\n{'='*80}")
        print(f"BATCH REPORT GENERATION COMPLETE")
        print(f"{'='*80}\n")
    
    except Exception as e:
        print(f"Error in batch generation: {e}")

# ============================================================================
# EMAIL INTEGRATION (PLACEHOLDER)
# ============================================================================

def send_report_via_email(report_path: str, recipient_emails: List[str]):
    """
    Send generated report via email
    
    This is a placeholder for email integration with n8n or SMTP
    """
    
    print(f"\n📧 EMAIL DELIVERY (Placeholder)")
    print(f"   Report: {report_path}")
    print(f"   Recipients: {', '.join(recipient_emails)}")
    print(f"   Implementation: Connect to n8n webhook or SMTP server")
    
    # In production, this would:
    # 1. Call n8n webhook with report path
    # 2. n8n sends email with attached report
    # 3. Or directly use SMTP to send email
    
    return True

# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """CLI interface for report generation"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Tender Intelligence Report Generator")
    parser.add_argument("command", choices=["single", "batch", "test"],
                       help="Command to execute")
    parser.add_argument("--tender-id", type=str,
                       help="Tender ID for single report generation")
    parser.add_argument("--format", choices=["html", "json", "both"],
                       default="html",
                       help="Output format")
    
    args = parser.parse_args()
    
    if args.command == "single":
        if not args.tender_id:
            print("Error: --tender-id required for single report generation")
            return
        
        generate_tender_report(args.tender_id, args.format)
    
    elif args.command == "batch":
        generate_reports_for_all_tenders(args.format)
    
    elif args.command == "test":
        # Test with sample data
        print("Running test with sample data...")
        test_report_generation()

def test_report_generation():
    """Test report generation with sample data"""
    
    from datetime import timedelta
    
    # Create sample tender data
    sample_criteria = [
        QualificationCriterion(
            criteria_id=1,
            criteria_type=CriteriaType.LICENSE,
            description="BCA L6 License (General Building)",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.95,
            evidence="Company holds BCA L6 valid until 31-Dec-2026",
            notes="Verified in company records",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=2,
            criteria_type=CriteriaType.CERTIFICATION,
            description="ISO 9001:2015 Certification",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.98,
            evidence="Valid until 15-Aug-2026",
            notes="Certificate on file",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=3,
            criteria_type=CriteriaType.EXPERIENCE,
            description="Minimum 3 completed projects >$2M in last 5 years",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=False,
            confidence_score=0.85,
            evidence="Only 2 qualifying projects found",
            notes="Tampines HDB ($2.5M, 2023), Jurong West CC ($3.1M, 2024)",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=4,
            criteria_type=CriteriaType.FINANCIAL,
            description="Minimum annual turnover of $5M",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=True,
            confidence_score=0.92,
            evidence="FY2024: $7.2M",
            notes="From audited financials",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=5,
            criteria_type=CriteriaType.COMPLIANCE,
            description="Valid MOM work permits for all foreign workers",
            severity=CriteriaSeverity.MANDATORY,
            is_met=False,
            confidence_score=0.70,
            evidence="Need to verify work permits",
            notes="Company has 3 foreign workers - verification pending",
            source="addendum_1"
        )
    ]
    
    sample_documents = [
        DocumentStatus("BOQ Template v2.0", True, True, "Financial"),
        DocumentStatus("Method Statement", True, True, "Technical"),
        DocumentStatus("Technical Specifications", True, True, "Technical"),
        DocumentStatus("Safety Risk Assessment", True, False, "Safety"),
        DocumentStatus("Site Plan", True, False, "Technical"),
        DocumentStatus("Company Profile", False, True, "Administrative"),
        DocumentStatus("Insurance Certificate", False, False, "Financial")
    ]
    
    sample_summary = TenderSummary(
        tender_id="TEST-001",
        reference_number="HDB/2025/REN/001",
        title="HDB Renovation at Ang Mo Kio Block 123",
        issuing_authority="Housing & Development Board",
        submission_deadline=datetime.now() + timedelta(days=7),
        clarification_deadline=datetime.now() - timedelta(days=3),
        project_name="AMK Block 123 Upgrading Works",
        site_location="Ang Mo Kio Avenue 3, Singapore",
        contract_type="PSSCOC (Public Sector Standard Conditions of Contract)",
        liquidated_damages="$1,000 per day of delay",
        performance_bond="10% of contract value",
        retention="5% (released upon completion)",
        defects_liability_period="12 months from completion",
        criteria=sample_criteria,
        documents=sample_documents,
        addenda_count=1,
        last_addendum_date=datetime.now() - timedelta(days=11)
    )
    
    # Generate report
    generator = TenderReportGenerator()
    report = generator.generate_report(sample_summary)
    
    # Generate HTML
    output_path = REPORT_OUTPUT_DIR / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    generate_html_report(report, str(output_path))
    
    print(f"\n✅ Test report generated: {output_path}")
    print(f"\nOpen in browser: file://{output_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        # Default: run test
        print("No arguments provided, running test...")
        test_report_generation()
