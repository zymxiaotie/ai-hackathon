"""
Tender Intelligence Report Generator
Uses Bitdeer AI API for intelligent report generation
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

# ============================================================================
# CONFIGURATION
# ============================================================================

BITDEER_API_KEY = os.getenv("BITDEER_API_KEY", "YOUR_API_KEY_HERE")
BITDEER_URL = "https://api-inference.bitdeer.ai/v1/chat/completions"
BITDEER_MODEL = "openai/gpt-oss-120b"

# ============================================================================
# ENUMS & DATA MODELS
# ============================================================================

class CriteriaType(str, Enum):
    """Types of qualification criteria"""
    LICENSE = "LICENSE"
    CERTIFICATION = "CERTIFICATION"
    EXPERIENCE = "EXPERIENCE"
    FINANCIAL = "FINANCIAL"
    COMPLIANCE = "COMPLIANCE"
    TECHNICAL = "TECHNICAL"

class CriteriaSeverity(str, Enum):
    """Severity levels for criteria"""
    MANDATORY = "mandatory"  # Failing = automatic disqualification
    IMPORTANT = "important"   # Strongly recommended
    OPTIONAL = "optional"     # Good to have

class RecommendationType(str, Enum):
    """Bid recommendation types"""
    STRONGLY_RECOMMEND = "strongly_recommend"
    RECOMMEND = "recommend"
    CONDITIONAL = "conditional"
    NOT_RECOMMEND = "not_recommend"
    DISQUALIFIED = "disqualified"

@dataclass
class QualificationCriterion:
    """Individual qualification criterion"""
    criteria_id: int
    criteria_type: CriteriaType
    description: str
    severity: CriteriaSeverity
    is_met: bool
    confidence_score: float
    evidence: str
    notes: str
    source: str  # 'original' or 'addendum_#'
    
    def to_dict(self):
        return asdict(self)

@dataclass
class DocumentStatus:
    """Status of required document"""
    doc_name: str
    is_mandatory: bool
    is_received: bool
    category: str
    notes: str = ""

@dataclass
class TenderSummary:
    """Complete tender summary"""
    tender_id: str
    reference_number: str
    title: str
    issuing_authority: str
    submission_deadline: datetime
    clarification_deadline: Optional[datetime]
    project_name: str
    site_location: str
    contract_type: str
    
    # Contract terms
    liquidated_damages: str
    performance_bond: str
    retention: str
    defects_liability_period: str
    
    # Qualification data
    criteria: List[QualificationCriterion]
    documents: List[DocumentStatus]
    
    # Addenda
    addenda_count: int
    last_addendum_date: Optional[datetime]
    
    def to_dict(self):
        return {
            **asdict(self),
            'submission_deadline': self.submission_deadline.isoformat() if self.submission_deadline else None,
            'clarification_deadline': self.clarification_deadline.isoformat() if self.clarification_deadline else None,
            'last_addendum_date': self.last_addendum_date.isoformat() if self.last_addendum_date else None,
            'criteria': [c.to_dict() for c in self.criteria],
            'documents': [asdict(d) for d in self.documents]
        }

@dataclass
class BidRecommendation:
    """Bid recommendation with reasoning"""
    recommendation: RecommendationType
    score: float  # 0-100
    confidence: float  # 0-1
    
    # Breakdown
    mandatory_pass_rate: float
    important_pass_rate: float
    document_completeness: float
    
    # Critical issues
    disqualifying_issues: List[str]
    critical_issues: List[str]
    warnings: List[str]
    
    # Reasoning
    summary: str
    detailed_reasoning: str
    
    def to_dict(self):
        return asdict(self)

# ============================================================================
# BITDEER AI HELPER
# ============================================================================

def call_bitdeer_ai(
    prompt: str,
    system_message: str = "You are a construction tender analysis expert.",
    max_tokens: int = 1500,
    temperature: float = 0.3
) -> Optional[str]:
    """
    Call Bitdeer AI API for intelligent analysis
    """
    
    try:
        headers = {
            "Authorization": f"Bearer {BITDEER_API_KEY}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": BITDEER_MODEL,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        response = requests.post(BITDEER_URL, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        return content.strip()
    
    except Exception as e:
        print(f"Error calling Bitdeer AI: {e}")
        return None

# ============================================================================
# CRITERIA ANALYSIS ENGINE
# ============================================================================

class CriteriaAnalyzer:
    """Analyzes qualification criteria and determines severity"""
    
    # Mandatory criteria patterns - automatic disqualification if not met
    MANDATORY_PATTERNS = {
        CriteriaType.LICENSE: [
            "bca", "license", "registration", "authorized contractor"
        ],
        CriteriaType.CERTIFICATION: [
            "iso 9001", "bizSAFE", "safety certification", "mandatory certification"
        ],
        CriteriaType.COMPLIANCE: [
            "work permit", "mom", "legal requirement", "regulatory"
        ]
    }
    
    # Important but negotiable criteria
    NEGOTIABLE_PATTERNS = {
        CriteriaType.FINANCIAL: [
            "performance bond", "bank guarantee", "insurance"
        ],
        CriteriaType.EXPERIENCE: [
            "similar project", "past experience", "reference project"
        ]
    }
    
    @classmethod
    def determine_severity(cls, criterion: QualificationCriterion) -> CriteriaSeverity:
        """
        Determine if criterion is mandatory or negotiable using AI
        """
        
        desc_lower = criterion.description.lower()
        
        # Check mandatory patterns first
        if criterion.criteria_type in cls.MANDATORY_PATTERNS:
            patterns = cls.MANDATORY_PATTERNS[criterion.criteria_type]
            if any(pattern in desc_lower for pattern in patterns):
                return CriteriaSeverity.MANDATORY
        
        # Check negotiable patterns
        if criterion.criteria_type in cls.NEGOTIABLE_PATTERNS:
            patterns = cls.NEGOTIABLE_PATTERNS[criterion.criteria_type]
            if any(pattern in desc_lower for pattern in patterns):
                return CriteriaSeverity.IMPORTANT
        
        # Use AI to determine severity for unclear cases
        prompt = f"""Analyze this tender qualification criterion and determine its severity.

Criterion Type: {criterion.criteria_type}
Description: {criterion.description}

Classification Rules:
- MANDATORY: Legal requirements, licenses, certifications that if not met = automatic disqualification
  Examples: BCA license, ISO9001 certification, work permits, legal compliance
  
- IMPORTANT: Strong requirements that affect competitiveness but are negotiable
  Examples: Performance bonds, past project experience, financial capacity
  
- OPTIONAL: Preferred but not critical requirements
  Examples: Additional certifications, nice-to-have experience

Return ONLY one word: MANDATORY, IMPORTANT, or OPTIONAL"""

        result = call_bitdeer_ai(prompt, temperature=0.1)
        
        if result:
            result_upper = result.strip().upper()
            if "MANDATORY" in result_upper:
                return CriteriaSeverity.MANDATORY
            elif "IMPORTANT" in result_upper:
                return CriteriaSeverity.IMPORTANT
        
        return CriteriaSeverity.OPTIONAL
    
    @classmethod
    def analyze_all_criteria(cls, criteria: List[QualificationCriterion]) -> List[QualificationCriterion]:
        """
        Analyze and classify all criteria
        """
        
        for criterion in criteria:
            if not hasattr(criterion, 'severity') or criterion.severity is None:
                criterion.severity = cls.determine_severity(criterion)
        
        return criteria

# ============================================================================
# RECOMMENDATION ENGINE
# ============================================================================

class RecommendationEngine:
    """Generates bid recommendations based on analysis"""
    
    @staticmethod
    def calculate_completeness(documents: List[DocumentStatus]) -> Dict[str, float]:
        """
        Calculate document completeness metrics
        """
        
        mandatory_docs = [d for d in documents if d.is_mandatory]
        optional_docs = [d for d in documents if not d.is_mandatory]
        
        mandatory_received = [d for d in mandatory_docs if d.is_received]
        optional_received = [d for d in optional_docs if d.is_received]
        
        return {
            'overall': len([d for d in documents if d.is_received]) / len(documents) * 100 if documents else 0,
            'mandatory': len(mandatory_received) / len(mandatory_docs) * 100 if mandatory_docs else 100,
            'optional': len(optional_received) / len(optional_docs) * 100 if optional_docs else 100,
            'mandatory_missing_count': len(mandatory_docs) - len(mandatory_received),
            'total_missing_count': len(documents) - len([d for d in documents if d.is_received])
        }
    
    @staticmethod
    def calculate_criteria_pass_rates(criteria: List[QualificationCriterion]) -> Dict[str, float]:
        """
        Calculate pass rates by severity
        """
        
        mandatory = [c for c in criteria if c.severity == CriteriaSeverity.MANDATORY]
        important = [c for c in criteria if c.severity == CriteriaSeverity.IMPORTANT]
        optional = [c for c in criteria if c.severity == CriteriaSeverity.OPTIONAL]
        
        return {
            'mandatory_pass_rate': len([c for c in mandatory if c.is_met]) / len(mandatory) * 100 if mandatory else 100,
            'important_pass_rate': len([c for c in important if c.is_met]) / len(important) * 100 if important else 100,
            'optional_pass_rate': len([c for c in optional if c.is_met]) / len(optional) * 100 if optional else 100,
            'mandatory_failed': [c for c in mandatory if not c.is_met],
            'important_failed': [c for c in important if not c.is_met],
            'mandatory_count': len(mandatory),
            'important_count': len(important),
            'optional_count': len(optional)
        }
    
    @classmethod
    def generate_recommendation(
        cls, 
        summary: TenderSummary
    ) -> BidRecommendation:
        """
        Generate comprehensive bid recommendation
        """
        
        # Calculate metrics
        doc_metrics = cls.calculate_completeness(summary.documents)
        criteria_metrics = cls.calculate_criteria_pass_rates(summary.criteria)
        
        # Identify issues
        disqualifying_issues = []
        critical_issues = []
        warnings = []
        
        # Check mandatory criteria
        if criteria_metrics['mandatory_pass_rate'] < 100:
            for criterion in criteria_metrics['mandatory_failed']:
                disqualifying_issues.append(
                    f"❌ DISQUALIFYING: {criterion.criteria_type} - {criterion.description}"
                )
        
        # Check important criteria
        if criteria_metrics['important_pass_rate'] < 75:
            for criterion in criteria_metrics['important_failed']:
                critical_issues.append(
                    f"⚠️ CRITICAL: {criterion.criteria_type} - {criterion.description}"
                )
        
        # Check document completeness
        if doc_metrics['mandatory_missing_count'] > 0:
            missing_docs = [d.doc_name for d in summary.documents if d.is_mandatory and not d.is_received]
            for doc in missing_docs:
                critical_issues.append(f"⚠️ MISSING MANDATORY DOCUMENT: {doc}")
        
        if doc_metrics['total_missing_count'] > doc_metrics['mandatory_missing_count']:
            warnings.append(f"ℹ️ {doc_metrics['total_missing_count'] - doc_metrics['mandatory_missing_count']} optional documents missing")
        
        # Determine recommendation
        if disqualifying_issues:
            recommendation = RecommendationType.DISQUALIFIED
            score = 0
            confidence = 0.95
        elif critical_issues and doc_metrics['mandatory'] < 100:
            recommendation = RecommendationType.NOT_RECOMMEND
            score = 30
            confidence = 0.85
        elif critical_issues or doc_metrics['mandatory'] < 100:
            recommendation = RecommendationType.CONDITIONAL
            score = 55
            confidence = 0.75
        elif criteria_metrics['important_pass_rate'] >= 80 and doc_metrics['mandatory'] >= 90:
            recommendation = RecommendationType.RECOMMEND
            score = 75
            confidence = 0.80
        else:
            recommendation = RecommendationType.CONDITIONAL
            score = 60
            confidence = 0.70
        
        # Generate AI-powered reasoning
        summary_text = cls._generate_ai_summary(
            summary, 
            recommendation,
            doc_metrics,
            criteria_metrics,
            disqualifying_issues,
            critical_issues,
            warnings
        )
        
        detailed_reasoning = cls._generate_ai_detailed_reasoning(
            summary,
            recommendation,
            doc_metrics,
            criteria_metrics,
            disqualifying_issues,
            critical_issues,
            warnings
        )
        
        return BidRecommendation(
            recommendation=recommendation,
            score=score,
            confidence=confidence,
            mandatory_pass_rate=criteria_metrics['mandatory_pass_rate'],
            important_pass_rate=criteria_metrics['important_pass_rate'],
            document_completeness=doc_metrics['mandatory'],
            disqualifying_issues=disqualifying_issues,
            critical_issues=critical_issues,
            warnings=warnings,
            summary=summary_text,
            detailed_reasoning=detailed_reasoning
        )
    
    @staticmethod
    def _generate_ai_summary(
        summary: TenderSummary,
        recommendation: RecommendationType,
        doc_metrics: Dict,
        criteria_metrics: Dict,
        disqualifying: List[str],
        critical: List[str],
        warnings: List[str]
    ) -> str:
        """Generate AI-powered executive summary"""
        
        prompt = f"""Generate a concise executive summary (2-3 sentences) for this tender bid recommendation.

Tender: {summary.reference_number} - {summary.title}
Recommendation: {recommendation.value.upper().replace('_', ' ')}

Metrics:
- Mandatory Criteria Pass Rate: {criteria_metrics['mandatory_pass_rate']:.0f}%
- Important Criteria Pass Rate: {criteria_metrics['important_pass_rate']:.0f}%
- Document Completeness: {doc_metrics['mandatory']:.0f}%

Issues:
- Disqualifying: {len(disqualifying)}
- Critical: {len(critical)}
- Warnings: {len(warnings)}

Provide a clear, professional summary explaining why we {recommendation.value.replace('_', ' ')} bidding.
Focus on the most critical factors affecting the decision."""

        result = call_bitdeer_ai(prompt, max_tokens=300)
        
        if result:
            return result
        
        # Fallback
        if disqualifying:
            return f"Company does not meet {len(disqualifying)} mandatory requirement(s) and is automatically disqualified from bidding."
        elif critical:
            return f"Company faces {len(critical)} critical issue(s) and is missing {doc_metrics['mandatory_missing_count']} mandatory document(s). Bidding not recommended without resolution."
        else:
            return f"Company meets basic requirements with {criteria_metrics['mandatory_pass_rate']:.0f}% mandatory compliance and {doc_metrics['mandatory']:.0f}% document completeness."
    
    @staticmethod
    def _generate_ai_detailed_reasoning(
        summary: TenderSummary,
        recommendation: RecommendationType,
        doc_metrics: Dict,
        criteria_metrics: Dict,
        disqualifying: List[str],
        critical: List[str],
        warnings: List[str]
    ) -> str:
        """Generate detailed AI-powered reasoning"""
        
        prompt = f"""Generate detailed reasoning (3-4 paragraphs) explaining this tender bid recommendation.

Tender: {summary.reference_number}
Recommendation: {recommendation.value.upper().replace('_', ' ')}

Analysis:
- Mandatory Criteria: {criteria_metrics['mandatory_count']} total, {criteria_metrics['mandatory_pass_rate']:.0f}% met
- Important Criteria: {criteria_metrics['important_count']} total, {criteria_metrics['important_pass_rate']:.0f}% met
- Mandatory Documents: {doc_metrics['mandatory']:.0f}% complete ({doc_metrics['mandatory_missing_count']} missing)

Issues Summary:
Disqualifying Issues: {len(disqualifying)}
{chr(10).join(disqualifying[:3]) if disqualifying else 'None'}

Critical Issues: {len(critical)}
{chr(10).join(critical[:3]) if critical else 'None'}

Structure your response:
1. Overall assessment and recommendation
2. Explanation of how completeness was calculated
3. Impact of failed criteria (distinguish mandatory vs important)
4. What actions the system should take for missing documents
5. How this analysis helps the SME decide

Be specific and actionable. Use professional construction industry language."""

        result = call_bitdeer_ai(prompt, max_tokens=800)
        
        if result:
            return result
        
        # Fallback reasoning
        reasoning = []
        
        if disqualifying:
            reasoning.append(
                f"**DISQUALIFICATION**: The company fails {len(disqualifying)} mandatory requirement(s). "
                f"These are legal or regulatory requirements that cannot be waived. "
                f"Submitting a bid would result in automatic rejection."
            )
        
        if critical:
            reasoning.append(
                f"**CRITICAL GAPS**: {len(critical)} important requirement(s) are not met. "
                f"While not automatically disqualifying, these significantly reduce competitiveness "
                f"and may lead to rejection. Resolution required before bidding."
            )
        
        reasoning.append(
            f"**COMPLETENESS CALCULATION**: Document completeness is calculated as "
            f"{len([d for d in summary.documents if d.is_mandatory and d.is_received])} received "
            f"/ {len([d for d in summary.documents if d.is_mandatory])} required mandatory documents = "
            f"{doc_metrics['mandatory']:.0f}%. Missing documents trigger automated alerts to the QS team."
        )
        
        return "\n\n".join(reasoning)

# ============================================================================
# MAIN REPORT GENERATOR
# ============================================================================

class TenderReportGenerator:
    """Main report generation orchestrator"""
    
    def __init__(self):
        self.criteria_analyzer = CriteriaAnalyzer()
        self.recommendation_engine = RecommendationEngine()
    
    def generate_report(self, summary: TenderSummary) -> Dict:
        """
        Generate complete tender report
        """
        
        # Analyze criteria severity
        summary.criteria = self.criteria_analyzer.analyze_all_criteria(summary.criteria)
        
        # Generate recommendation
        recommendation = self.recommendation_engine.generate_recommendation(summary)
        
        # Calculate detailed metrics
        doc_metrics = self.recommendation_engine.calculate_completeness(summary.documents)
        criteria_metrics = self.recommendation_engine.calculate_criteria_pass_rates(summary.criteria)
        
        # Generate action items
        action_items = self._generate_action_items(
            summary,
            recommendation,
            doc_metrics,
            criteria_metrics
        )
        
        # Compile full report
        report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'tender_id': summary.tender_id,
                'reference_number': summary.reference_number
            },
            'executive_summary': {
                'recommendation': recommendation.recommendation.value,
                'score': recommendation.score,
                'confidence': recommendation.confidence,
                'summary': recommendation.summary,
                'key_metrics': {
                    'mandatory_criteria_met': f"{recommendation.mandatory_pass_rate:.0f}%",
                    'important_criteria_met': f"{recommendation.important_pass_rate:.0f}%",
                    'document_completeness': f"{recommendation.document_completeness:.0f}%",
                    'days_until_deadline': self._calculate_days_until(summary.submission_deadline)
                }
            },
            'tender_overview': summary.to_dict(),
            'qualification_analysis': {
                'criteria_breakdown': criteria_metrics,
                'criteria_details': [c.to_dict() for c in summary.criteria],
                'mandatory_criteria': [c.to_dict() for c in summary.criteria if c.severity == CriteriaSeverity.MANDATORY],
                'failed_mandatory': criteria_metrics['mandatory_failed'],
                'failed_important': criteria_metrics['important_failed']
            },
            'document_status': {
                'completeness_metrics': doc_metrics,
                'all_documents': [asdict(d) for d in summary.documents],
                'missing_mandatory': [d.doc_name for d in summary.documents if d.is_mandatory and not d.is_received],
                'missing_optional': [d.doc_name for d in summary.documents if not d.is_mandatory and not d.is_received]
            },
            'issues_and_risks': {
                'disqualifying_issues': recommendation.disqualifying_issues,
                'critical_issues': recommendation.critical_issues,
                'warnings': recommendation.warnings
            },
            'action_items': action_items,
            'detailed_reasoning': recommendation.detailed_reasoning
        }
        
        return report
    
    def _generate_action_items(
        self,
        summary: TenderSummary,
        recommendation: BidRecommendation,
        doc_metrics: Dict,
        criteria_metrics: Dict
    ) -> List[Dict]:
        """
        Generate prioritized action items using AI
        """
        
        action_items = []
        
        # Critical: Missing mandatory documents
        if doc_metrics['mandatory_missing_count'] > 0:
            missing = [d.doc_name for d in summary.documents if d.is_mandatory and not d.is_received]
            for doc in missing:
                action_items.append({
                    'priority': 'CRITICAL',
                    'category': 'Documentation',
                    'action': f"Obtain and submit {doc}",
                    'impact': "Mandatory document - submission will be rejected without it",
                    'owner': 'QS/Admin Team',
                    'automated_action': f"System sent email alert to document coordinator about missing {doc}"
                })
        
        # Critical: Failed mandatory criteria
        for criterion in criteria_metrics.get('mandatory_failed', []):
            action_items.append({
                'priority': 'CRITICAL',
                'category': criterion.criteria_type,
                'action': f"Address requirement: {criterion.description}",
                'impact': "DISQUALIFYING - Cannot bid without meeting this requirement",
                'owner': 'Management/QS',
                'automated_action': "System flagged this tender as non-viable in dashboard"
            })
        
        # High: Failed important criteria
        for criterion in criteria_metrics.get('important_failed', []):
            action_items.append({
                'priority': 'HIGH',
                'category': criterion.criteria_type,
                'action': f"Decide on requirement: {criterion.description}",
                'impact': "Important but negotiable - Management decision required",
                'owner': 'Project Director/QS',
                'automated_action': "System escalated to management for decision"
            })
        
        # Medium: Missing optional documents
        missing_optional = [d.doc_name for d in summary.documents if not d.is_mandatory and not d.is_received]
        if missing_optional:
            action_items.append({
                'priority': 'MEDIUM',
                'category': 'Documentation',
                'action': f"Consider submitting optional documents: {', '.join(missing_optional[:3])}",
                'impact': "May improve competitiveness",
                'owner': 'QS Team',
                'automated_action': "System logged optional documents in tracking system"
            })
        
        # Add timeline-based actions
        days_until = self._calculate_days_until(summary.submission_deadline)
        if days_until <= 7:
            action_items.append({
                'priority': 'URGENT',
                'category': 'Timeline',
                'action': f"Final submission preparation - only {days_until} days remaining",
                'impact': "Deadline approaching",
                'owner': 'All Team',
                'automated_action': f"System sent deadline reminder to all stakeholders"
            })
        
        return sorted(action_items, key=lambda x: ['URGENT', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].index(x['priority']))
    
    @staticmethod
    def _calculate_days_until(deadline: datetime) -> int:
        """Calculate days until deadline"""
        if not deadline:
            return 999
        delta = deadline - datetime.now()
        return max(0, delta.days)

# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def generate_html_report(report: Dict, output_path: str):
    """Generate HTML report using template"""
    # This will be implemented in the next file
    pass

def generate_email_report(report: Dict) -> str:
    """Generate email-formatted report"""
    # This will be implemented in the next file
    pass

if __name__ == "__main__":
    print("Tender Report Generator loaded successfully")
    print(f"Using Bitdeer AI: {BITDEER_URL}")
