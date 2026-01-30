from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check if we're in mock mode (for testing without API key)
MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"

# OpenAI model to use
OPENAI_MODEL = "gpt-5.2"

# Try to find API key from multiple sources
def get_api_key():
    # 1. Environment variable
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    # 2. .env file in current directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key:
                        return key

    # 3. Home directory config
    home_config = Path.home() / ".openai" / "api_key"
    if home_config.exists():
        return home_config.read_text().strip()

    return None

app = FastAPI(title="Insurance LLM", description="Pixel-powered insurance document intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy client initialization
_client = None

def get_client():
    global _client
    if MOCK_MODE:
        return None  # Mock mode doesn't need a client
    if _client is None:
        api_key = get_api_key()
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY not configured. Set it in environment, .env file, or ~/.openai/api_key"
            )
        _client = OpenAI(api_key=api_key)
    return _client

def mock_extract(text: str) -> dict:
    """Generate mock extraction based on document content for testing"""
    text_lower = text.lower()

    # Try to extract insured name
    insured = None
    for pattern in [r'insured[:\s]+([A-Za-z\s&.,]+?)(?:\n|policy|$)',
                    r'named insured[:\s]+([A-Za-z\s&.,]+?)(?:\n|dba|$)',
                    r'prepared for[:\s]+([A-Za-z\s&.,]+?)(?:\n|date|$)',
                    r'policy for ([A-Za-z\s]+?)\.']:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            insured = match.group(1).strip()
            break

    # Try to extract policy number - look for specific patterns
    policy_num = None
    policy_patterns = [
        r'policy\s*#[:\s]*([A-Z]+-\d{4}-\d+)',  # BOP-2024-88821
        r'policy\s*number[:\s]*([A-Z]+-[A-Z]+-\d{4}-\d+)',  # CGL-NY-2023-44891
        r'quote\s*#[:\s]*([A-Z]+-\d{4}-\d+)',  # CPQ-2024-1182
        r'([A-Z]{2,4}-\d{4}-\d{4,})',  # Generic policy number pattern
        r'([A-Z]{2,4}-[A-Z]{2}-\d{4}-\d+)',  # With state code
    ]
    for pattern in policy_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            policy_num = match.group(1).upper()
            break

    # Try to extract carrier
    carrier = None
    for pattern in [r'carrier[:\s]+([A-Za-z\s]+?)(?:\n|eff|$)',
                    r'underwritten by[:\s]+([A-Za-z\s]+?)(?:\n|$)',
                    r'quoted by[:\s]+([A-Za-z\s]+?)(?:\n|$)']:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            carrier = match.group(1).strip()
            break

    # Try to extract premium - multiple patterns
    premium = None
    premium_patterns = [
        r'premium\s*(?:total)?[:\s]*\$?([\d,]+)(?:/yr)?',
        r'annual\s*premium[:\s]*\$?([\d,]+)',
        r'premium\s*increase[:\s]*\$?[\d,]+\s*->\s*\$?([\d,]+)',
        r'\$([\d,]+)\s*(?:/yr|per year|annually)',
    ]
    for pattern in premium_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            premium = f"${match.group(1)}"
            break

    # Extract coverages
    coverages = []
    coverage_patterns = [
        (r'GL[:\s]+\$?([\d,MmKk]+)', 'General Liability'),
        (r'general liability[:\s\w]*\$?([\d,MmKk/]+)', 'General Liability'),
        (r'building coverage[.\s]+\$?([\d,]+)', 'Building Coverage'),
        (r'business personal property[.\s]+\$?([\d,]+)', 'Business Personal Property'),
        (r'business income[.\s]+\$?([\d,]+)', 'Business Income'),
        (r'umbrella[:\s]+\$?([\d,MmKk]+)', 'Umbrella'),
        (r'professional liability[:\s\w]*\$?([\d,MmKk]+)', 'Professional Liability'),
        (r'equipment breakdown[.\s]+\$?([\d,]+)', 'Equipment Breakdown'),
        (r'coverage\s*\$?([\d,]+k?)', 'General Coverage'),
    ]
    for pattern, cov_type in coverage_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            limit = match.group(1)
            if not limit.startswith('$'):
                limit = f"${limit}"
            coverages.append({"type": cov_type, "limit": limit, "deductible": None, "notes": None})

    # Extract exclusions
    exclusions = []
    if 'ferment' in text_lower:
        exclusions.append("Fermentation explosions")
    if 'flood' in text_lower and ('no' in text_lower or 'excluded' in text_lower or 'separate' in text_lower):
        exclusions.append("Flood coverage excluded")
    if 'e-bike' in text_lower or 'ebike' in text_lower:
        exclusions.append("E-bike battery fires")
    if 'carbon fiber' in text_lower:
        exclusions.append("Carbon fiber frame defects over $10k")

    # Calculate risk score
    risk_score = 70
    if len(coverages) >= 3:
        risk_score += 10
    if 'umbrella' in text_lower:
        risk_score += 10
    if len(exclusions) > 2:
        risk_score -= 15

    return {
        "insured_name": insured,
        "policy_number": policy_num,
        "carrier": carrier,
        "effective_date": None,
        "expiration_date": None,
        "coverages": coverages,
        "total_premium": premium,
        "exclusions": exclusions,
        "special_conditions": [],
        "risk_score": min(100, max(1, risk_score)),
        "compliance_issues": [],
        "summary": f"Policy for {insured or 'unknown insured'} with {len(coverages)} coverage types."
    }

class DocumentInput(BaseModel):
    text: str
    doc_type: Optional[str] = "auto"

class Coverage(BaseModel):
    type: str
    limit: str
    deductible: Optional[str] = None
    notes: Optional[str] = None

# COI Compliance Checker Models
class COIData(BaseModel):
    insured_name: Optional[str] = None
    policy_number: Optional[str] = None
    carrier: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    gl_limit_per_occurrence: Optional[str] = None
    gl_limit_aggregate: Optional[str] = None
    workers_comp: bool = False
    auto_liability: bool = False
    umbrella_limit: Optional[str] = None
    additional_insured_checked: bool = False
    waiver_of_subrogation_checked: bool = False
    primary_noncontributory: bool = False
    certificate_holder: Optional[str] = None
    description_of_operations: Optional[str] = None
    cg_20_10_endorsement: bool = False
    cg_20_37_endorsement: bool = False

class ComplianceRequirement(BaseModel):
    name: str
    required_value: str
    actual_value: str
    status: str  # "pass", "fail", "warning"
    explanation: str

class ComplianceReport(BaseModel):
    overall_status: str  # "compliant", "non-compliant", "needs-review"
    coi_data: COIData
    critical_gaps: list[ComplianceRequirement] = []
    warnings: list[ComplianceRequirement] = []
    passed: list[ComplianceRequirement] = []
    risk_exposure: str
    fix_request_letter: str

    def __init__(self, **data):
        for field in ['critical_gaps', 'warnings', 'passed']:
            if data.get(field) is None:
                data[field] = []
        super().__init__(**data)

class COIComplianceInput(BaseModel):
    coi_text: str
    project_type: Optional[str] = None  # preset project type
    custom_requirements: Optional[dict] = None  # custom requirements
    state: Optional[str] = None  # 2-letter state code for state-specific rules

# State-specific insurance requirements data
# Based on comprehensive research as of January 2026

STATE_WORKERS_COMP = {
    # Format: "STATE": {"required": bool, "threshold": int or None, "construction_specific": str, "monopolistic": bool}
    "AL": {"required": True, "threshold": 5, "construction_specific": "5+ employees", "monopolistic": False},
    "AK": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "AZ": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "AR": {"required": True, "threshold": 3, "construction_specific": "3+ in construction (stricter)", "monopolistic": False},
    "CA": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "CO": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "CT": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "DE": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "FL": {"required": True, "threshold": 1, "construction_specific": "1+ in construction (stricter than 4 general)", "monopolistic": False},
    "GA": {"required": True, "threshold": 3, "construction_specific": "3+ employees", "monopolistic": False},
    "HI": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "ID": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "IL": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "IN": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "IA": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "KS": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "KY": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "LA": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "ME": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "MD": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "MA": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "MI": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "MN": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "MS": {"required": True, "threshold": 5, "construction_specific": "5+ employees", "monopolistic": False},
    "MO": {"required": True, "threshold": 1, "construction_specific": "1+ in construction (stricter than 5 general)", "monopolistic": False},
    "MT": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "NE": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "NV": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "NH": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "NJ": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "NM": {"required": True, "threshold": 1, "construction_specific": "1+ in construction (stricter than 3 general)", "monopolistic": False},
    "NY": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "NC": {"required": True, "threshold": 3, "construction_specific": "3+ employees", "monopolistic": False},
    "ND": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": True},
    "OH": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": True},
    "OK": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "OR": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "PA": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "RI": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "SC": {"required": True, "threshold": 4, "construction_specific": "4+ employees", "monopolistic": False},
    "SD": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "TN": {"required": True, "threshold": 1, "construction_specific": "1+ in construction (stricter than 5 general)", "monopolistic": False},
    "TX": {"required": False, "threshold": None, "construction_specific": "NOT REQUIRED - only fully voluntary state", "monopolistic": False},
    "UT": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "VT": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "VA": {"required": True, "threshold": 3, "construction_specific": "3+ employees", "monopolistic": False},
    "WA": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": True},
    "WV": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
    "WI": {"required": True, "threshold": 3, "construction_specific": "3+ employees", "monopolistic": False},
    "WY": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": True},
    "DC": {"required": True, "threshold": 1, "construction_specific": "All employees", "monopolistic": False},
}

# Anti-indemnity statutes - CRITICAL for Additional Insured coverage validity
# These laws limit or void indemnification/AI provisions for contractor negligence
STATE_ANTI_INDEMNITY = {
    # Format: "STATE": {"type": str, "voids_ai_for_sole_negligence": bool, "insurance_savings_clause": bool, "notes": str}
    "AL": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Voids indemnity for indemnitee's sole negligence; insurance savings clause preserves AI"},
    "AK": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance savings clause preserves AI"},
    "AZ": {"type": "Broad", "voids_ai_for_sole_negligence": True, "insurance_savings_clause": False, "notes": "CAUTION: Voids AI for indemnitee's negligence - insurance does NOT save it"},
    "AR": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Voids for sole/partial negligence but insurance savings clause applies"},
    "CA": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Type I construction - voids sole negligence; insurance savings clause preserves AI"},
    "CO": {"type": "Broad", "voids_ai_for_sole_negligence": True, "insurance_savings_clause": False, "notes": "CAUTION: Very broad - voids indemnity AND insurance for any indemnitee negligence"},
    "CT": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Limited to sole negligence; insurance provisions preserved"},
    "DE": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance savings clause applies"},
    "FL": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Limits indemnity to proportionate fault; insurance requirements allowed"},
    "GA": {"type": "Broad", "voids_ai_for_sole_negligence": True, "insurance_savings_clause": False, "notes": "CAUTION: Voids AI provisions for any indemnitee negligence"},
    "HI": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance provisions preserved"},
    "ID": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance savings clause applies"},
    "IL": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Void for sole/concurrent negligence; insurance savings clause preserves AI"},
    "IN": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Limited construction anti-indemnity; insurance savings clause"},
    "IA": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "KS": {"type": "Broad", "voids_ai_for_sole_negligence": True, "insurance_savings_clause": False, "notes": "CAUTION: Broad statute voids AI for indemnitee negligence"},
    "KY": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "LA": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance provisions preserved"},
    "ME": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "MD": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Void for sole/concurrent; insurance savings clause applies"},
    "MA": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance savings clause"},
    "MI": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance provisions preserved"},
    "MN": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction contracts; insurance requirements allowed"},
    "MS": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance savings clause"},
    "MO": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance provisions preserved"},
    "MT": {"type": "Broad", "voids_ai_for_sole_negligence": True, "insurance_savings_clause": False, "notes": "MOST RESTRICTIVE: Voids AI for ANY negligence of indemnitee - no insurance savings"},
    "NE": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance savings clause"},
    "NV": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance provisions preserved"},
    "NH": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "NJ": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance savings clause applies"},
    "NM": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Void for sole/concurrent; insurance savings clause"},
    "NY": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "GOL 5-322.1 - void for negligence; insurance savings clause preserves AI"},
    "NC": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance provisions preserved"},
    "ND": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "OH": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance savings clause"},
    "OK": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance provisions preserved"},
    "OR": {"type": "Broad", "voids_ai_for_sole_negligence": True, "insurance_savings_clause": False, "notes": "CAUTION: Broad statute - voids AI for indemnitee negligence"},
    "PA": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance savings clause applies"},
    "RI": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance provisions preserved"},
    "SC": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Void for sole/concurrent; insurance savings clause"},
    "SD": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "TN": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Void for sole/concurrent; insurance savings clause preserves AI"},
    "TX": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Chapter 151 - void for negligence; explicit insurance savings clause"},
    "UT": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Sole negligence void; insurance provisions preserved"},
    "VT": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "VA": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Void for sole/concurrent; insurance savings clause"},
    "WA": {"type": "Intermediate", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Void for negligence; insurance savings clause applies"},
    "WV": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "WI": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance provisions preserved"},
    "WY": {"type": "None", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "No anti-indemnity statute - full contractual freedom"},
    "DC": {"type": "Partial", "voids_ai_for_sole_negligence": False, "insurance_savings_clause": True, "notes": "Construction-specific; insurance savings clause"},
}

# State GL requirements for contractor licensing
STATE_GL_REQUIREMENTS = {
    # Format: "STATE": {"required_for_license": bool, "minimum_per_occurrence": int or None, "notes": str}
    "AL": {"required_for_license": True, "minimum_per_occurrence": 100000, "notes": "Required for licensing"},
    "AK": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for residential contractors"},
    "AZ": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required - amount varies by license class"},
    "AR": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "CA": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not required but must disclose if uninsured"},
    "CO": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "CT": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "DE": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "FL": {"required_for_license": True, "minimum_per_occurrence": 300000, "notes": "Required for construction licensing - $300K min"},
    "GA": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for residential contractors"},
    "HI": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for licensing"},
    "ID": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "IL": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "IN": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "IA": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "KS": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "KY": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "LA": {"required_for_license": True, "minimum_per_occurrence": 100000, "notes": "Required for licensing"},
    "ME": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "MD": {"required_for_license": True, "minimum_per_occurrence": 100000, "notes": "Required for home improvement"},
    "MA": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "MI": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for residential builders"},
    "MN": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for residential contractors"},
    "MS": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for licensing"},
    "MO": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "MT": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "NE": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "NV": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for licensing"},
    "NH": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "NJ": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated but common for home improvement"},
    "NM": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for licensing"},
    "NY": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated (local requirements vary)"},
    "NC": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for general contractors"},
    "ND": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "OH": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "OK": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "OR": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for CCB license"},
    "PA": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "RI": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "SC": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for licensing"},
    "SD": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "TN": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for licensing"},
    "TX": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated (no state licensing)"},
    "UT": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for licensing"},
    "VT": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "VA": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for Class A contractors"},
    "WA": {"required_for_license": True, "minimum_per_occurrence": None, "notes": "Required for registration"},
    "WV": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "WI": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "WY": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not state mandated"},
    "DC": {"required_for_license": False, "minimum_per_occurrence": None, "notes": "Not DC mandated"},
}

# State auto liability minimums (applies to all vehicles, construction often higher by contract)
STATE_AUTO_MINIMUMS = {
    # Format: "STATE": {"bodily_injury_per_person": int, "bodily_injury_per_accident": int, "property_damage": int, "combined_single_limit": int or None}
    "AL": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "AK": {"bodily_injury_per_person": 50000, "bodily_injury_per_accident": 100000, "property_damage": 25000, "combined_single_limit": None},
    "AZ": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 15000, "combined_single_limit": None},
    "AR": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "CA": {"bodily_injury_per_person": 15000, "bodily_injury_per_accident": 30000, "property_damage": 5000, "combined_single_limit": None},
    "CO": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 15000, "combined_single_limit": None},
    "CT": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "DE": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 10000, "combined_single_limit": None},
    "FL": {"bodily_injury_per_person": 0, "bodily_injury_per_accident": 0, "property_damage": 10000, "combined_single_limit": None},  # FL only requires PIP + PD
    "GA": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "HI": {"bodily_injury_per_person": 20000, "bodily_injury_per_accident": 40000, "property_damage": 10000, "combined_single_limit": None},
    "ID": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 15000, "combined_single_limit": None},
    "IL": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 20000, "combined_single_limit": None},
    "IN": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "IA": {"bodily_injury_per_person": 20000, "bodily_injury_per_accident": 40000, "property_damage": 15000, "combined_single_limit": None},
    "KS": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "KY": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "LA": {"bodily_injury_per_person": 15000, "bodily_injury_per_accident": 30000, "property_damage": 25000, "combined_single_limit": None},
    "ME": {"bodily_injury_per_person": 50000, "bodily_injury_per_accident": 100000, "property_damage": 25000, "combined_single_limit": None},
    "MD": {"bodily_injury_per_person": 30000, "bodily_injury_per_accident": 60000, "property_damage": 15000, "combined_single_limit": None},
    "MA": {"bodily_injury_per_person": 20000, "bodily_injury_per_accident": 40000, "property_damage": 5000, "combined_single_limit": None},
    "MI": {"bodily_injury_per_person": 50000, "bodily_injury_per_accident": 100000, "property_damage": 10000, "combined_single_limit": None},
    "MN": {"bodily_injury_per_person": 30000, "bodily_injury_per_accident": 60000, "property_damage": 10000, "combined_single_limit": None},
    "MS": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "MO": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "MT": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 20000, "combined_single_limit": None},
    "NE": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "NV": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 20000, "combined_single_limit": None},
    "NH": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "NJ": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "NM": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 10000, "combined_single_limit": None},
    "NY": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 10000, "combined_single_limit": None},
    "NC": {"bodily_injury_per_person": 30000, "bodily_injury_per_accident": 60000, "property_damage": 25000, "combined_single_limit": None},
    "ND": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "OH": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "OK": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "OR": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 20000, "combined_single_limit": None},
    "PA": {"bodily_injury_per_person": 15000, "bodily_injury_per_accident": 30000, "property_damage": 5000, "combined_single_limit": None},
    "RI": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "SC": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "SD": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "TN": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 15000, "combined_single_limit": None},
    "TX": {"bodily_injury_per_person": 30000, "bodily_injury_per_accident": 60000, "property_damage": 25000, "combined_single_limit": None},
    "UT": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 65000, "property_damage": 15000, "combined_single_limit": None},
    "VT": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 10000, "combined_single_limit": None},
    "VA": {"bodily_injury_per_person": 30000, "bodily_injury_per_accident": 60000, "property_damage": 20000, "combined_single_limit": None},
    "WA": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 10000, "combined_single_limit": None},
    "WV": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 25000, "combined_single_limit": None},
    "WI": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 10000, "combined_single_limit": None},
    "WY": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 20000, "combined_single_limit": None},
    "DC": {"bodily_injury_per_person": 25000, "bodily_injury_per_accident": 50000, "property_damage": 10000, "combined_single_limit": None},
}

# Preset project types with their requirements
PROJECT_TYPE_REQUIREMENTS = {
    "commercial_construction": {
        "name": "Commercial Construction",
        "gl_per_occurrence": 1000000,
        "gl_aggregate": 2000000,
        "umbrella_required": True,
        "umbrella_minimum": 2000000,
        "workers_comp_required": True,
        "auto_liability_required": True,
        "additional_insured_required": True,
        "waiver_of_subrogation_required": True,
        "primary_noncontributory_required": True,
        "cg_20_10_required": True,
        "cg_20_37_required": True,
    },
    "residential_construction": {
        "name": "Residential Construction",
        "gl_per_occurrence": 500000,
        "gl_aggregate": 1000000,
        "umbrella_required": False,
        "umbrella_minimum": 0,
        "workers_comp_required": True,
        "auto_liability_required": True,
        "additional_insured_required": True,
        "waiver_of_subrogation_required": False,
        "primary_noncontributory_required": False,
        "cg_20_10_required": False,
        "cg_20_37_required": False,
    },
    "government_municipal": {
        "name": "Government/Municipal",
        "gl_per_occurrence": 2000000,
        "gl_aggregate": 4000000,
        "umbrella_required": True,
        "umbrella_minimum": 5000000,
        "workers_comp_required": True,
        "auto_liability_required": True,
        "additional_insured_required": True,
        "waiver_of_subrogation_required": True,
        "primary_noncontributory_required": True,
        "cg_20_10_required": True,
        "cg_20_37_required": True,
    },
    "industrial_manufacturing": {
        "name": "Industrial/Manufacturing",
        "gl_per_occurrence": 2000000,
        "gl_aggregate": 4000000,
        "umbrella_required": True,
        "umbrella_minimum": 5000000,
        "workers_comp_required": True,
        "auto_liability_required": True,
        "additional_insured_required": True,
        "waiver_of_subrogation_required": True,
        "primary_noncontributory_required": True,
        "cg_20_10_required": True,
        "cg_20_37_required": True,
    },
}

class ExtractedPolicy(BaseModel):
    insured_name: Optional[str] = None
    policy_number: Optional[str] = None
    carrier: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    coverages: Optional[list[Coverage]] = []
    total_premium: Optional[str] = None
    exclusions: Optional[list[str]] = []
    special_conditions: Optional[list[str]] = []
    risk_score: Optional[int] = None
    compliance_issues: Optional[list[str]] = []
    summary: Optional[str] = None

    def __init__(self, **data):
        # Convert None to empty lists for list fields
        for field in ['coverages', 'exclusions', 'special_conditions', 'compliance_issues']:
            if data.get(field) is None:
                data[field] = []
        super().__init__(**data)

COI_EXTRACTION_PROMPT = """You are an expert insurance document analyst specializing in Certificates of Insurance (ACORD 25 forms).

Extract structured data from this COI document. Be thorough and precise - this data will be used for compliance checking.

Return a JSON object with these fields:
- insured_name: Name of the insured party (the subcontractor/vendor)
- policy_number: Policy number(s) if present
- carrier: Insurance carrier/company name
- effective_date: Policy start date (format: YYYY-MM-DD if possible)
- expiration_date: Policy end date (format: YYYY-MM-DD if possible)
- gl_limit_per_occurrence: General liability per occurrence limit (e.g., "$1,000,000")
- gl_limit_aggregate: General liability aggregate limit (e.g., "$2,000,000")
- workers_comp: boolean - is workers compensation coverage present?
- auto_liability: boolean - is auto liability coverage present?
- umbrella_limit: Umbrella/excess liability limit if present (e.g., "$5,000,000")
- additional_insured_checked: boolean - is the Additional Insured checkbox marked?
- waiver_of_subrogation_checked: boolean - is the Waiver of Subrogation checkbox marked?
- primary_noncontributory: boolean - is primary and non-contributory language present?
- certificate_holder: Name and address of certificate holder
- description_of_operations: Contents of the Description of Operations field
- cg_20_10_endorsement: boolean - is CG 20 10 (ongoing operations) endorsement referenced?
- cg_20_37_endorsement: boolean - is CG 20 37 (completed operations) endorsement referenced?

IMPORTANT: Being listed as "Certificate Holder" does NOT make someone an Additional Insured. These are separate concepts.

If a field isn't clearly present, use null for strings or false for booleans.

COI Document:
<<DOCUMENT>>

Return ONLY valid JSON, no markdown formatting."""

COI_COMPLIANCE_PROMPT = """You are an expert insurance compliance analyst. Analyze this COI data against the contract requirements and identify all compliance gaps.

CRITICAL DISTINCTION: Being listed as "Certificate Holder" does NOT make someone an Additional Insured. The Additional Insured box must be checked AND proper endorsements (CG 20 10, CG 20 37) should be referenced. This distinction has cost companies millions in lawsuits.

COI Data Extracted:
<<COI_DATA>>

Contract Requirements:
<<REQUIREMENTS>>

Project Type: <<PROJECT_TYPE>>

Analyze EACH requirement and return a JSON object with:
{
  "overall_status": "compliant" | "non-compliant" | "needs-review",
  "critical_gaps": [
    {
      "name": "Requirement name",
      "required_value": "What was required",
      "actual_value": "What the COI shows",
      "status": "fail",
      "explanation": "Why this is a critical gap and what the risk is"
    }
  ],
  "warnings": [
    {
      "name": "Requirement name",
      "required_value": "What was required",
      "actual_value": "What the COI shows",
      "status": "warning",
      "explanation": "Why this needs attention"
    }
  ],
  "passed": [
    {
      "name": "Requirement name",
      "required_value": "What was required",
      "actual_value": "What the COI shows",
      "status": "pass",
      "explanation": "Requirement satisfied"
    }
  ],
  "risk_exposure": "Estimated dollar exposure if gaps are not addressed (e.g., '$1M+ potential liability')",
  "fix_request_letter": "A professional but firm letter to send to the subcontractor requesting corrections. Include specific items that need to be fixed, reference the contract requirements, and set a deadline. The letter should be ready to copy and send."
}

Check these items (mark as critical gaps if failed):
1. GL Per Occurrence Limit - meets or exceeds required minimum
2. GL Aggregate Limit - meets or exceeds required minimum
3. Additional Insured Status - box is checked AND endorsement is referenced (not just certificate holder!)
4. Waiver of Subrogation - checked if required
5. Coverage Dates - effective before project, expiration after project end
6. Workers Compensation - present if required

Check these items (mark as warnings if issues found):
7. CG 20 10 Endorsement - ongoing operations coverage
8. CG 20 37 Endorsement - completed operations coverage
9. Primary & Non-Contributory language
10. Umbrella/Excess limits if required
11. Policy numbers present and formatted correctly
12. Certificate holder name/address correct

Return ONLY valid JSON, no markdown formatting."""

EXTRACTION_PROMPT = """You are an expert insurance document analyst. Extract structured data from this insurance document.

Return a JSON object with these fields:
- insured_name: Name of the insured party
- policy_number: Policy number if present
- carrier: Insurance carrier/company name
- effective_date: Policy start date (format: YYYY-MM-DD if possible)
- expiration_date: Policy end date (format: YYYY-MM-DD if possible)
- coverages: Array of objects with keys: type, limit, deductible, notes
- total_premium: Total premium amount
- exclusions: Array of exclusion strings
- special_conditions: Array of special conditions or endorsements
- risk_score: 1-100 score based on coverage adequacy (100 = excellent)
- compliance_issues: Array of potential compliance concerns
- summary: 2-3 sentence summary of the policy

Be thorough but only include information actually present in the document.
If a field isn't present, use null.

Document text:
<<DOCUMENT>>

Return ONLY valid JSON, no markdown formatting."""

@app.get("/")
def read_root():
    return {"status": "online", "message": "Insurance LLM API - Pixel Perfect Coverage Analysis"}

@app.post("/api/extract", response_model=ExtractedPolicy)
async def extract_document(doc: DocumentInput):
    """Extract structured data from insurance document text"""
    try:
        # Use mock extraction in mock mode
        if MOCK_MODE:
            extracted = mock_extract(doc.text)
            return ExtractedPolicy(**extracted)

        prompt = EXTRACTION_PROMPT.replace("<<DOCUMENT>>", doc.text)
        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        response_text = response.choices[0].message.content
        # Clean up potential markdown formatting
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        extracted = json.loads(response_text)
        return ExtractedPolicy(**extracted)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/compare")
async def compare_quotes(quotes: list[DocumentInput]):
    """Compare multiple insurance quotes"""
    if len(quotes) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 quotes to compare")

    # Extract each quote
    extracted_quotes = []
    for quote in quotes:
        extracted = await extract_document(quote)
        extracted_quotes.append(extracted)

    # Generate comparison
    comparison_prompt = f"""Compare these {len(extracted_quotes)} insurance quotes and provide a recommendation.

Quotes:
{[q.model_dump() for q in extracted_quotes]}

Provide a JSON response with:
- recommendation: Which quote is best and why (string)
- comparison_table: Array of objects comparing key metrics
- pros_cons: Object with quote index as key, containing pros and cons arrays
- cost_analysis: Premium comparison and value assessment
- risk_assessment: Which provides better risk coverage

Return ONLY valid JSON."""

    try:
        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": comparison_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        return json.loads(response_text.strip())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-proposal")
async def generate_proposal(extracted: ExtractedPolicy):
    """Generate a polished client-ready proposal from extracted data"""

    # Mock proposal generation
    if MOCK_MODE:
        coverages_text = "\n".join([f"- **{c.type}**: {c.limit}" for c in extracted.coverages]) if extracted.coverages else "- No coverages specified"
        exclusions_text = "\n".join([f"- {e}" for e in extracted.exclusions]) if extracted.exclusions else "- None noted"

        proposal = f"""# Insurance Coverage Summary

## Policy Overview
- **Insured**: {extracted.insured_name or 'Not specified'}
- **Policy Number**: {extracted.policy_number or 'Not specified'}
- **Carrier**: {extracted.carrier or 'Not specified'}
- **Premium**: {extracted.total_premium or 'Not specified'}

## Coverage Details
{coverages_text}

## Important Exclusions
{exclusions_text}

## Risk Assessment
Coverage adequacy score: **{extracted.risk_score or 'N/A'}/100**

## Recommendations
1. Review all exclusions carefully with your broker
2. Consider additional coverage for any identified gaps
3. Verify all policy dates and deadlines

---
*Generated by Insurance.exe - Pixel Perfect Coverage Analysis*
"""
        return {"proposal": proposal}

    proposal_prompt = f"""Create a professional insurance proposal summary for a client based on this extracted policy data:

{extracted.model_dump()}

Write a clear, client-friendly proposal that:
1. Summarizes key coverages in plain English
2. Highlights important dates and deadlines
3. Notes any gaps or concerns
4. Provides actionable recommendations

Format as markdown with clear sections. Keep it concise but comprehensive."""

    try:
        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=2048,
            messages=[{"role": "user", "content": proposal_prompt}]
        )

        return {"proposal": response.choices[0].message.content}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def parse_limit_to_number(limit_str: str) -> int:
    """Parse a limit string like '$1,000,000' or '$1M' to an integer"""
    if not limit_str:
        return 0
    # Remove $ and commas
    cleaned = limit_str.replace('$', '').replace(',', '').strip().upper()
    # Handle M for million, K for thousand
    if 'M' in cleaned:
        try:
            return int(float(cleaned.replace('M', '')) * 1000000)
        except:
            return 0
    if 'K' in cleaned:
        try:
            return int(float(cleaned.replace('K', '')) * 1000)
        except:
            return 0
    try:
        return int(cleaned)
    except:
        return 0

def mock_coi_extract(text: str) -> dict:
    """Generate mock COI extraction for testing"""
    text_lower = text.lower()

    # Try to extract insured name
    insured = None
    for pattern in [r'insured[:\s]+([A-Za-z\s&.,]+?)(?:\n|policy|$)',
                    r'named insured[:\s]+([A-Za-z\s&.,]+?)(?:\n|dba|$)']:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            insured = match.group(1).strip()
            break

    # Extract GL limits
    gl_per_occ = None
    gl_agg = None
    gl_match = re.search(r'(?:each occurrence|per occurrence)[:\s]*\$?([\d,]+)', text, re.IGNORECASE)
    if gl_match:
        gl_per_occ = f"${gl_match.group(1)}"
    agg_match = re.search(r'(?:general aggregate|aggregate)[:\s]*\$?([\d,]+)', text, re.IGNORECASE)
    if agg_match:
        gl_agg = f"${agg_match.group(1)}"

    # Check for additional insured
    ai_checked = bool(re.search(r'\[x\]\s*additional\s*insured', text, re.IGNORECASE)) or \
                 bool(re.search(r'additional\s*insured.*checked', text, re.IGNORECASE)) or \
                 ('additional insured' in text_lower and '[x]' in text_lower)

    # Check for waiver of subrogation
    wos_checked = bool(re.search(r'\[x\]\s*waiver\s*of\s*subrogation', text, re.IGNORECASE)) or \
                  bool(re.search(r'waiver\s*of\s*subrogation.*checked', text, re.IGNORECASE))

    # Certificate holder
    cert_holder = None
    ch_match = re.search(r'certificate holder[:\s]*\n?([A-Za-z\s&.,\n]+?)(?:\n\n|$)', text, re.IGNORECASE)
    if ch_match:
        cert_holder = ch_match.group(1).strip()

    # Umbrella limit
    umbrella = None
    umb_match = re.search(r'umbrella[:\s]*\$?([\d,MmKk]+)', text, re.IGNORECASE)
    if umb_match:
        umbrella = f"${umb_match.group(1)}"

    return {
        "insured_name": insured,
        "policy_number": None,
        "carrier": None,
        "effective_date": None,
        "expiration_date": None,
        "gl_limit_per_occurrence": gl_per_occ,
        "gl_limit_aggregate": gl_agg,
        "workers_comp": 'workers comp' in text_lower or 'work comp' in text_lower,
        "auto_liability": 'auto' in text_lower or 'automobile' in text_lower,
        "umbrella_limit": umbrella,
        "additional_insured_checked": ai_checked,
        "waiver_of_subrogation_checked": wos_checked,
        "primary_noncontributory": 'primary' in text_lower and 'non-contributory' in text_lower,
        "certificate_holder": cert_holder,
        "description_of_operations": None,
        "cg_20_10_endorsement": 'cg 20 10' in text_lower or 'cg2010' in text_lower,
        "cg_20_37_endorsement": 'cg 20 37' in text_lower or 'cg2037' in text_lower,
    }

def mock_compliance_check(coi_data: dict, requirements: dict, state: str = None) -> dict:
    """Generate mock compliance check for testing"""
    critical_gaps = []
    warnings = []
    passed = []
    state_warnings = []

    # Get state-specific rules if state provided
    state_upper = state.upper() if state else None
    wc_rules = STATE_WORKERS_COMP.get(state_upper) if state_upper else None
    ai_rules = STATE_ANTI_INDEMNITY.get(state_upper) if state_upper else None
    gl_rules = STATE_GL_REQUIREMENTS.get(state_upper) if state_upper else None
    auto_rules = STATE_AUTO_MINIMUMS.get(state_upper) if state_upper else None

    # Check GL per occurrence
    coi_limit = parse_limit_to_number(coi_data.get('gl_limit_per_occurrence', '') or '')
    req_limit = requirements.get('gl_per_occurrence', 1000000)
    if coi_limit >= req_limit:
        passed.append({
            "name": "GL Per Occurrence Limit",
            "required_value": f"${req_limit:,}",
            "actual_value": coi_data.get('gl_limit_per_occurrence', 'Not specified'),
            "status": "pass",
            "explanation": "Limit meets or exceeds requirement"
        })
    else:
        critical_gaps.append({
            "name": "GL Per Occurrence Limit",
            "required_value": f"${req_limit:,}",
            "actual_value": coi_data.get('gl_limit_per_occurrence', 'Not specified'),
            "status": "fail",
            "explanation": f"INADEQUATE COVERAGE: Limit is ${coi_limit:,} but contract requires ${req_limit:,}. This leaves a ${req_limit - coi_limit:,} gap in coverage."
        })

    # Check GL aggregate
    coi_agg = parse_limit_to_number(coi_data.get('gl_limit_aggregate', '') or '')
    req_agg = requirements.get('gl_aggregate', 2000000)
    if coi_agg >= req_agg:
        passed.append({
            "name": "GL Aggregate Limit",
            "required_value": f"${req_agg:,}",
            "actual_value": coi_data.get('gl_limit_aggregate', 'Not specified'),
            "status": "pass",
            "explanation": "Aggregate limit meets or exceeds requirement"
        })
    else:
        critical_gaps.append({
            "name": "GL Aggregate Limit",
            "required_value": f"${req_agg:,}",
            "actual_value": coi_data.get('gl_limit_aggregate', 'Not specified'),
            "status": "fail",
            "explanation": f"INADEQUATE COVERAGE: Aggregate is ${coi_agg:,} but contract requires ${req_agg:,}."
        })

    # Check Additional Insured (CRITICAL)
    if requirements.get('additional_insured_required', True):
        if coi_data.get('additional_insured_checked'):
            if coi_data.get('cg_20_10_endorsement') or coi_data.get('cg_20_37_endorsement'):
                passed.append({
                    "name": "Additional Insured Status",
                    "required_value": "Additional Insured box checked with proper endorsement",
                    "actual_value": "Box checked with endorsement referenced",
                    "status": "pass",
                    "explanation": "Additional insured status properly documented"
                })
            else:
                warnings.append({
                    "name": "Additional Insured Endorsement",
                    "required_value": "CG 20 10 / CG 20 37 endorsement referenced",
                    "actual_value": "Box checked but no endorsement number listed",
                    "status": "warning",
                    "explanation": "Additional Insured box is checked but no specific endorsement (CG 20 10, CG 20 37) is referenced. Request confirmation of actual endorsement."
                })
        else:
            critical_gaps.append({
                "name": "Additional Insured Status",
                "required_value": "Must be named as Additional Insured",
                "actual_value": "Additional Insured box NOT checked",
                "status": "fail",
                "explanation": "CRITICAL: Being listed as Certificate Holder does NOT make you an Additional Insured. The California scaffolding case (Pardee v. Pacific) resulted in $3.5M+ in damages when this distinction was ignored. Request endorsement CG 20 10 for ongoing operations."
            })

    # Check Waiver of Subrogation
    if requirements.get('waiver_of_subrogation_required', True):
        if coi_data.get('waiver_of_subrogation_checked'):
            passed.append({
                "name": "Waiver of Subrogation",
                "required_value": "Waiver of Subrogation required",
                "actual_value": "Waiver of Subrogation checked",
                "status": "pass",
                "explanation": "Waiver of subrogation is in place"
            })
        else:
            critical_gaps.append({
                "name": "Waiver of Subrogation",
                "required_value": "Waiver of Subrogation required",
                "actual_value": "Waiver of Subrogation NOT checked",
                "status": "fail",
                "explanation": "Missing Waiver of Subrogation. This allows the subcontractor's insurer to sue you after paying a claim. Request this endorsement."
            })

    # Check Workers Comp
    if requirements.get('workers_comp_required', True):
        if coi_data.get('workers_comp'):
            passed.append({
                "name": "Workers Compensation",
                "required_value": "Workers Compensation required",
                "actual_value": "Workers Comp present",
                "status": "pass",
                "explanation": "Workers compensation coverage confirmed"
            })
        else:
            critical_gaps.append({
                "name": "Workers Compensation",
                "required_value": "Workers Compensation required",
                "actual_value": "Workers Comp NOT shown",
                "status": "fail",
                "explanation": "No workers compensation coverage shown. This is required for all contractors with employees."
            })

    # Check Umbrella if required
    if requirements.get('umbrella_required', False):
        umbrella_limit = parse_limit_to_number(coi_data.get('umbrella_limit', '') or '')
        req_umbrella = requirements.get('umbrella_minimum', 2000000)
        if umbrella_limit >= req_umbrella:
            passed.append({
                "name": "Umbrella/Excess Liability",
                "required_value": f"${req_umbrella:,} umbrella required",
                "actual_value": coi_data.get('umbrella_limit') or 'Not specified',
                "status": "pass",
                "explanation": "Umbrella coverage meets requirement"
            })
        else:
            warnings.append({
                "name": "Umbrella/Excess Liability",
                "required_value": f"${req_umbrella:,} umbrella required",
                "actual_value": coi_data.get('umbrella_limit') or 'Not shown',
                "status": "warning",
                "explanation": f"Umbrella coverage is insufficient or not shown. Contract requires ${req_umbrella:,}."
            })

    # State-specific mitigation strategies for broad anti-indemnity states
    STATE_MITIGATIONS = {
        "AZ": "Consider CG 24 26 endorsement or higher primary limits on your own CGL.",
        "CO": "Wrap-up/OCIP recommended for larger projects. Ensure contractual liability coverage on your policy.",
        "GA": "Primary & non-contributory language remains valid. Verify your own CGL limits are adequate.",
        "KS": "Wrap-up programs or higher umbrella limits on your own policy recommended.",
        "MT": "OCIP/CCIP wrap-up insurance or project-specific coverage. Your own policy should be primary.",
        "OR": "CG 24 26 amendment endorsement or contractual liability on your CGL.",
    }

    # STATE-SPECIFIC CHECKS
    if state_upper:
        # Anti-Indemnity Statute Note (informational for AI coverage)
        if ai_rules:
            if ai_rules.get('voids_ai_for_sole_negligence'):
                mitigation = STATE_MITIGATIONS.get(state_upper, "Review coverage with your broker.")
                warnings.append({
                    "name": f"{state_upper} Anti-Indemnity Note",
                    "required_value": "AI coverage for shared fault",
                    "actual_value": "Limited by state statute",
                    "status": "warning",
                    "explanation": f"{state_upper}'s broad anti-indemnity statute limits AI coverage when you share fault. {mitigation}"
                })
            elif ai_rules.get('type') not in ['None', None]:
                warnings.append({
                    "name": f"{state_upper} Anti-Indemnity",
                    "required_value": "Standard AI coverage",
                    "actual_value": f"{ai_rules.get('type')} statute applies",
                    "status": "warning",
                    "explanation": f"{ai_rules.get('type')} anti-indemnity statute. Insurance savings clause {'preserves AI coverage' if ai_rules.get('insurance_savings_clause') else 'does not apply'}."
                })

        # Workers Comp State-Specific Rules
        if wc_rules:
            if not wc_rules.get('required'):
                # Texas - only state where WC is optional
                warnings.append({
                    "name": f"{state_upper} Workers Comp",
                    "required_value": "Workers Comp recommended",
                    "actual_value": coi_data.get('workers_comp') and "Present" or "Not shown",
                    "status": "warning" if not coi_data.get('workers_comp') else "pass",
                    "explanation": f"{state_upper} is the only state where Workers' Compensation is fully voluntary. {wc_rules.get('construction_specific', '')} However, most contracts still require it. Non-subscribers face unlimited liability exposure."
                })
            elif wc_rules.get('monopolistic'):
                passed.append({
                    "name": f"{state_upper} Monopolistic State Fund",
                    "required_value": "State fund coverage",
                    "actual_value": "Monopolistic state rules apply",
                    "status": "pass",
                    "explanation": f"{state_upper} is a monopolistic state - WC must be purchased through the state fund ({state_upper} State Insurance Fund). Private insurers cannot write WC here."
                })
            elif wc_rules.get('threshold') and wc_rules.get('threshold') > 1:
                # States with higher thresholds
                warnings.append({
                    "name": f"{state_upper} WC Threshold",
                    "required_value": f"WC required for {wc_rules.get('threshold')}+ employees",
                    "actual_value": f"Construction rule: {wc_rules.get('construction_specific', 'Standard')}",
                    "status": "warning",
                    "explanation": f"{state_upper} requires WC for {wc_rules.get('threshold')}+ employees. Construction-specific: {wc_rules.get('construction_specific', '')}. Verify employee count threshold is met."
                })

        # State GL Requirements
        if gl_rules and gl_rules.get('required_for_license'):
            if gl_rules.get('minimum_per_occurrence'):
                state_min = gl_rules.get('minimum_per_occurrence')
                coi_limit = parse_limit_to_number(coi_data.get('gl_limit_per_occurrence', '') or '')
                if coi_limit < state_min:
                    warnings.append({
                        "name": f"{state_upper} State GL Minimum",
                        "required_value": f"${state_min:,} state minimum",
                        "actual_value": coi_data.get('gl_limit_per_occurrence', 'Not specified'),
                        "status": "warning",
                        "explanation": f"{state_upper} requires minimum ${state_min:,} GL for contractor licensing. {gl_rules.get('notes', '')} Current coverage may not meet state licensing requirements."
                    })

    # Determine overall status
    if len(critical_gaps) > 0:
        overall_status = "non-compliant"
    elif len(warnings) > 0:
        overall_status = "needs-review"
    else:
        overall_status = "compliant"

    # Calculate risk exposure
    total_gap = 0
    for gap in critical_gaps:
        if 'GL' in gap['name']:
            total_gap += 1000000  # Estimate $1M exposure per GL gap
        elif 'Additional Insured' in gap['name']:
            total_gap += 3500000  # Based on real case outcomes
        elif 'Waiver' in gap['name']:
            total_gap += 500000

    risk_exposure = f"${total_gap:,}+ potential liability exposure" if total_gap > 0 else "Minimal risk exposure"

    # Generate fix request letter
    fix_items = []
    for gap in critical_gaps:
        fix_items.append(f"- {gap['name']}: {gap['explanation']}")
    for warn in warnings:
        fix_items.append(f"- {warn['name']}: {warn['explanation']}")

    fix_letter = f"""RE: Certificate of Insurance Compliance - Immediate Action Required

Dear {coi_data.get('insured_name', '[Subcontractor Name]')},

We have reviewed the Certificate of Insurance submitted for your work on our project and identified the following compliance gaps that must be addressed before work can proceed:

ITEMS REQUIRING CORRECTION:
{chr(10).join(fix_items)}

Per our contract agreement, the following insurance requirements must be met:
- General Liability: ${requirements.get('gl_per_occurrence', 1000000):,} per occurrence / ${requirements.get('gl_aggregate', 2000000):,} aggregate
- Additional Insured endorsement (CG 20 10 for ongoing operations, CG 20 37 for completed operations)
- Waiver of Subrogation endorsement
- Workers Compensation at statutory limits

IMPORTANT: Being listed as "Certificate Holder" does NOT satisfy the Additional Insured requirement. We must be named as an Additional Insured on your policy with the proper endorsement.

Please provide an updated Certificate of Insurance with the required coverages and endorsements within 5 business days.

If you have questions, please contact us immediately.

Regards,
[Your Name]
[Your Company]
"""

    return {
        "overall_status": overall_status,
        "coi_data": coi_data,
        "critical_gaps": critical_gaps,
        "warnings": warnings,
        "passed": passed,
        "risk_exposure": risk_exposure,
        "fix_request_letter": fix_letter
    }

@app.post("/api/check-coi-compliance", response_model=ComplianceReport)
async def check_coi_compliance(input: COIComplianceInput):
    """Check a Certificate of Insurance against contract requirements"""
    try:
        # Get requirements from preset or custom
        if input.project_type and input.project_type in PROJECT_TYPE_REQUIREMENTS:
            requirements = PROJECT_TYPE_REQUIREMENTS[input.project_type]
        elif input.custom_requirements:
            requirements = input.custom_requirements
        else:
            # Default to commercial construction requirements
            requirements = PROJECT_TYPE_REQUIREMENTS["commercial_construction"]

        project_type_name = requirements.get('name', 'Commercial Construction')

        # Use mock mode or real API
        if MOCK_MODE:
            coi_data = mock_coi_extract(input.coi_text)
            result = mock_compliance_check(coi_data, requirements, input.state)
            return ComplianceReport(**result)

        # Step 1: Extract COI data
        extract_prompt = COI_EXTRACTION_PROMPT.replace("<<DOCUMENT>>", input.coi_text)
        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": extract_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        coi_data = json.loads(response_text)

        # Step 2: Check compliance
        compliance_prompt = COI_COMPLIANCE_PROMPT.replace("<<COI_DATA>>", json.dumps(coi_data, indent=2))
        compliance_prompt = compliance_prompt.replace("<<REQUIREMENTS>>", json.dumps(requirements, indent=2))
        compliance_prompt = compliance_prompt.replace("<<PROJECT_TYPE>>", project_type_name)

        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": compliance_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        result = json.loads(response_text)
        result['coi_data'] = coi_data

        return ComplianceReport(**result)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/project-types")
async def get_project_types():
    """Get available preset project types and their requirements"""
    return {
        key: {
            "name": val["name"],
            "gl_per_occurrence": f"${val['gl_per_occurrence']:,}",
            "gl_aggregate": f"${val['gl_aggregate']:,}",
            "umbrella_required": val.get("umbrella_required", False),
            "umbrella_minimum": f"${val.get('umbrella_minimum', 0):,}" if val.get('umbrella_minimum', 0) > 0 else None,
        }
        for key, val in PROJECT_TYPE_REQUIREMENTS.items()
    }

@app.get("/api/states")
async def get_states():
    """Get list of all states with summary of their insurance rules"""
    states = []
    for state_code in sorted(STATE_WORKERS_COMP.keys()):
        wc = STATE_WORKERS_COMP.get(state_code, {})
        ai = STATE_ANTI_INDEMNITY.get(state_code, {})
        gl = STATE_GL_REQUIREMENTS.get(state_code, {})

        states.append({
            "code": state_code,
            "wc_required": wc.get('required', True),
            "wc_threshold": wc.get('threshold'),
            "monopolistic_wc": wc.get('monopolistic', False),
            "anti_indemnity_type": ai.get('type', 'Unknown'),
            "voids_ai_coverage": ai.get('voids_ai_for_sole_negligence', False),
            "gl_required_for_license": gl.get('required_for_license', False),
            "risk_level": "HIGH" if ai.get('voids_ai_for_sole_negligence') else ("MEDIUM" if ai.get('type') not in ['None', None] else "LOW")
        })
    return states

@app.get("/api/state/{state_code}")
async def get_state_details(state_code: str):
    """Get detailed insurance requirements for a specific state"""
    state_upper = state_code.upper()

    if state_upper not in STATE_WORKERS_COMP:
        raise HTTPException(status_code=404, detail=f"State {state_upper} not found")

    wc = STATE_WORKERS_COMP.get(state_upper, {})
    ai = STATE_ANTI_INDEMNITY.get(state_upper, {})
    gl = STATE_GL_REQUIREMENTS.get(state_upper, {})
    auto = STATE_AUTO_MINIMUMS.get(state_upper, {})

    return {
        "state": state_upper,
        "workers_comp": {
            "required": wc.get('required', True),
            "threshold": wc.get('threshold'),
            "construction_specific": wc.get('construction_specific'),
            "monopolistic": wc.get('monopolistic', False),
            "notes": "Must purchase through state fund" if wc.get('monopolistic') else ("Voluntary state" if not wc.get('required') else "Standard private market")
        },
        "anti_indemnity": {
            "type": ai.get('type', 'Unknown'),
            "voids_ai_for_negligence": ai.get('voids_ai_for_sole_negligence', False),
            "insurance_savings_clause": ai.get('insurance_savings_clause', True),
            "notes": ai.get('notes', ''),
            "risk_level": "CRITICAL" if ai.get('voids_ai_for_sole_negligence') else "STANDARD"
        },
        "general_liability": {
            "required_for_license": gl.get('required_for_license', False),
            "minimum_per_occurrence": f"${gl.get('minimum_per_occurrence'):,}" if gl.get('minimum_per_occurrence') else None,
            "notes": gl.get('notes', '')
        },
        "auto_liability": {
            "bodily_injury_per_person": f"${auto.get('bodily_injury_per_person', 25000):,}",
            "bodily_injury_per_accident": f"${auto.get('bodily_injury_per_accident', 50000):,}",
            "property_damage": f"${auto.get('property_damage', 25000):,}",
            "combined_format": f"{auto.get('bodily_injury_per_person', 25000)//1000}/{auto.get('bodily_injury_per_accident', 50000)//1000}/{auto.get('property_damage', 25000)//1000}"
        }
    }

@app.get("/api/ai-limited-states")
async def get_ai_limited_states():
    """Get states with broad anti-indemnity statutes that limit AI coverage"""
    mitigations = {
        "AZ": ["CG 24 26 endorsement (excludes your negligence from AI)", "Higher primary limits on your own CGL"],
        "CO": ["Wrap-up/OCIP for larger projects", "Contractual liability coverage on your policy", "Explicit fault allocation in subcontracts"],
        "GA": ["Primary & non-contributory language still valid", "Ensure your own CGL has adequate limits"],
        "KS": ["Wrap-up programs", "Higher umbrella limits on your policy"],
        "MT": ["OCIP/CCIP wrap-up insurance", "Project-specific coverage", "Your own policy must be primary"],
        "OR": ["CG 24 26 amendment endorsement", "Contractual liability on your CGL"],
    }

    states = []
    for state_code, ai_rules in STATE_ANTI_INDEMNITY.items():
        if ai_rules.get('voids_ai_for_sole_negligence'):
            states.append({
                "state": state_code,
                "statute_type": ai_rules.get('type'),
                "mitigation_options": mitigations.get(state_code, []),
                "insurance_savings_clause": ai_rules.get('insurance_savings_clause', False)
            })
    return {
        "states": states,
        "count": len(states),
        "note": "These states have broad anti-indemnity statutes. AI coverage may be limited when you share fault. See mitigation options for each state."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
