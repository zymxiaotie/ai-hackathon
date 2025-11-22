"""
Demo Script for Tender Report Generator
Demonstrates complete functionality with sample data
"""

from datetime import datetime, timedelta
from report_generator import (
    TenderSummary,
    QualificationCriterion,
    DocumentStatus,
    CriteriaType,
    CriteriaSeverity,
    TenderReportGenerator
)
from html_report_generator import generate_html_report
from pathlib import Path

def create_sample_tender_good() -> TenderSummary:
    """
    Create sample tender with GOOD compliance
    Should result in RECOMMEND
    """
    
    criteria = [
        QualificationCriterion(
            criteria_id=1,
            criteria_type=CriteriaType.LICENSE,
            description="BCA L6 License (General Building) required",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.95,
            evidence="Company holds BCA L6 valid until 31-Dec-2026",
            notes="Verified against BCA registry. License valid.",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=2,
            criteria_type=CriteriaType.CERTIFICATION,
            description="ISO 9001:2015 Quality Management Certification",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.98,
            evidence="Certificate valid until 15-Aug-2026",
            notes="Certificate on file. Annual audit passed.",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=3,
            criteria_type=CriteriaType.CERTIFICATION,
            description="bizSAFE Level 3 Safety Certification",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.96,
            evidence="Valid certification from WSH Council",
            notes="Risk assessment completed and approved",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=4,
            criteria_type=CriteriaType.EXPERIENCE,
            description="Minimum 3 completed projects over $2M in last 5 years",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=True,
            confidence_score=0.92,
            evidence="4 qualifying projects found",
            notes="Tampines HDB ($2.5M, 2023), Jurong West CC ($3.1M, 2024), Sengkang MRT ($4.2M, 2022), Woodlands School ($2.8M, 2021)",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=5,
            criteria_type=CriteriaType.FINANCIAL,
            description="Minimum annual turnover of $5M",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=True,
            confidence_score=0.94,
            evidence="FY2024: $7.2M, FY2023: $6.8M",
            notes="From audited financial statements",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=6,
            criteria_type=CriteriaType.FINANCIAL,
            description="Ability to provide 10% performance bond",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=True,
            confidence_score=0.90,
            evidence="Bank confirmed ability to issue bond",
            notes="Pre-approval obtained from OCBC Bank",
            source="original"
        )
    ]
    
    documents = [
        DocumentStatus("Invitation to Tender (ITT)", True, True, "Administrative"),
        DocumentStatus("Bill of Quantities (BOQ)", True, True, "Financial"),
        DocumentStatus("Technical Specifications", True, True, "Technical"),
        DocumentStatus("Method Statement", True, True, "Technical"),
        DocumentStatus("Safety Risk Assessment", True, True, "Safety"),
        DocumentStatus("Site Plan & Drawings", True, True, "Technical"),
        DocumentStatus("BCA License Copy", True, True, "Compliance"),
        DocumentStatus("ISO 9001 Certificate", True, True, "Compliance"),
        DocumentStatus("Company Profile", False, True, "Administrative"),
        DocumentStatus("Insurance Certificate", False, True, "Financial"),
        DocumentStatus("Past Project References", False, True, "Administrative")
    ]
    
    return TenderSummary(
        tender_id="DEMO-GOOD",
        reference_number="HDB/2025/BUILD/023",
        title="Construction of Community Centre at Punggol",
        issuing_authority="Housing & Development Board (HDB)",
        submission_deadline=datetime.now() + timedelta(days=14),
        clarification_deadline=datetime.now() + timedelta(days=7),
        project_name="Punggol East Community Centre",
        site_location="Punggol Way, Singapore 828761",
        contract_type="PSSCOC 2020 (Lump Sum)",
        liquidated_damages="$800 per day of delay",
        performance_bond="10% of contract sum",
        retention="5% (released 50% at completion, 50% after defects liability)",
        defects_liability_period="12 months from date of completion",
        criteria=criteria,
        documents=documents,
        addenda_count=0,
        last_addendum_date=None
    )

def create_sample_tender_poor() -> TenderSummary:
    """
    Create sample tender with POOR compliance
    Should result in NOT_RECOMMEND or DISQUALIFIED
    """
    
    criteria = [
        QualificationCriterion(
            criteria_id=1,
            criteria_type=CriteriaType.LICENSE,
            description="BCA L6 License (General Building) required",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.95,
            evidence="Company holds BCA L6",
            notes="License valid",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=2,
            criteria_type=CriteriaType.CERTIFICATION,
            description="ISO 9001:2015 Certification mandatory",
            severity=CriteriaSeverity.MANDATORY,
            is_met=False,
            confidence_score=0.98,
            evidence="Certificate expired 3 months ago",
            notes="Renewal process started but not completed. CRITICAL ISSUE.",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=3,
            criteria_type=CriteriaType.COMPLIANCE,
            description="Valid MOM work permits for all foreign workers",
            severity=CriteriaSeverity.MANDATORY,
            is_met=False,
            confidence_score=0.85,
            evidence="2 workers have expired permits",
            notes="Company has 5 foreign workers, 2 permits expired last month. Renewal pending. DISQUALIFYING ISSUE.",
            source="addendum_1"
        ),
        QualificationCriterion(
            criteria_id=4,
            criteria_type=CriteriaType.EXPERIENCE,
            description="Minimum 3 completed HDB projects in last 5 years",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=False,
            confidence_score=0.80,
            evidence="Only 1 HDB project found",
            notes="Company has completed Tampines HDB ($2.5M, 2023). Needs 2 more similar projects.",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=5,
            criteria_type=CriteriaType.FINANCIAL,
            description="Minimum annual turnover of $8M",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=False,
            confidence_score=0.92,
            evidence="FY2024: $6.2M",
            notes="Below threshold by $1.8M. Company growing but not yet at required level.",
            source="original"
        )
    ]
    
    documents = [
        DocumentStatus("Invitation to Tender (ITT)", True, True, "Administrative"),
        DocumentStatus("Bill of Quantities (BOQ)", True, True, "Financial"),
        DocumentStatus("Technical Specifications", True, True, "Technical"),
        DocumentStatus("Method Statement", True, False, "Technical", "Not yet prepared"),
        DocumentStatus("Safety Risk Assessment", True, False, "Safety", "WSH officer on leave"),
        DocumentStatus("Site Plan & Drawings", True, True, "Technical"),
        DocumentStatus("BCA License Copy", True, True, "Compliance"),
        DocumentStatus("ISO 9001 Certificate", True, False, "Compliance", "EXPIRED - renewal in progress"),
        DocumentStatus("MOM Work Permit Copies", True, False, "Compliance", "2 permits expired"),
        DocumentStatus("Company Profile", False, False, "Administrative"),
        DocumentStatus("Insurance Certificate", False, True, "Financial")
    ]
    
    return TenderSummary(
        tender_id="DEMO-POOR",
        reference_number="HDB/2025/REN/001",
        title="Major Renovation at Ang Mo Kio Block 123",
        issuing_authority="Housing & Development Board (HDB)",
        submission_deadline=datetime.now() + timedelta(days=7),
        clarification_deadline=datetime.now() - timedelta(days=2),
        project_name="AMK Block 123 Lift Upgrading & Facade Works",
        site_location="Ang Mo Kio Avenue 3, Singapore",
        contract_type="PSSCOC 2020 (Remeasurement)",
        liquidated_damages="$1,200 per day of delay",
        performance_bond="10% of contract sum",
        retention="5% (released after defects liability)",
        defects_liability_period="18 months from date of completion",
        criteria=criteria,
        documents=documents,
        addenda_count=1,
        last_addendum_date=datetime.now() - timedelta(days=11)
    )

def create_sample_tender_conditional() -> TenderSummary:
    """
    Create sample tender with MIXED compliance
    Should result in CONDITIONAL
    """
    
    criteria = [
        QualificationCriterion(
            criteria_id=1,
            criteria_type=CriteriaType.LICENSE,
            description="BCA L6 License required",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.95,
            evidence="Valid license",
            notes="License expires in 18 months",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=2,
            criteria_type=CriteriaType.CERTIFICATION,
            description="ISO 9001:2015 or equivalent quality certification",
            severity=CriteriaSeverity.MANDATORY,
            is_met=True,
            confidence_score=0.90,
            evidence="ISO 9001:2015 valid",
            notes="Annual surveillance audit due next month",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=3,
            criteria_type=CriteriaType.EXPERIENCE,
            description="Minimum 5 years in commercial construction",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=False,
            confidence_score=0.85,
            evidence="Company has 3.5 years experience",
            notes="Established 2021. Growing track record but below threshold.",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=4,
            criteria_type=CriteriaType.FINANCIAL,
            description="Minimum $3M paid-up capital",
            severity=CriteriaSeverity.IMPORTANT,
            is_met=False,
            confidence_score=0.88,
            evidence="Current paid-up: $2.2M",
            notes="Below threshold. Directors willing to inject capital if needed.",
            source="original"
        ),
        QualificationCriterion(
            criteria_id=5,
            criteria_type=CriteriaType.TECHNICAL,
            description="In-house structural engineering capability",
            severity=CriteriaSeverity.OPTIONAL,
            is_met=False,
            confidence_score=0.75,
            evidence="No in-house PE. Uses consultants.",
            notes="Can engage external consultant. Not critical requirement.",
            source="original"
        )
    ]
    
    documents = [
        DocumentStatus("ITT Document", True, True, "Administrative"),
        DocumentStatus("BOQ Template", True, True, "Financial"),
        DocumentStatus("Technical Specs", True, True, "Technical"),
        DocumentStatus("Method Statement", True, True, "Technical"),
        DocumentStatus("Safety Plan", True, False, "Safety", "Being prepared"),
        DocumentStatus("Drawings Set", True, True, "Technical"),
        DocumentStatus("License Copy", True, True, "Compliance"),
        DocumentStatus("ISO Certificate", True, True, "Compliance"),
        DocumentStatus("Financial Statements", False, True, "Financial"),
        DocumentStatus("Insurance Policy", False, False, "Financial")
    ]
    
    return TenderSummary(
        tender_id="DEMO-COND",
        reference_number="JTC/2025/IND/045",
        title="Factory Renovation at Jurong Industrial Estate",
        issuing_authority="JTC Corporation",
        submission_deadline=datetime.now() + timedelta(days=21),
        clarification_deadline=datetime.now() + timedelta(days=14),
        project_name="Block 45 Industrial Facility Upgrading",
        site_location="Jurong East Street 21, Singapore",
        contract_type="JTC Standard Form (Fixed Price)",
        liquidated_damages="$500 per day",
        performance_bond="5% of contract value",
        retention="3% (progressive release)",
        defects_liability_period="12 months",
        criteria=criteria,
        documents=documents,
        addenda_count=0,
        last_addendum_date=None
    )

def run_demo():
    """Run complete demonstration"""
    
    print("\n" + "="*80)
    print("TENDER INTELLIGENCE REPORT GENERATOR - DEMO")
    print("="*80 + "\n")
    
    # Create output directory
    output_dir = Path("/mnt/user-data/outputs/demo_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize generator
    generator = TenderReportGenerator()
    
    # Demo scenarios
    scenarios = [
        ("GOOD", create_sample_tender_good()),
        ("POOR", create_sample_tender_poor()),
        ("CONDITIONAL", create_sample_tender_conditional())
    ]
    
    for scenario_name, tender_summary in scenarios:
        print(f"\n{'='*80}")
        print(f"SCENARIO: {scenario_name} COMPLIANCE")
        print(f"Tender: {tender_summary.reference_number} - {tender_summary.title}")
        print(f"{'='*80}\n")
        
        print("📊 Analyzing tender...")
        print(f"   - {len(tender_summary.criteria)} qualification criteria")
        print(f"   - {len(tender_summary.documents)} required documents")
        print(f"   - {len([d for d in tender_summary.documents if d.is_mandatory])} mandatory documents")
        
        # Generate report
        report = generator.generate_report(tender_summary)
        
        # Display results
        print(f"\n✅ Analysis Complete:")
        print(f"   - Recommendation: {report['executive_summary']['recommendation'].upper()}")
        print(f"   - Score: {report['executive_summary']['score']:.0f}/100")
        print(f"   - Confidence: {report['executive_summary']['confidence']:.0%}")
        
        print(f"\n📈 Metrics:")
        print(f"   - Mandatory Criteria: {report['executive_summary']['key_metrics']['mandatory_criteria_met']}")
        print(f"   - Important Criteria: {report['executive_summary']['key_metrics']['important_criteria_met']}")
        print(f"   - Document Completeness: {report['executive_summary']['key_metrics']['document_completeness']}")
        
        if report['issues_and_risks']['disqualifying_issues']:
            print(f"\n❌ Disqualifying Issues:")
            for issue in report['issues_and_risks']['disqualifying_issues']:
                print(f"   {issue}")
        
        if report['issues_and_risks']['critical_issues']:
            print(f"\n⚠️ Critical Issues:")
            for issue in report['issues_and_risks']['critical_issues'][:3]:
                print(f"   {issue}")
        
        print(f"\n🎯 Action Items: {len(report['action_items'])}")
        for action in report['action_items'][:3]:
            print(f"   - [{action['priority']}] {action['action']}")
        
        # Generate HTML report
        filename = f"demo_report_{scenario_name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = output_dir / filename
        
        generate_html_report(report, str(output_path))
        
        print(f"\n📄 HTML Report Generated:")
        print(f"   {output_path}")
        print(f"   Open in browser: file://{output_path}")
        
        # Generate JSON
        import json
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"   JSON: {json_path}")
    
    print(f"\n{'='*80}")
    print("DEMO COMPLETE")
    print(f"{'='*80}\n")
    print(f"📁 All reports saved to: {output_dir}")
    print(f"\nKey Takeaways:")
    print(f"  • GOOD: All mandatory criteria met, high document completeness → RECOMMEND")
    print(f"  • POOR: Failed mandatory criteria (ISO9001, work permits) → DISQUALIFIED/NOT_RECOMMEND")
    print(f"  • CONDITIONAL: Mandatory met, some important criteria failed → CONDITIONAL (management decision)")
    print(f"\n  System distinguishes:")
    print(f"  • MANDATORY = Must have (legal/regulatory) → Failure = disqualification")
    print(f"  • IMPORTANT = Should have (competitive) → Failure = management decision")
    print(f"  • OPTIONAL = Nice to have → Failure = minor impact")

if __name__ == "__main__":
    run_demo()
