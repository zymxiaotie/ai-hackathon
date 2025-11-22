"""
HTML Report Template Generator
Generates interactive HTML reports based on interactive_report_mockup.html
"""

from datetime import datetime
from typing import Dict, List
import json

def generate_html_report(report: Dict, output_path: str = None) -> str:
    """
    Generate interactive HTML report from report data
    """
    
    exec_summary = report['executive_summary']
    tender = report['tender_overview']
    qual_analysis = report['qualification_analysis']
    doc_status = report['document_status']
    issues = report['issues_and_risks']
    actions = report['action_items']
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tender Report - {tender['reference_number']}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .email-header {{
            background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
            color: white;
            padding: 30px;
        }}
        .email-header h1 {{
            font-size: 24px;
            margin-bottom: 8px;
        }}
        .email-meta {{
            font-size: 13px;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
            transition: all 0.3s ease;
        }}
        .section:hover {{
            border-color: #2563eb;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
        }}
        .section-header {{
            background: linear-gradient(to right, #f9fafb 0%, #f3f4f6 100%);
            padding: 18px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            user-select: none;
            border-bottom: 2px solid #e5e7eb;
        }}
        .section-header:hover {{
            background: linear-gradient(to right, #eff6ff 0%, #dbeafe 100%);
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 700;
            color: #1e40af;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-icon {{
            font-size: 20px;
        }}
        .toggle-icon {{
            font-size: 20px;
            color: #6b7280;
            transition: transform 0.3s ease;
        }}
        .section.collapsed .toggle-icon {{
            transform: rotate(-90deg);
        }}
        .section-content {{
            padding: 25px;
            max-height: 2000px;
            overflow: hidden;
            transition: max-height 0.4s ease, padding 0.4s ease;
        }}
        .section.collapsed .section-content {{
            max-height: 0;
            padding: 0 25px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #2563eb;
            text-align: center;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            color: #1e40af;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6b7280;
            margin-top: 8px;
        }}
        .recommendation-box {{
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
            font-size: 18px;
            font-weight: 700;
        }}
        .rec-disqualified {{
            background: #fecaca;
            border: 3px solid #dc2626;
            color: #7f1d1d;
        }}
        .rec-not-recommend {{
            background: #fee2e2;
            border: 2px solid #ef4444;
            color: #991b1b;
        }}
        .rec-conditional {{
            background: #fef3c7;
            border: 2px solid #f59e0b;
            color: #92400e;
        }}
        .rec-recommend {{
            background: #d1fae5;
            border: 2px solid #10b981;
            color: #065f46;
        }}
        .rec-strongly-recommend {{
            background: #bbf7d0;
            border: 3px solid #059669;
            color: #064e3b;
        }}
        .info-table {{
            width: 100%;
            margin: 15px 0;
        }}
        .info-table td {{
            padding: 10px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .info-table td:first-child {{
            font-weight: 600;
            color: #4b5563;
            width: 200px;
        }}
        .deadline-urgent {{
            color: #dc2626;
            font-weight: 700;
            font-size: 16px;
        }}
        table.data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        table.data-table th {{
            background: #2563eb;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        table.data-table td {{
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }}
        table.data-table tr:hover {{
            background: #f9fafb;
        }}
        .status-badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
            display: inline-block;
        }}
        .status-met {{ background: #d1fae5; color: #065f46; }}
        .status-not-met {{ background: #fee2e2; color: #991b1b; }}
        .status-pending {{ background: #fef3c7; color: #92400e; }}
        .status-received {{ background: #d1fae5; color: #065f46; }}
        .status-missing {{ background: #fee2e2; color: #991b1b; }}
        .severity-mandatory {{ 
            background: #fecaca; 
            color: #7f1d1d;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
        }}
        .severity-important {{ 
            background: #fed7aa; 
            color: #7c2d12;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
        }}
        .severity-optional {{ 
            background: #e0e7ff; 
            color: #3730a3;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
        }}
        .badge-addendum {{
            background: #fef3c7;
            color: #92400e;
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 12px;
        }}
        .alert {{
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid;
        }}
        .alert-warning {{
            background: #fef3c7;
            border-color: #f59e0b;
            color: #92400e;
        }}
        .alert-danger {{
            background: #fee2e2;
            border-color: #ef4444;
            color: #991b1b;
        }}
        .alert-success {{
            background: #d1fae5;
            border-color: #10b981;
            color: #065f46;
        }}
        .alert-info {{
            background: #dbeafe;
            border-color: #3b82f6;
            color: #1e40af;
        }}
        .action-item {{
            background: #f9fafb;
            padding: 15px;
            margin: 10px 0;
            border-radius: 6px;
            border-left: 4px solid;
        }}
        .priority-urgent {{ border-left-color: #dc2626; background: #fef2f2; }}
        .priority-critical {{ border-left-color: #ef4444; background: #fef2f2; }}
        .priority-high {{ border-left-color: #f59e0b; background: #fefce8; }}
        .priority-medium {{ border-left-color: #3b82f6; background: #eff6ff; }}
        .priority-low {{ border-left-color: #6b7280; }}
        .addendum-box {{
            background: #fef9e7;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #f59e0b;
        }}
        .controls {{
            background: #f3f4f6;
            padding: 15px 30px;
            display: flex;
            gap: 10px;
            border-top: 2px solid #e5e7eb;
        }}
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-primary {{
            background: #2563eb;
            color: white;
        }}
        .btn-primary:hover {{
            background: #1e40af;
        }}
        .btn-secondary {{
            background: white;
            color: #374151;
            border: 2px solid #d1d5db;
        }}
        .btn-secondary:hover {{
            background: #f9fafb;
        }}
        .reasoning-text {{
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
            margin: 15px 0;
            line-height: 1.8;
        }}
        .reasoning-text p {{
            margin-bottom: 12px;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .container {{ box-shadow: none; }}
            .controls {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Email Header -->
        <div class="email-header">
            <h1>📧 Tender Alert: {tender['reference_number']} - {tender.get('title', 'Overview Report')}</h1>
            <div class="email-meta">
                <div>From: Tender Intelligence Assistant &lt;ai-tender@company.com&gt;</div>
                <div>To: qs@company.com, management@company.com</div>
                <div>Date: {datetime.now().strftime('%d %b %Y, %I:%M %p')}</div>
            </div>
        </div>

        <!-- Content -->
        <div class="content">
            {_generate_section_1_executive_summary(exec_summary, qual_analysis, doc_status)}
            {_generate_section_2_tender_overview(tender)}
            {_generate_section_3_eligibility(qual_analysis, issues)}
            {_generate_section_4_documents(doc_status)}
            {_generate_section_5_addenda(tender)}
            {_generate_section_6_actions(actions, tender)}
            {_generate_section_7_reasoning(report['detailed_reasoning'])}
        </div>

        <!-- Controls -->
        <div class="controls">
            <button class="btn btn-primary" onclick="expandAll()">▼ Expand All Sections</button>
            <button class="btn btn-secondary" onclick="collapseAll()">▲ Collapse All Sections</button>
            <button class="btn btn-secondary" onclick="window.print()">🖨️ Print Report</button>
        </div>
    </div>

    <script>
        // Toggle individual section
        document.querySelectorAll('.section-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('collapsed');
            }});
        }});

        // Expand all sections
        function expandAll() {{
            document.querySelectorAll('.section').forEach(section => {{
                section.classList.remove('collapsed');
            }});
        }}

        // Collapse all sections
        function collapseAll() {{
            document.querySelectorAll('.section').forEach(section => {{
                section.classList.add('collapsed');
            }});
        }}
    </script>
</body>
</html>"""

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Report generated: {output_path}")
    
    return html

def _generate_section_1_executive_summary(exec_summary: Dict, qual_analysis: Dict, doc_status: Dict) -> str:
    """Generate Section 1: Executive Summary"""
    
    recommendation = exec_summary['recommendation']
    score = exec_summary['score']
    metrics = exec_summary['key_metrics']
    
    # Map recommendation to CSS class
    rec_class = f"rec-{recommendation.replace('_', '-')}"
    
    # Recommendation icon and text
    rec_icons = {
        'disqualified': '❌ DISQUALIFIED',
        'not_recommend': '❌ NOT RECOMMENDED TO BID',
        'conditional': '⚠️ CONDITIONAL - REVIEW REQUIRED',
        'recommend': '✅ RECOMMENDED TO BID',
        'strongly_recommend': '✅ STRONGLY RECOMMENDED'
    }
    rec_text = rec_icons.get(recommendation, recommendation.upper())
    
    # Calculate stats
    criteria_met = len([c for c in qual_analysis['criteria_details'] if c['is_met']])
    criteria_total = len(qual_analysis['criteria_details'])
    
    docs_received = len([d for d in doc_status['all_documents'] if d['is_received']])
    docs_total = len(doc_status['all_documents'])
    
    return f"""
            <!-- Section 1: Executive Summary -->
            <div class="section" data-section="1">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">📊</span>
                        SECTION 1: Executive Summary
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">{criteria_met}/{criteria_total}</div>
                            <div class="stat-label">Requirements Met</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">{docs_received}/{docs_total}</div>
                            <div class="stat-label">Documents Received</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">{metrics['days_until_deadline']}</div>
                            <div class="stat-label">Days Until Deadline</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">{score:.0f}/100</div>
                            <div class="stat-label">Bid Readiness Score</div>
                        </div>
                    </div>
                    <div class="recommendation-box {rec_class}">
                        {rec_text}
                    </div>
                    <div class="alert alert-info">
                        <strong>How We Calculate This:</strong><br>
                        • <strong>Completeness</strong>: {metrics['document_completeness']} of mandatory documents received<br>
                        • <strong>Mandatory Criteria</strong>: {metrics['mandatory_criteria_met']} of critical requirements met (license, certifications, compliance)<br>
                        • <strong>Important Criteria</strong>: {metrics['important_criteria_met']} of competitive requirements met (experience, financials)<br>
                        • <strong>Score</strong>: Weighted calculation where mandatory criteria are pass/fail, important criteria affect competitiveness
                    </div>
                    <p style="color: #6b7280; margin-top: 15px;">
                        {exec_summary['summary']}
                    </p>
                </div>
            </div>
    """

def _generate_section_2_tender_overview(tender: Dict) -> str:
    """Generate Section 2: Tender Overview"""
    
    submission_date = tender.get('submission_deadline', 'Not specified')
    if submission_date != 'Not specified':
        try:
            dt = datetime.fromisoformat(submission_date.replace('Z', '+00:00'))
            submission_date = dt.strftime('%d %b %Y, %I:%M %p')
        except:
            pass
    
    clarification_date = tender.get('clarification_deadline', 'Not specified')
    if clarification_date != 'Not specified':
        try:
            dt = datetime.fromisoformat(clarification_date.replace('Z', '+00:00'))
            clarification_date = dt.strftime('%d %b %Y, %I:%M %p')
        except:
            pass
    
    return f"""
            <!-- Section 2: Tender Overview -->
            <div class="section" data-section="2">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">📋</span>
                        SECTION 2: Tender Overview (Key Data Sheet)
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    <h3 style="color: #1e40af; margin-bottom: 10px;">Basic Information</h3>
                    <table class="info-table">
                        <tr>
                            <td>Tender Title</td>
                            <td>{tender.get('title', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Reference Number</td>
                            <td><strong>{tender['reference_number']}</strong></td>
                        </tr>
                        <tr>
                            <td>Issuing Authority</td>
                            <td>{tender.get('issuing_authority', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Submission Deadline</td>
                            <td class="deadline-urgent">{submission_date}</td>
                        </tr>
                        <tr>
                            <td>Clarification Closing</td>
                            <td>{clarification_date}</td>
                        </tr>
                    </table>

                    <h3 style="color: #1e40af; margin: 20px 0 10px;">Project Details</h3>
                    <table class="info-table">
                        <tr>
                            <td>Project Name</td>
                            <td>{tender.get('project_name', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Site Location</td>
                            <td>{tender.get('site_location', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Contract Type</td>
                            <td>{tender.get('contract_type', 'N/A')}</td>
                        </tr>
                    </table>

                    <h3 style="color: #1e40af; margin: 20px 0 10px;">Contract Terms</h3>
                    <table class="info-table">
                        <tr>
                            <td>Liquidated Damages</td>
                            <td>{tender.get('liquidated_damages', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Performance Bond</td>
                            <td>{tender.get('performance_bond', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Retention</td>
                            <td>{tender.get('retention', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Defects Liability Period</td>
                            <td>{tender.get('defects_liability_period', 'N/A')}</td>
                        </tr>
                    </table>
                </div>
            </div>
    """

def _generate_section_3_eligibility(qual_analysis: Dict, issues: Dict) -> str:
    """Generate Section 3: Eligibility Status"""
    
    mandatory_failed = qual_analysis['failed_mandatory']
    important_failed = qual_analysis['failed_important']
    
    # Determine alert type
    if mandatory_failed:
        alert_class = "alert-danger"
        alert_text = f"❌ DISQUALIFYING: Company does not meet {len(mandatory_failed)} mandatory requirement(s). Bidding will result in automatic rejection."
    elif important_failed:
        alert_class = "alert-warning"
        alert_text = f"⚠️ WARNING: Company does not meet {len(important_failed)} important requirement(s). This significantly reduces competitiveness."
    else:
        alert_class = "alert-success"
        alert_text = "✅ SUCCESS: Company meets all mandatory requirements and is eligible to bid."
    
    # Build criteria table
    criteria_rows = ""
    for criterion in qual_analysis['criteria_details']:
        severity = criterion.get('severity', 'optional')
        severity_badge = f'<span class="severity-{severity}">{severity.upper()}</span>'
        
        is_met = criterion.get('is_met', False)
        status_class = "status-met" if is_met else "status-not-met"
        status_text = "✓ MET" if is_met else "✗ NOT MET"
        
        row_class = ""
        if not is_met and severity == 'mandatory':
            row_class = ' style="background: #fef2f2;"'
        elif not is_met and severity == 'important':
            row_class = ' style="background: #fefce8;"'
        
        criteria_rows += f"""
                            <tr{row_class}>
                                <td>{criterion['criteria_type']}</td>
                                <td>{criterion['description']}</td>
                                <td>{severity_badge}</td>
                                <td><span class="status-badge {status_class}">{status_text}</span></td>
                                <td>{criterion.get('notes', 'N/A')}</td>
                                <td>{criterion.get('source', 'Original')}</td>
                            </tr>
        """
    
    return f"""
            <!-- Section 3: Eligibility Status -->
            <div class="section" data-section="3">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">✅</span>
                        SECTION 3: Eligibility Status (Risks & Readiness)
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    <div class="alert {alert_class}">
                        <strong>{alert_text}</strong>
                    </div>
                    
                    <div class="alert alert-info">
                        <strong>Understanding Criteria Severity:</strong><br>
                        • <span class="severity-mandatory">MANDATORY</span>: Legal/regulatory requirements. Failing = automatic disqualification (e.g., BCA license, ISO9001)<br>
                        • <span class="severity-important">IMPORTANT</span>: Competitive requirements. Can be negotiated or decided by management (e.g., performance bond, experience)<br>
                        • <span class="severity-optional">OPTIONAL</span>: Preferred but not critical. Improves competitiveness if met
                    </div>

                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Type</th>
                                <th>Requirement</th>
                                <th>Severity</th>
                                <th>Status</th>
                                <th>Notes</th>
                                <th>Source</th>
                            </tr>
                        </thead>
                        <tbody>
                            {criteria_rows}
                        </tbody>
                    </table>
                </div>
            </div>
    """

def _generate_section_4_documents(doc_status: Dict) -> str:
    """Generate Section 4: Document Register"""
    
    missing_mandatory = doc_status['missing_mandatory']
    missing_optional = doc_status['missing_optional']
    
    if missing_mandatory:
        alert_class = "alert-danger"
        alert_text = f"❌ CRITICAL: {len(missing_mandatory)} mandatory document(s) not received. Submission will be rejected without these."
    elif missing_optional:
        alert_class = "alert-warning"
        alert_text = f"⚠️ {len(missing_optional)} optional document(s) missing. May affect competitiveness."
    else:
        alert_class = "alert-success"
        alert_text = "✅ All mandatory documents received. Submission package complete."
    
    # Build document table
    doc_rows = ""
    for doc in doc_status['all_documents']:
        is_received = doc['is_received']
        is_mandatory = doc['is_mandatory']
        
        status_class = "status-received" if is_received else "status-missing"
        status_text = "✓ Received" if is_received else "✗ Missing"
        
        mandatory_text = "Yes" if is_mandatory else "No"
        
        row_class = ""
        if not is_received and is_mandatory:
            row_class = ' style="background: #fef2f2;"'
        elif not is_received:
            row_class = ' style="background: #fefce8;"'
        
        doc_rows += f"""
                            <tr{row_class}>
                                <td>{doc['doc_name']}</td>
                                <td>{doc.get('category', 'General')}</td>
                                <td>{mandatory_text}</td>
                                <td><span class="status-badge {status_class}">{status_text}</span></td>
                                <td>{doc.get('notes', '-')}</td>
                            </tr>
        """
    
    # System action explanation
    action_text = ""
    if missing_mandatory:
        action_text = """
                    <div class="alert alert-info">
                        <strong>Automated System Actions for Missing Documents:</strong><br>
                        • Email alerts sent to Document Coordinator and QS Team<br>
                        • Missing documents logged in tracking dashboard with HIGH priority<br>
                        • Daily reminders scheduled until documents received<br>
                        • Tender status flagged as "INCOMPLETE" in management reports<br>
                        • Submission workflow blocked until mandatory documents uploaded
                    </div>
        """
    
    return f"""
            <!-- Section 4: Document Register -->
            <div class="section" data-section="4">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">📁</span>
                        SECTION 4: Document Register & Completeness Check
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    <div class="alert {alert_class}">
                        <strong>{alert_text}</strong>
                    </div>
                    
                    {action_text}

                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Document Name</th>
                                <th>Category</th>
                                <th>Mandatory</th>
                                <th>Status</th>
                                <th>Notes</th>
                            </tr>
                        </thead>
                        <tbody>
                            {doc_rows}
                        </tbody>
                    </table>
                </div>
            </div>
    """

def _generate_section_5_addenda(tender: Dict) -> str:
    """Generate Section 5: Addenda Tracker"""
    
    addenda_count = tender.get('addenda_count', 0)
    
    if addenda_count == 0:
        content = """
                    <div class="alert alert-success">
                        ✅ No addenda issued for this tender. Original tender documents remain current.
                    </div>
        """
    else:
        content = f"""
                    <div class="alert alert-warning">
                        ⚠️ IMPORTANT: This tender has {addenda_count} addendum/addenda. Review all changes carefully.
                    </div>
                    
                    <div class="addendum-box">
                        <h3 style="margin-top: 0;">Addendum Information</h3>
                        <p><strong>Note:</strong> Addendum tracking and impact analysis will be displayed here when addenda are processed by the system.</p>
                        <p>System automatically monitors tender emails for addenda and processes changes to criteria, documents, and deadlines.</p>
                    </div>
        """
    
    return f"""
            <!-- Section 5: Addenda Tracker -->
            <div class="section" data-section="5">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">📝</span>
                        SECTION 5: Addenda Impact Tracker
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    {content}
                </div>
            </div>
    """

def _generate_section_6_actions(actions: List[Dict], tender: Dict) -> str:
    """Generate Section 6: Next Actions"""
    
    if not actions:
        return """
            <!-- Section 6: Next Actions -->
            <div class="section" data-section="6">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">🎯</span>
                        SECTION 6: Next Actions & Outstanding Items
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    <div class="alert alert-success">
                        ✅ No outstanding actions. Tender is ready for final review and submission.
                    </div>
                </div>
            </div>
        """
    
    action_items_html = ""
    for action in actions:
        priority = action['priority'].lower()
        priority_class = f"priority-{priority}"
        
        emoji = {
            'urgent': '🔴',
            'critical': '❌',
            'high': '⚠️',
            'medium': '📋',
            'low': 'ℹ️'
        }.get(priority, '📋')
        
        action_items_html += f"""
                    <div class="action-item {priority_class}">
                        <strong style="font-size: 14px;">{emoji} {priority.upper()}: {action['action']}</strong>
                        <p style="margin: 5px 0; color: #6b7280; font-size: 13px;">
                            <strong>Category:</strong> {action['category']} | 
                            <strong>Owner:</strong> {action['owner']}<br>
                            <strong>Impact:</strong> {action['impact']}
                        </p>
                        <p style="margin: 5px 0; padding: 8px; background: #eff6ff; border-radius: 4px; font-size: 12px;">
                            <strong>🤖 System Action:</strong> {action['automated_action']}
                        </p>
                    </div>
        """
    
    return f"""
            <!-- Section 6: Next Actions -->
            <div class="section" data-section="6">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">🎯</span>
                        SECTION 6: Next Actions & Outstanding Items
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    <p style="margin-bottom: 15px; font-weight: 600; color: #374151;">
                        Complete these actions before submitting your bid:
                    </p>
                    
                    {action_items_html}
                    
                    <div class="alert alert-info" style="margin-top: 20px;">
                        <strong>How the System Helps:</strong><br>
                        • Automated email alerts sent to responsible teams<br>
                        • Daily progress tracking and status updates<br>
                        • Document upload notifications<br>
                        • Deadline reminders at 7 days, 3 days, and 1 day before submission<br>
                        • Management dashboard shows real-time tender readiness across all tenders
                    </div>
                </div>
            </div>
    """

def _generate_section_7_reasoning(reasoning: str) -> str:
    """Generate Section 7: Detailed Reasoning"""
    
    # Format reasoning text with paragraphs
    paragraphs = reasoning.split('\n\n')
    formatted_reasoning = ""
    for para in paragraphs:
        if para.strip():
            formatted_reasoning += f"<p>{para.strip()}</p>"
    
    return f"""
            <!-- Section 7: Detailed Reasoning -->
            <div class="section" data-section="7">
                <div class="section-header">
                    <div class="section-title">
                        <span class="section-icon">📄</span>
                        SECTION 7: Detailed Analysis & Reasoning
                    </div>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="section-content">
                    <div class="reasoning-text">
                        {formatted_reasoning}
                    </div>
                </div>
            </div>
    """

if __name__ == "__main__":
    print("HTML Report Generator loaded successfully")
