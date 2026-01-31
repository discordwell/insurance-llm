from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI
import json
import os
import re
import base64
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from contextlib import asynccontextmanager

# Database imports
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load .env file
load_dotenv()

# Database setup - uses DATABASE_URL env var (set in Railway)
DATABASE_URL = os.environ.get("DATABASE_URL")
db_engine = None
SessionLocal = None
Base = declarative_base()

# Database models
class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    document_type = Column(String(50), index=True)  # coi, lease, gym, etc.
    document_text = Column(Text)
    text_length = Column(Integer)
    state = Column(String(10), nullable=True)  # User-selected state
    analysis_result = Column(JSON, nullable=True)  # Full analysis response
    overall_risk = Column(String(20), nullable=True)  # high/medium/low
    risk_score = Column(Integer, nullable=True)
    red_flag_count = Column(Integer, nullable=True)
    # Metadata
    source = Column(String(50), default="web")  # web, api, etc.
    user_agent = Column(String(500), nullable=True)

class Waitlist(Base):
    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    email = Column(String(255), index=True)
    document_type = Column(String(100))  # What they uploaded
    document_text_preview = Column(Text, nullable=True)  # First 500 chars
    notified = Column(Boolean, default=False)
    notified_at = Column(DateTime, nullable=True)

def init_db():
    """Initialize database connection and create tables"""
    global db_engine, SessionLocal
    if DATABASE_URL:
        # Railway uses postgres:// but SQLAlchemy needs postgresql://
        db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        db_engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        Base.metadata.create_all(bind=db_engine)
        print("Database initialized successfully")
        return True
    else:
        print("DATABASE_URL not set - running without database storage")
        return False

def get_db():
    """Get database session"""
    if SessionLocal is None:
        return None
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        raise

def save_upload(doc_type: str, text: str, state: str = None, analysis: dict = None, user_agent: str = None):
    """Save an upload to the database"""
    db = get_db()
    if db is None:
        return None  # No database configured

    try:
        upload = Upload(
            document_type=doc_type,
            document_text=text,
            text_length=len(text),
            state=state,
            analysis_result=analysis,
            overall_risk=analysis.get("overall_risk") if analysis else None,
            risk_score=analysis.get("risk_score") if analysis else None,
            red_flag_count=len(analysis.get("red_flags", [])) if analysis else None,
            user_agent=user_agent
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        return upload.id
    except Exception as e:
        print(f"Error saving upload: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def save_waitlist(email: str, doc_type: str, text_preview: str = None):
    """Save a waitlist signup"""
    db = get_db()
    if db is None:
        return None

    try:
        entry = Waitlist(
            email=email,
            document_type=doc_type,
            document_text_preview=text_preview[:500] if text_preview else None
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry.id
    except Exception as e:
        print(f"Error saving waitlist: {e}")
        db.rollback()
        return None
    finally:
        db.close()

# Initialize database on startup
init_db()

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

# Confidence level for extracted fields
class FieldConfidence(BaseModel):
    """Confidence information for an extracted field"""
    level: str  # "high", "medium", "low"
    reason: Optional[str] = None  # Why this confidence level
    source_quote: Optional[str] = None  # Direct quote from document supporting this extraction


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

    # Confidence scores for critical fields
    confidence: Optional[dict[str, FieldConfidence]] = None


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process"""
    overall_confidence: float  # 0-1 score
    needs_human_review: bool  # True if confidence is low or critical fields are uncertain
    review_reasons: list[str] = []  # Why human review is recommended
    low_confidence_fields: list[str] = []  # Fields with low confidence
    extraction_notes: Optional[str] = None  # Any notes from extraction process

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

    # Extraction confidence metadata
    extraction_metadata: Optional[ExtractionMetadata] = None

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


class OCRInput(BaseModel):
    file_data: str  # base64 encoded file
    file_type: str  # MIME type (application/pdf, image/png, etc.)
    file_name: str


class ClassifyInput(BaseModel):
    text: str


class ClassifyResult(BaseModel):
    document_type: str  # "coi", "lease", "insurance_policy", "contract", "unknown"
    confidence: float  # 0-1
    description: str  # Human-readable description
    supported: bool  # Whether we can analyze this type


# Supported document types
SUPPORTED_DOC_TYPES = {
    "coi": {
        "name": "Certificate of Insurance",
        "description": "ACORD 25 or similar certificate of insurance",
        "supported": True
    },
    "lease": {
        "name": "Property Lease",
        "description": "Commercial or residential lease agreement",
        "supported": True
    },
    "gym_contract": {
        "name": "Gym/Fitness Membership",
        "description": "Gym or fitness center membership agreement",
        "supported": True
    },
    "employment_contract": {
        "name": "Employment Contract",
        "description": "Employment agreement, offer letter, or employee handbook",
        "supported": True
    },
    "freelancer_contract": {
        "name": "Freelancer Agreement",
        "description": "Independent contractor, freelance, or consulting agreement",
        "supported": True
    },
    "influencer_contract": {
        "name": "Influencer/Sponsorship",
        "description": "Brand deal, sponsorship, or content creator agreement",
        "supported": True
    },
    "insurance_policy": {
        "name": "Insurance Policy",
        "description": "Full insurance policy document",
        "supported": True
    },
    "timeshare_contract": {
        "name": "Timeshare Contract",
        "description": "Timeshare or vacation ownership agreement",
        "supported": True
    },
    "contract": {
        "name": "Contract",
        "description": "General contract or agreement",
        "supported": False
    },
    "unknown": {
        "name": "Unknown Document",
        "description": "Could not identify document type",
        "supported": False
    }
}


# ============== LEASE ANALYSIS MODELS ==============

class LeaseInsuranceClause(BaseModel):
    clause_type: str  # e.g., "liability_requirement", "additional_insured", "waiver_of_subrogation"
    original_text: str  # The actual clause text from the lease
    summary: str  # Plain English summary
    risk_level: str  # "high", "medium", "low"
    explanation: str  # Why this matters
    recommendation: str  # What to do about it


class LeaseRedFlag(BaseModel):
    name: str
    severity: str  # "critical", "warning", "info"
    clause_text: Optional[str]  # The problematic clause if found
    explanation: str
    protection: str  # How to protect yourself


class LeaseAnalysisInput(BaseModel):
    lease_text: str
    state: Optional[str] = None
    lease_type: Optional[str] = "commercial"  # "commercial" or "residential"


class LeaseAnalysisReport(BaseModel):
    overall_risk: str  # "high", "medium", "low"
    risk_score: int  # 0-100 (100 = very risky for tenant)
    lease_type: str
    landlord_name: Optional[str]
    tenant_name: Optional[str]
    property_address: Optional[str]
    lease_term: Optional[str]

    # Insurance requirements found
    insurance_requirements: list[LeaseInsuranceClause]

    # Red flags found
    red_flags: list[LeaseRedFlag]

    # What's missing that should be there
    missing_protections: list[str]

    # Summary
    summary: str

    # Negotiation letter
    negotiation_letter: str


# Lease insurance red flags to check
LEASE_RED_FLAGS = {
    "blanket_indemnification": {
        "name": "Blanket Indemnification",
        "keywords": ["indemnify", "hold harmless", "defend"],
        "bad_pattern": "all claims",  # Without negligence carve-out
        "severity": "critical",
        "explanation": "You may be agreeing to pay for the landlord's mistakes, not just your own.",
        "protection": "Add 'except to the extent caused by landlord's negligence or willful misconduct'"
    },
    "landlord_not_liable": {
        "name": "Landlord Not Liable Clause",
        "keywords": ["landlord shall not be liable", "not responsible for", "waives all claims"],
        "severity": "critical",
        "explanation": "Landlord is trying to eliminate liability even for their own negligence.",
        "protection": "Add 'except for landlord's negligence or willful misconduct'"
    },
    "insurance_proceeds_to_landlord": {
        "name": "Insurance Proceeds to Landlord",
        "keywords": ["insurance proceeds", "paid to landlord", "payable to lessor"],
        "severity": "critical",
        "explanation": "Your insurance payout for your improvements could go to the landlord instead of you.",
        "protection": "Ensure your improvements coverage pays you directly"
    },
    "no_tenant_termination": {
        "name": "No Tenant Termination Right",
        "keywords": ["landlord may terminate", "tenant shall have no right"],
        "severity": "critical",
        "explanation": "If there's major damage, landlord can walk away but you're stuck waiting or paying rent.",
        "protection": "Negotiate mutual termination rights or tenant termination if repairs exceed 90-180 days"
    },
    "additional_insured_requirement": {
        "name": "Additional Insured Requirement",
        "keywords": ["additional insured", "named insured"],
        "severity": "warning",
        "explanation": "Landlord will share YOUR policy limits. If they use $500K defending themselves, you only have $500K left.",
        "protection": "Increase liability limits to account for sharing. Negotiate to exclude landlord's sole negligence."
    },
    "primary_noncontributory": {
        "name": "Primary and Non-Contributory",
        "keywords": ["primary and non-contributory", "primary basis", "non-contributory"],
        "severity": "warning",
        "explanation": "Your policy pays first even if the landlord was at fault. Very landlord-favorable.",
        "protection": "Resist this language or significantly increase your limits"
    },
    "waiver_of_subrogation": {
        "name": "Waiver of Subrogation",
        "keywords": ["waiver of subrogation", "waive subrogation", "waiver of recovery"],
        "severity": "warning",
        "explanation": "If landlord's negligence damages your property, your insurer can't sue them to recover. You eat the deductibles and gaps.",
        "protection": "Ensure it's mutual. Get the endorsement on your policy. Negotiate carve-outs for gross negligence."
    },
    "self_insurance_requirement": {
        "name": "Self-Insurance/High Deductible",
        "keywords": ["self-insure", "first $", "deductible of"],
        "severity": "warning",
        "explanation": "This is a hidden cost - every claim will cost you this amount out of pocket.",
        "protection": "Negotiate down or eliminate. Budget for it if unavoidable."
    },
    "coverage_lapse_default": {
        "name": "Coverage Lapse = Default",
        "keywords": ["lapse in coverage", "failure to maintain", "immediate default"],
        "severity": "warning",
        "explanation": "A paperwork error by your insurer could get you evicted.",
        "protection": "Negotiate a 30-day cure period. Set up automatic payments."
    },
    "landlord_can_purchase_insurance": {
        "name": "Landlord Can Buy and Charge Back",
        "keywords": ["landlord may purchase", "charge to tenant", "additional rent"],
        "severity": "warning",
        "explanation": "Landlord buys overpriced coverage and bills you at a markup as 'rent'.",
        "protection": "Negotiate right to cure before landlord can purchase. Cap chargebacks at market rates."
    },
    "care_custody_control_gap": {
        "name": "Care, Custody & Control Gap",
        "keywords": ["damage to premises", "damage to building", "tenant responsible for"],
        "severity": "warning",
        "explanation": "Your GL policy excludes damage to property you rent. You could be personally liable for building damage.",
        "protection": "Add 'Damage to Premises Rented to You' coverage (Fire Legal Liability) with adequate limits."
    },
    "betterments_ownership": {
        "name": "Improvements Become Landlord's Property",
        "keywords": ["improvements shall become", "property of landlord", "tenant improvements"],
        "severity": "warning",
        "explanation": "Your $300K build-out becomes theirs - and they may not insure it.",
        "protection": "Get Betterments & Improvements coverage at replacement cost. Clarify who insures what in writing."
    },
    "unlimited_repair_timeline": {
        "name": "No Repair Deadline",
        "keywords": ["reasonable time", "diligent efforts", "as soon as practicable"],
        "severity": "warning",
        "explanation": "Landlord has no urgency to repair - especially if they're collecting loss-of-rents insurance.",
        "protection": "Negotiate hard deadlines (90-180 days max) with termination rights if not met."
    },
    "no_rent_abatement": {
        "name": "No Rent Abatement",
        "keywords": ["rent shall continue", "no abatement", "rent not reduced"],
        "severity": "critical",
        "explanation": "You keep paying rent even when you can't use the space due to damage.",
        "protection": "Negotiate rent abatement during any period the premises are unusable."
    },
    "extraordinary_coverage": {
        "name": "Unusual Coverage Requirements",
        "keywords": ["terrorism", "pollution", "cyber", "earthquake", "flood"],
        "severity": "info",
        "explanation": "Some of these coverages may be expensive, unavailable, or inapplicable to your business.",
        "protection": "Only agree to coverage that's available, affordable, and applicable. Add 'if commercially available at reasonable cost'."
    }
}

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

CONFIDENCE SCORING - For each critical field, provide a confidence assessment:
- confidence: An object with field names as keys, each containing:
  - level: "high" (clearly visible/readable), "medium" (present but ambiguous), or "low" (inferred or uncertain)
  - reason: Brief explanation of confidence level
  - source_quote: Direct quote from document (max 50 chars) if available, null if not found

Provide confidence for these critical fields:
- gl_limit_per_occurrence
- gl_limit_aggregate
- additional_insured_checked
- waiver_of_subrogation_checked
- cg_20_10_endorsement
- cg_20_37_endorsement

IMPORTANT: Being listed as "Certificate Holder" does NOT make someone an Additional Insured. These are separate concepts.

If a field isn't clearly present, use null for strings or false for booleans. When uncertain, mark confidence as "low".

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

# Waitlist signup model
class WaitlistInput(BaseModel):
    email: str
    document_type: str
    document_text: Optional[str] = None

class WaitlistResponse(BaseModel):
    success: bool
    message: str

@app.post("/api/waitlist", response_model=WaitlistResponse)
async def add_to_waitlist(input: WaitlistInput):
    """Add someone to the waitlist for unsupported document types"""
    # Validate email format (basic)
    if not input.email or '@' not in input.email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    # Save to database
    entry_id = save_waitlist(
        email=input.email,
        doc_type=input.document_type,
        text_preview=input.document_text
    )

    if entry_id:
        return WaitlistResponse(
            success=True,
            message=f"Added to waitlist for {input.document_type}"
        )
    else:
        # Still return success even if DB not configured (graceful degradation)
        return WaitlistResponse(
            success=True,
            message="Thanks! We'll notify you when we support this document type."
        )

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

    # Generate mock extraction metadata
    extraction_metadata = {
        "overall_confidence": 0.75,
        "needs_human_review": len(critical_gaps) > 0 or not coi_data.get('additional_insured_checked'),
        "review_reasons": [
            "Mock extraction - recommend verification with actual document"
        ] + ([f"Critical gap: {gap['name']}" for gap in critical_gaps[:2]]),
        "low_confidence_fields": ["cg_20_10_endorsement", "cg_20_37_endorsement"] if not coi_data.get('cg_20_10_endorsement') else [],
        "extraction_notes": "Mock extraction for testing purposes"
    }

    return {
        "overall_status": overall_status,
        "coi_data": coi_data,
        "critical_gaps": critical_gaps,
        "warnings": warnings,
        "passed": passed,
        "risk_exposure": risk_exposure,
        "fix_request_letter": fix_letter,
        "extraction_metadata": extraction_metadata
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
            # Save upload
            save_upload("coi", input.coi_text, input.state, result)
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

        # Calculate extraction confidence metadata
        extraction_metadata = calculate_extraction_confidence(coi_data)
        result['extraction_metadata'] = extraction_metadata

        # Save upload
        save_upload("coi", input.coi_text, input.state, result)

        return ComplianceReport(**result)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def calculate_extraction_confidence(coi_data: dict) -> dict:
    """Calculate overall extraction confidence and determine if human review is needed"""
    confidence_data = coi_data.get('confidence', {})

    # Critical fields that need confidence assessment
    critical_fields = [
        'gl_limit_per_occurrence',
        'gl_limit_aggregate',
        'additional_insured_checked',
        'waiver_of_subrogation_checked',
        'cg_20_10_endorsement',
        'cg_20_37_endorsement'
    ]

    # Calculate confidence scores
    confidence_scores = []
    low_confidence_fields = []
    review_reasons = []

    for field in critical_fields:
        field_conf = confidence_data.get(field, {})
        level = field_conf.get('level', 'low') if isinstance(field_conf, dict) else 'low'

        if level == 'high':
            confidence_scores.append(1.0)
        elif level == 'medium':
            confidence_scores.append(0.7)
        else:  # low
            confidence_scores.append(0.3)
            low_confidence_fields.append(field)
            reason = field_conf.get('reason', 'Not clearly visible in document') if isinstance(field_conf, dict) else 'No confidence data'
            review_reasons.append(f"{field}: {reason}")

    # Calculate overall confidence
    overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5

    # Determine if human review is needed
    # Threshold: 0.8 (80% confidence) - based on research recommendations
    needs_human_review = overall_confidence < 0.8 or len(low_confidence_fields) > 0

    # Add additional review reasons
    if not coi_data.get('additional_insured_checked'):
        review_reasons.append("Additional Insured not checked - verify this is intentional")
    if not coi_data.get('cg_20_10_endorsement') and not coi_data.get('cg_20_37_endorsement'):
        review_reasons.append("No CG endorsements found - may indicate incomplete coverage")

    return {
        "overall_confidence": round(overall_confidence, 2),
        "needs_human_review": needs_human_review,
        "review_reasons": review_reasons[:5],  # Limit to top 5 reasons
        "low_confidence_fields": low_confidence_fields,
        "extraction_notes": f"Analyzed {len(critical_fields)} critical fields. {len(low_confidence_fields)} have low confidence."
    }

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


CLASSIFY_PROMPT = """Classify this document into one of these categories:
- "coi" = Certificate of Insurance (ACORD 25 form, insurance certificate, proof of coverage)
- "lease" = Property Lease (rental agreement, commercial lease, residential lease)
- "gym_contract" = Gym/Fitness Membership (gym membership, fitness center contract, health club agreement)
- "employment_contract" = Employment Contract (offer letter, employment agreement, employee handbook with arbitration/non-compete)
- "freelancer_contract" = Freelancer/Contractor Agreement (independent contractor, consulting, freelance, SOW)
- "influencer_contract" = Influencer/Sponsorship (brand deal, sponsorship, content creator agreement, influencer contract)
- "insurance_policy" = Full Insurance Policy (declarations page, policy document, coverage details)
- "timeshare_contract" = Timeshare Contract (vacation ownership, timeshare purchase, resort membership)
- "contract" = Other Contract (service agreement, vendor contract, NDA, etc.)
- "unknown" = Cannot determine

Look for key indicators:
- COI: "CERTIFICATE OF LIABILITY INSURANCE", "ACORD", "CERTIFICATE HOLDER", "ADDITIONAL INSURED"
- Lease: "LEASE AGREEMENT", "LANDLORD", "TENANT", "RENT", "PREMISES", "TERM"
- Gym: "MEMBERSHIP", "FITNESS", "GYM", "HEALTH CLUB", "CANCEL", "DUES", "MONTHLY FEE"
- Employment: "EMPLOYMENT", "EMPLOYEE", "NON-COMPETE", "ARBITRATION", "AT-WILL", "TERMINATION", "SALARY"
- Freelancer: "INDEPENDENT CONTRACTOR", "FREELANCE", "CONSULTING", "DELIVERABLES", "SOW", "WORK FOR HIRE"
- Influencer: "BRAND", "SPONSOR", "INFLUENCER", "CONTENT", "DELIVERABLES", "USAGE RIGHTS", "EXCLUSIVITY", "CAMPAIGN"
- Insurance Policy: "DECLARATIONS", "POLICY NUMBER", "COVERAGE", "PREMIUM", "ENDORSEMENT"
- Timeshare: "TIMESHARE", "VACATION OWNERSHIP", "RESORT", "INTERVAL", "MAINTENANCE FEE", "DEEDED", "RIGHT TO USE"
- Contract: "AGREEMENT", "PARTIES", "TERMS AND CONDITIONS", "WHEREAS"

Return JSON only:
{"type": "coi|lease|insurance_policy|contract|unknown", "confidence": 0.0-1.0, "reason": "brief explanation"}"""

OCR_PROMPT = """Extract ALL text from this document image. This is likely an insurance document, certificate of insurance (COI), policy, lease, or contract.

Return the text exactly as it appears, preserving:
- Line breaks and formatting
- Checkbox status (show as [X] for checked, [ ] for unchecked)
- Tables and columns (use spacing to preserve alignment)
- Headers and section titles
- All numbers, dates, and dollar amounts exactly as written

Do not summarize or interpret - just extract the raw text content."""


@app.post("/api/ocr")
async def ocr_document(input: OCRInput):
    """Extract text from PDF or image using OpenAI Vision API"""
    try:
        # Mock mode - return placeholder text
        if MOCK_MODE:
            return {
                "text": f"[Mock OCR result for {input.file_name}]\n\nSample extracted text would appear here.\nUpload a real document with OPENAI_API_KEY configured."
            }

        client = get_client()

        # Decode base64 file data
        import base64
        file_bytes = base64.b64decode(input.file_data)

        # Handle PDFs by converting to images first
        if input.file_type == 'application/pdf':
            import fitz  # PyMuPDF
            import io

            # Open PDF from bytes
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")

            all_text = []
            # Process each page (limit to first 5 pages for performance)
            for page_num in range(min(len(pdf_doc), 5)):
                page = pdf_doc[page_num]
                # Render page to image at 150 DPI for good quality
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                # Create data URL for image
                data_url = f"data:image/png;base64,{img_base64}"

                # Call Vision API for this page
                response = client.chat.completions.create(
                    model="gpt-5.2",
                    max_completion_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": OCR_PROMPT
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": data_url
                                    }
                                }
                            ]
                        }
                    ]
                )

                page_text = response.choices[0].message.content
                if len(pdf_doc) > 1:
                    all_text.append(f"--- Page {page_num + 1} ---\n{page_text}")
                else:
                    all_text.append(page_text)

            pdf_doc.close()
            return {"text": "\n\n".join(all_text)}

        # Handle images directly
        elif input.file_type.startswith('image/'):
            media_type = input.file_type
            data_url = f"data:{media_type};base64,{input.file_data}"

            response = client.chat.completions.create(
                model="gpt-5.2",
                max_completion_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": OCR_PROMPT
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url
                                }
                            }
                        ]
                    }
                ]
            )

            return {"text": response.choices[0].message.content}

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {input.file_type}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")


@app.post("/api/classify", response_model=ClassifyResult)
async def classify_document(input: ClassifyInput):
    """Classify document type using cheap/fast model"""
    try:
        # Mock mode
        if MOCK_MODE:
            text_lower = input.text.lower()
            if 'certificate' in text_lower and ('insurance' in text_lower or 'liability' in text_lower):
                doc_type = "coi"
            elif 'lease' in text_lower or ('landlord' in text_lower and 'tenant' in text_lower):
                doc_type = "lease"
            elif 'gym' in text_lower or 'fitness' in text_lower or ('membership' in text_lower and ('cancel' in text_lower or 'dues' in text_lower)):
                doc_type = "gym_contract"
            elif 'timeshare' in text_lower or 'vacation ownership' in text_lower or ('resort' in text_lower and 'maintenance fee' in text_lower):
                doc_type = "timeshare_contract"
            elif 'influencer' in text_lower or 'brand deal' in text_lower or ('content' in text_lower and 'usage rights' in text_lower) or 'sponsorship' in text_lower:
                doc_type = "influencer_contract"
            elif 'independent contractor' in text_lower or 'freelance' in text_lower or ('contractor' in text_lower and 'deliverables' in text_lower):
                doc_type = "freelancer_contract"
            elif 'employment' in text_lower or 'non-compete' in text_lower or ('employee' in text_lower and ('arbitration' in text_lower or 'at-will' in text_lower)):
                doc_type = "employment_contract"
            elif 'policy' in text_lower and 'premium' in text_lower:
                doc_type = "insurance_policy"
            elif 'agreement' in text_lower or 'contract' in text_lower:
                doc_type = "contract"
            else:
                doc_type = "unknown"

            doc_info = SUPPORTED_DOC_TYPES[doc_type]
            return ClassifyResult(
                document_type=doc_type,
                confidence=0.85,
                description=doc_info["name"],
                supported=doc_info["supported"]
            )

        client = get_client()

        # Use cheap model for classification - just need first ~2000 chars
        sample_text = input.text[:2000]

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cheap and fast
            max_completion_tokens=150,
            messages=[
                {"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": f"Classify this document:\n\n{sample_text}"}
            ]
        )

        response_text = response.choices[0].message.content.strip()

        # Parse JSON response
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        result = json.loads(response_text)
        doc_type = result.get("type", "unknown")

        # Validate doc_type
        if doc_type not in SUPPORTED_DOC_TYPES:
            doc_type = "unknown"

        doc_info = SUPPORTED_DOC_TYPES[doc_type]

        return ClassifyResult(
            document_type=doc_type,
            confidence=result.get("confidence", 0.5),
            description=doc_info["name"],
            supported=doc_info["supported"]
        )

    except json.JSONDecodeError:
        return ClassifyResult(
            document_type="unknown",
            confidence=0.0,
            description="Could not classify document",
            supported=False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


# ============== LEASE ANALYSIS ==============

LEASE_EXTRACTION_PROMPT = """You are an expert lease analyst specializing in insurance and liability provisions.

Extract the following from this lease document:

1. BASIC INFO:
- landlord_name: Name of landlord/lessor
- tenant_name: Name of tenant/lessee
- property_address: Property address
- lease_term: Lease duration (e.g., "3 years", "Month-to-month")
- lease_type: "commercial" or "residential"

2. INSURANCE CLAUSES: Find ALL clauses related to:
- Required insurance types and limits (GL, property, umbrella, etc.)
- Additional insured requirements
- Waiver of subrogation
- Indemnification/hold harmless provisions
- Who insures what (building vs contents vs improvements)
- Insurance proceeds allocation
- Liability waivers or limitations
- Casualty/damage provisions
- Rent abatement provisions
- Repair/restoration obligations

For each insurance clause found, extract:
- clause_type: Category (e.g., "gl_requirement", "additional_insured", "waiver_of_subrogation", "indemnification", "casualty", "rent_abatement")
- original_text: The exact text from the lease (keep it reasonably short, just the key language)
- summary: Plain English explanation

Return JSON:
{
  "landlord_name": "...",
  "tenant_name": "...",
  "property_address": "...",
  "lease_term": "...",
  "lease_type": "commercial" or "residential",
  "insurance_clauses": [
    {
      "clause_type": "...",
      "original_text": "...",
      "summary": "..."
    }
  ]
}

LEASE DOCUMENT:
<<DOCUMENT>>

Return ONLY valid JSON, no markdown."""

LEASE_ANALYSIS_PROMPT = """You are an expert insurance and real estate attorney helping a TENANT understand the risks in their lease.

Your job is to identify provisions that could "fuck" the tenant - clauses that expose them to unexpected liability, costs, or coverage gaps.

EXTRACTED LEASE DATA:
<<LEASE_DATA>>

RED FLAG DEFINITIONS:
<<RED_FLAGS>>

STATE: <<STATE>>

Analyze each insurance clause and the lease overall. Return JSON:

{
  "overall_risk": "high" | "medium" | "low",
  "risk_score": 0-100 (100 = extremely risky for tenant),
  "red_flags": [
    {
      "name": "Name of the issue",
      "severity": "critical" | "warning" | "info",
      "clause_text": "The problematic text if found",
      "explanation": "Why this fucks the tenant (be direct, use plain language)",
      "protection": "What to negotiate or do about it"
    }
  ],
  "insurance_requirements": [
    {
      "clause_type": "Type of requirement",
      "original_text": "The clause text",
      "summary": "Plain English summary",
      "risk_level": "high" | "medium" | "low",
      "explanation": "Why this matters to the tenant",
      "recommendation": "What to do"
    }
  ],
  "missing_protections": [
    "Things that SHOULD be in the lease but aren't (like rent abatement, repair deadlines, termination rights)"
  ],
  "summary": "2-3 sentence summary of the biggest risks in this lease",
  "negotiation_letter": "A professional but firm letter the tenant can send to the landlord requesting changes. Be specific about which clauses need modification and what the changes should be. Include the most critical items first."
}

Be direct and practical. Use phrases like "This could cost you..." and "You're agreeing to...".
The tenant needs to understand the REAL risks, not legal jargon.

Return ONLY valid JSON, no markdown."""


def mock_lease_analysis(lease_text: str, state: str = None) -> dict:
    """Generate mock lease analysis for testing"""
    text_lower = lease_text.lower()

    red_flags = []
    insurance_requirements = []
    risk_score = 50

    # Check for common red flags
    if 'indemnify' in text_lower and 'hold harmless' in text_lower:
        if 'negligence' not in text_lower or 'except' not in text_lower:
            red_flags.append({
                "name": "Blanket Indemnification",
                "severity": "critical",
                "clause_text": "Tenant shall indemnify and hold harmless Landlord from any and all claims...",
                "explanation": "You're agreeing to pay for the landlord's mistakes, not just your own. If someone slips on ice the landlord should have salted, you could be on the hook.",
                "protection": "Add: 'except to the extent caused by Landlord's negligence or willful misconduct'"
            })
            risk_score += 20

    if 'additional insured' in text_lower:
        red_flags.append({
            "name": "Additional Insured Requirement",
            "severity": "warning",
            "clause_text": "Tenant shall name Landlord as Additional Insured on all liability policies...",
            "explanation": "The landlord gets to use YOUR insurance policy limits. If they use $500K defending a lawsuit, you only have $500K left for your own claims.",
            "protection": "Increase your liability limits. Negotiate to exclude coverage for landlord's sole negligence."
        })
        insurance_requirements.append({
            "clause_type": "additional_insured",
            "original_text": "Landlord shall be named as Additional Insured",
            "summary": "You must add the landlord to your insurance policy",
            "risk_level": "medium",
            "explanation": "Landlord shares your policy limits",
            "recommendation": "Increase liability limits to $2M+ to account for sharing"
        })
        risk_score += 10

    if 'waiver of subrogation' in text_lower or 'waive subrogation' in text_lower:
        red_flags.append({
            "name": "Waiver of Subrogation",
            "severity": "warning",
            "clause_text": "Tenant waives all rights of subrogation against Landlord...",
            "explanation": "If the landlord's negligence causes a fire that destroys your business, your insurance pays you but CAN'T sue the landlord to recover. You eat the deductibles and coverage gaps.",
            "protection": "Make sure it's mutual. Get the endorsement on your policy. Negotiate carve-outs for gross negligence."
        })
        risk_score += 10

    if 'primary and non-contributory' in text_lower:
        red_flags.append({
            "name": "Primary and Non-Contributory",
            "severity": "warning",
            "clause_text": "Tenant's insurance shall be primary and non-contributory...",
            "explanation": "Your insurance pays FIRST, even if it's the landlord's fault. Their insurance sits back and watches yours get depleted.",
            "protection": "Resist this language if possible. If required, significantly increase your limits."
        })
        risk_score += 15

    if 'not be liable' in text_lower or 'not responsible' in text_lower:
        red_flags.append({
            "name": "Landlord Not Liable",
            "severity": "critical",
            "clause_text": "Landlord shall not be liable for any damage to Tenant's property...",
            "explanation": "The landlord is trying to avoid ALL liability, even for their own negligence. This may not be enforceable, but you'll have to fight it in court.",
            "protection": "Add: 'except for damage caused by Landlord's negligence or willful misconduct'"
        })
        risk_score += 15

    # Check for missing protections
    missing = []
    if 'abatement' not in text_lower and 'abate' not in text_lower:
        missing.append("Rent abatement during periods when premises are unusable")
        risk_score += 10

    if 'terminate' not in text_lower or ('landlord may terminate' in text_lower and 'tenant may terminate' not in text_lower):
        missing.append("Tenant termination right if repairs take too long")
        risk_score += 10

    # Add some basic insurance requirements if found
    if '$1,000,000' in lease_text or '$1M' in text_lower:
        insurance_requirements.append({
            "clause_type": "gl_requirement",
            "original_text": "Commercial General Liability: $1,000,000 per occurrence",
            "summary": "You need at least $1M in general liability coverage",
            "risk_level": "low",
            "explanation": "This is a standard commercial requirement",
            "recommendation": "Make sure your policy meets or exceeds this limit"
        })

    if '$2,000,000' in lease_text or '$2M' in text_lower:
        insurance_requirements.append({
            "clause_type": "gl_aggregate",
            "original_text": "General Aggregate: $2,000,000",
            "summary": "Your policy needs $2M aggregate limit",
            "risk_level": "low",
            "explanation": "Standard aggregate for commercial leases",
            "recommendation": "Verify your policy's aggregate limit"
        })

    # Cap risk score
    risk_score = min(100, risk_score)

    # Determine overall risk
    if risk_score >= 70:
        overall_risk = "high"
    elif risk_score >= 40:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    warning_count = len([r for r in red_flags if r['severity'] == 'warning'])

    if critical_count > 0:
        summary = f"This lease has {critical_count} critical issues that could expose you to significant liability. "
    else:
        summary = "This lease has some concerning provisions but no critical red flags. "

    if missing:
        summary += f"It's also missing {len(missing)} standard tenant protections."

    # Generate negotiation letter
    letter_items = []
    for rf in red_flags:
        if rf['severity'] == 'critical':
            letter_items.append(f"- {rf['name']}: {rf['protection']}")

    for missing_item in missing[:3]:
        letter_items.append(f"- Add: {missing_item}")

    letter = f"""RE: Lease Insurance and Liability Terms - Requested Modifications

Dear Landlord,

We have reviewed the proposed lease agreement and identified several provisions that require modification before we can proceed:

REQUESTED CHANGES:
{chr(10).join(letter_items) if letter_items else '- No critical changes required'}

These modifications reflect standard commercial practice and appropriate risk allocation between landlord and tenant. We believe these changes are reasonable and look forward to discussing them.

Please provide a revised lease addressing these items within 10 business days.

Best regards,
[Tenant Name]
"""

    return {
        "overall_risk": overall_risk,
        "risk_score": risk_score,
        "lease_type": "commercial" if 'commercial' in text_lower else "residential",
        "landlord_name": None,
        "tenant_name": None,
        "property_address": None,
        "lease_term": None,
        "insurance_requirements": insurance_requirements,
        "red_flags": red_flags,
        "missing_protections": missing,
        "summary": summary,
        "negotiation_letter": letter
    }


@app.post("/api/analyze-lease", response_model=LeaseAnalysisReport)
async def analyze_lease(input: LeaseAnalysisInput):
    """Analyze a lease for insurance-related red flags and risks"""
    try:
        # Mock mode
        if MOCK_MODE:
            result = mock_lease_analysis(input.lease_text, input.state)
            save_upload("lease", input.lease_text, input.state, result)
            return LeaseAnalysisReport(**result)

        client = get_client()

        # Step 1: Extract lease data
        extract_prompt = LEASE_EXTRACTION_PROMPT.replace("<<DOCUMENT>>", input.lease_text[:15000])  # Limit length

        response = client.chat.completions.create(
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

        lease_data = json.loads(response_text)

        # Step 2: Analyze for red flags
        analysis_prompt = LEASE_ANALYSIS_PROMPT.replace("<<LEASE_DATA>>", json.dumps(lease_data, indent=2))
        analysis_prompt = analysis_prompt.replace("<<RED_FLAGS>>", json.dumps(LEASE_RED_FLAGS, indent=2))
        analysis_prompt = analysis_prompt.replace("<<STATE>>", input.state or "Not specified")

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": analysis_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        analysis = json.loads(response_text)

        # Merge extraction and analysis
        result = {
            "overall_risk": analysis.get("overall_risk", "medium"),
            "risk_score": analysis.get("risk_score", 50),
            "red_flags": analysis.get("red_flags", [])
        }
        save_upload("lease", input.lease_text, input.state, result)

        return LeaseAnalysisReport(
            overall_risk=analysis.get("overall_risk", "medium"),
            risk_score=analysis.get("risk_score", 50),
            lease_type=lease_data.get("lease_type", input.lease_type),
            landlord_name=lease_data.get("landlord_name"),
            tenant_name=lease_data.get("tenant_name"),
            property_address=lease_data.get("property_address"),
            lease_term=lease_data.get("lease_term"),
            insurance_requirements=[LeaseInsuranceClause(**r) for r in analysis.get("insurance_requirements", [])],
            red_flags=[LeaseRedFlag(**r) for r in analysis.get("red_flags", [])],
            missing_protections=analysis.get("missing_protections", []),
            summary=analysis.get("summary", "Analysis complete."),
            negotiation_letter=analysis.get("negotiation_letter", "")
        )

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lease analysis failed: {str(e)}")


# ============== GYM CONTRACT ANALYSIS ==============

class GymRedFlag(BaseModel):
    name: str
    severity: str  # "critical", "warning", "info"
    clause_text: Optional[str]
    explanation: str
    protection: str

class GymContractInput(BaseModel):
    contract_text: str
    state: Optional[str] = None

class GymContractReport(BaseModel):
    overall_risk: str  # "high", "medium", "low"
    risk_score: int
    gym_name: Optional[str]
    contract_type: str  # "month-to-month", "annual", "multi-year"
    monthly_fee: Optional[str]
    cancellation_difficulty: str  # "easy", "moderate", "hard", "nightmare"
    red_flags: list[GymRedFlag]
    state_protections: list[str]
    summary: str
    cancellation_guide: str

# State gym protections
STATE_GYM_PROTECTIONS = {
    "CA": {
        "cooling_off": "5-45 days depending on contract value",
        "relocation_cancel": "25+ miles, max $100 fee",
        "medical_cancel": "With documentation",
        "max_term": "No limit",
        "notes": "Strongest protections in the country"
    },
    "NY": {
        "cooling_off": "3 days",
        "relocation_cancel": "25+ miles",
        "medical_cancel": "With documentation",
        "max_term": "36 months",
        "max_annual": "$3,600/year",
        "notes": "15 days to cancel annual renewal"
    },
    "NJ": {
        "cooling_off": "3 days",
        "relocation_cancel": "25+ miles",
        "medical_cancel": "With documentation",
        "max_term": "3 years",
        "notes": "Strong consumer protections"
    },
    "FL": {
        "cooling_off": "3 business days",
        "medical_cancel": "With documentation",
        "max_term": "3 years",
        "notes": "Excludes weekends and holidays"
    },
    "TX": {
        "cooling_off": "3 business days",
        "notes": "Applies to registered health spas"
    },
    "MA": {
        "cooling_off": "3 business days",
        "relocation_cancel": "25+ miles with pro-rata refund",
        "notes": "No EFT requirement allowed"
    }
}

GYM_RED_FLAGS = {
    "in_person_cancel": {
        "name": "In-Person Cancellation Only",
        "keywords": ["in person", "visit", "home club", "location"],
        "severity": "critical",
        "explanation": "You can only cancel by physically going to the gym. FTC sued LA Fitness for this exact practice in 2025.",
        "protection": "Check if your state requires alternative cancellation methods. Send certified mail anyway and document everything."
    },
    "certified_mail_only": {
        "name": "Certified Mail Required",
        "keywords": ["certified mail", "registered mail", "return receipt"],
        "severity": "warning",
        "explanation": "They're making it deliberately inconvenient to cancel. You have to go to the post office.",
        "protection": "Send certified mail with return receipt. Keep the receipt forever."
    },
    "long_notice_period": {
        "name": "Excessive Notice Period",
        "keywords": ["30 days", "60 days", "prior to billing"],
        "severity": "warning",
        "explanation": "Miss the window by a day and you're locked in for another month or year.",
        "protection": "Set calendar reminders. Document when you sent cancellation notice."
    },
    "auto_renewal": {
        "name": "Automatic Renewal",
        "keywords": ["automatically renew", "auto-renew", "continuous", "successive"],
        "severity": "warning",
        "explanation": "Your contract keeps going unless you actively stop it during a narrow window.",
        "protection": "Set reminder 60 days before renewal. Check your state's renewal notification requirements."
    },
    "annual_fee": {
        "name": "Hidden Annual Fee",
        "keywords": ["annual fee", "enhancement fee", "yearly fee", "maintenance fee"],
        "severity": "warning",
        "explanation": "Separate from monthly dues - often buried in the contract. Planet Fitness charges $49.99/year on top of monthly fees.",
        "protection": "Calculate total annual cost including all fees before signing."
    },
    "no_freeze": {
        "name": "No Freeze/Pause Option",
        "keywords": [],  # Absence detection
        "severity": "warning",
        "explanation": "If you get injured or travel, you keep paying.",
        "protection": "Negotiate freeze terms before signing. Most gyms offer this but don't advertise it."
    },
    "early_termination_fee": {
        "name": "Early Termination Fee",
        "keywords": ["early termination", "buyout", "remaining balance", "cancellation fee"],
        "severity": "warning",
        "explanation": "You may owe hundreds of dollars to exit the contract early.",
        "protection": "Check if fee exceeds your state's legal cap. Some states limit these fees."
    },
    "arbitration_clause": {
        "name": "Forced Arbitration",
        "keywords": ["arbitration", "waive", "class action", "jury trial"],
        "severity": "warning",
        "explanation": "You can't sue them or join a class action lawsuit - you have to go to private arbitration where they have the advantage.",
        "protection": "This is increasingly common. You may be able to opt out within 30 days of signing."
    },
    "personal_training_separate": {
        "name": "Personal Training is Separate",
        "keywords": ["personal training", "separate agreement", "pt contract"],
        "severity": "info",
        "explanation": "Canceling your membership does NOT cancel personal training. You could owe thousands.",
        "protection": "Review and cancel personal training separately. PT contracts often have stricter terms."
    }
}


def mock_gym_analysis(contract_text: str, state: str = None) -> dict:
    """Generate mock gym contract analysis for testing"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 30

    # Check for red flags
    if 'in person' in text_lower or 'visit' in text_lower and 'cancel' in text_lower:
        red_flags.append({
            "name": "In-Person Cancellation Only",
            "severity": "critical",
            "clause_text": "Cancellation requests must be made in person at your home club location...",
            "explanation": "You can only cancel by physically going to the gym. The FTC sued LA Fitness for this exact practice in August 2025.",
            "protection": "Check your state laws. Many states require alternative cancellation methods. Send certified mail anyway and keep records."
        })
        risk_score += 25

    if 'certified mail' in text_lower:
        red_flags.append({
            "name": "Certified Mail Required",
            "severity": "warning",
            "clause_text": "Written notice via certified mail to our corporate office...",
            "explanation": "They want you to go to the post office and pay for certified mail just to cancel.",
            "protection": "Do it. Keep the receipt. It's your proof they received it."
        })
        risk_score += 10

    if 'automatically renew' in text_lower or 'auto-renew' in text_lower:
        red_flags.append({
            "name": "Automatic Renewal Trap",
            "severity": "warning",
            "clause_text": "This agreement will automatically renew for successive monthly terms...",
            "explanation": "Your membership keeps going forever unless you actively cancel during the right window.",
            "protection": "Set calendar reminders 60 days before any renewal date. Know the exact cancellation window."
        })
        risk_score += 15

    if 'annual fee' in text_lower or 'enhancement fee' in text_lower:
        red_flags.append({
            "name": "Hidden Annual Fee",
            "severity": "warning",
            "clause_text": "Annual Enhancement Fee of $49.99 will be charged on...",
            "explanation": "This is on TOP of your monthly dues. They sneak it in once a year.",
            "protection": "Add this to your total annual cost calculation. Ask when it's charged so it doesn't surprise you."
        })
        risk_score += 10

    if 'arbitration' in text_lower:
        red_flags.append({
            "name": "Forced Arbitration",
            "severity": "warning",
            "clause_text": "Any disputes shall be resolved through binding arbitration...",
            "explanation": "You can't sue them or join a class action. Arbitration typically favors the company.",
            "protection": "Look for opt-out provisions. Some contracts let you opt out within 30 days."
        })
        risk_score += 10

    if 'early termination' in text_lower or 'buyout' in text_lower:
        red_flags.append({
            "name": "Early Termination Fee",
            "severity": "warning",
            "clause_text": "Early termination requires payment of remaining contract balance...",
            "explanation": "Want out early? That'll cost you. Could be hundreds of dollars.",
            "protection": "Check your state's limits on these fees. Some states cap them."
        })
        risk_score += 15

    # Check for missing protections
    if 'freeze' not in text_lower and 'pause' not in text_lower:
        red_flags.append({
            "name": "No Freeze Option Mentioned",
            "severity": "info",
            "clause_text": None,
            "explanation": "The contract doesn't mention freezing your membership. If you get injured or travel, you may keep paying.",
            "protection": "Ask about freeze policies before signing. Most gyms offer this but hide it."
        })
        risk_score += 5

    # Get state protections
    state_protections = []
    if state and state.upper() in STATE_GYM_PROTECTIONS:
        state_info = STATE_GYM_PROTECTIONS[state.upper()]
        state_protections.append(f"Cooling-off period: {state_info.get('cooling_off', 'Check local laws')}")
        if 'relocation_cancel' in state_info:
            state_protections.append(f"Relocation cancellation: {state_info['relocation_cancel']}")
        if 'max_term' in state_info:
            state_protections.append(f"Maximum contract term: {state_info['max_term']}")
        if 'notes' in state_info:
            state_protections.append(state_info['notes'])

    # Determine difficulty
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        cancellation_difficulty = "nightmare"
    elif risk_score >= 60:
        cancellation_difficulty = "hard"
    elif risk_score >= 40:
        cancellation_difficulty = "moderate"
    else:
        cancellation_difficulty = "easy"

    # Determine contract type
    if 'month-to-month' in text_lower or 'monthly' in text_lower and 'no commitment' in text_lower:
        contract_type = "month-to-month"
    elif '12 month' in text_lower or 'one year' in text_lower or 'annual' in text_lower:
        contract_type = "annual"
    elif '24 month' in text_lower or 'two year' in text_lower:
        contract_type = "multi-year"
    else:
        contract_type = "unknown"

    # Generate summary
    if critical_count > 0:
        summary = f"This gym contract is designed to trap you. {critical_count} critical issue(s) will make cancellation extremely difficult. "
    elif risk_score >= 50:
        summary = "This contract has several concerning clauses that could cost you money or make cancellation difficult. "
    else:
        summary = "This contract is relatively standard, but watch the renewal terms. "

    summary += f"Cancellation difficulty: {cancellation_difficulty.upper()}."

    # Generate cancellation guide
    guide = """HOW TO CANCEL THIS GYM MEMBERSHIP:

1. CHECK YOUR STATE LAWS
   - Look up your state's gym membership laws
   - Know your cooling-off period (often 3-5 days)
   - Check if your state requires alternative cancellation methods

2. DOCUMENT EVERYTHING
   - Screenshot all contract terms
   - Save all payment receipts
   - Record dates of all communication

3. SEND WRITTEN NOTICE
   - Even if they say "in person only", send certified mail
   - Include: name, member ID, request to cancel, effective date
   - Keep the certified mail receipt

4. FOLLOW UP
   - Call to confirm receipt
   - Get confirmation number/name of rep
   - Document the call

5. MONITOR YOUR ACCOUNTS
   - Watch for unauthorized charges after cancellation
   - Dispute any post-cancellation charges with your bank
   - File complaints with your state AG if they keep charging

6. IF THEY WON'T STOP:
   - File complaint: State Attorney General
   - File complaint: FTC (ReportFraud.ftc.gov)
   - File complaint: BBB
   - Consider credit card chargeback for unauthorized charges
"""

    return {
        "overall_risk": "high" if risk_score >= 60 else "medium" if risk_score >= 40 else "low",
        "risk_score": min(100, risk_score),
        "gym_name": None,
        "contract_type": contract_type,
        "monthly_fee": None,
        "cancellation_difficulty": cancellation_difficulty,
        "red_flags": red_flags,
        "state_protections": state_protections,
        "summary": summary,
        "cancellation_guide": guide
    }


GYM_ANALYSIS_PROMPT = """You are a consumer protection expert analyzing gym and fitness membership contracts.

Your job is to identify clauses that could "fuck" the member - terms that make cancellation difficult, hidden fees, or traps.

CONTRACT TEXT:
<<CONTRACT>>

STATE: <<STATE>>

STATE GYM LAWS:
<<STATE_LAWS>>

RED FLAGS TO CHECK:
<<RED_FLAGS>>

Return JSON:
{
    "overall_risk": "high" | "medium" | "low",
    "risk_score": 0-100 (100 = nightmare contract),
    "gym_name": "Name if found",
    "contract_type": "month-to-month" | "annual" | "multi-year" | "unknown",
    "monthly_fee": "$XX.XX if found",
    "cancellation_difficulty": "easy" | "moderate" | "hard" | "nightmare",
    "red_flags": [
        {
            "name": "Issue name",
            "severity": "critical" | "warning" | "info",
            "clause_text": "The actual contract text",
            "explanation": "Why this fucks you (plain language)",
            "protection": "What to do about it"
        }
    ],
    "state_protections": ["List of relevant state protections"],
    "summary": "2-3 sentence summary of how bad this contract is",
    "cancellation_guide": "Step-by-step guide to actually cancel this specific membership"
}

Be direct. Use phrases like "This means..." and "You're agreeing to..."
Return ONLY valid JSON."""


@app.post("/api/analyze-gym", response_model=GymContractReport)
async def analyze_gym_contract(input: GymContractInput):
    """Analyze a gym membership contract for red flags"""
    try:
        if MOCK_MODE:
            result = mock_gym_analysis(input.contract_text, input.state)
            save_upload("gym", input.contract_text, input.state, result)
            return GymContractReport(**result)

        client = get_client()

        # Get state laws
        state_laws = STATE_GYM_PROTECTIONS.get(input.state.upper() if input.state else "", {})

        prompt = GYM_ANALYSIS_PROMPT.replace("<<CONTRACT>>", input.contract_text[:15000])
        prompt = prompt.replace("<<STATE>>", input.state or "Not specified")
        prompt = prompt.replace("<<STATE_LAWS>>", json.dumps(state_laws, indent=2))
        prompt = prompt.replace("<<RED_FLAGS>>", json.dumps(GYM_RED_FLAGS, indent=2))

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("gym", input.contract_text, input.state, result)
        return GymContractReport(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gym contract analysis failed: {str(e)}")


# ============== EMPLOYMENT CONTRACT ANALYSIS ==============

class EmploymentRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str

class EmploymentContractInput(BaseModel):
    contract_text: str
    state: Optional[str] = None
    salary: Optional[int] = None  # For threshold checking

class EmploymentContractReport(BaseModel):
    overall_risk: str
    risk_score: int
    document_type: str  # "offer_letter", "employment_agreement", "handbook", "severance"
    has_non_compete: bool
    non_compete_enforceable: Optional[str]  # "likely", "unlikely", "unknown"
    has_arbitration: bool
    has_ip_assignment: bool
    red_flags: list[EmploymentRedFlag]
    state_notes: list[str]
    summary: str
    negotiation_points: str

# States that ban/restrict non-competes
NON_COMPETE_STATES = {
    "CA": {"status": "BANNED", "notes": "Non-competes void. Employers must notify employees of this."},
    "MN": {"status": "BANNED", "notes": "Banned effective July 2023."},
    "ND": {"status": "BANNED", "notes": "Non-competes unenforceable."},
    "OK": {"status": "BANNED", "notes": "Non-competes generally void."},
    "CO": {"status": "THRESHOLD", "threshold": 127091, "notes": "Only enforceable above $127,091 salary."},
    "IL": {"status": "THRESHOLD", "threshold": 75000, "notes": "Only enforceable above $75,000 salary."},
    "WA": {"status": "THRESHOLD", "threshold": 123394, "notes": "Only enforceable above $123,394 salary."},
    "ME": {"status": "RESTRICTED", "notes": "Cannot require non-compete before offer. 3-day review period required."},
    "MA": {"status": "RESTRICTED", "notes": "Max 1 year. Garden leave required. Not for hourly workers."},
    "OR": {"status": "RESTRICTED", "notes": "Max 18 months. Only for employees earning $113,241+."},
}

EMPLOYMENT_RED_FLAGS = {
    "broad_non_compete": {
        "name": "Overly Broad Non-Compete",
        "keywords": ["non-compete", "covenant not to compete", "compete with"],
        "severity": "critical",
        "explanation": "This could prevent you from working in your industry for years after leaving.",
        "protection": "Check your state's laws. Negotiate scope, geography, and duration."
    },
    "mandatory_arbitration": {
        "name": "Mandatory Arbitration",
        "keywords": ["binding arbitration", "arbitration agreement", "waive right to jury"],
        "severity": "warning",
        "explanation": "You give up your right to sue. Arbitration typically favors employers who use it repeatedly.",
        "protection": "Look for opt-out provisions (often within 30 days). Consider negotiating removal."
    },
    "class_action_waiver": {
        "name": "Class Action Waiver",
        "keywords": ["class action", "collective action", "waive right to participate"],
        "severity": "warning",
        "explanation": "You can't join other employees in lawsuits. Makes it expensive to pursue small claims.",
        "protection": "Some waivers are unenforceable. Consult an employment attorney if concerned."
    },
    "broad_ip_assignment": {
        "name": "Broad IP Assignment",
        "keywords": ["all inventions", "work product", "assign all rights", "intellectual property"],
        "severity": "warning",
        "explanation": "The company may own things you create on your own time, with your own resources.",
        "protection": "Check state protections (CA, IL, WA, DE, MN, NC, NV). Attach prior inventions list."
    },
    "no_moonlighting": {
        "name": "No Outside Work",
        "keywords": ["sole employer", "exclusive", "no other employment", "outside business"],
        "severity": "info",
        "explanation": "You may not be allowed to do freelance work or side projects.",
        "protection": "Negotiate explicit carve-outs for non-competing activities."
    },
    "clawback_provisions": {
        "name": "Clawback Provisions",
        "keywords": ["clawback", "repay", "forfeit", "return bonus"],
        "severity": "warning",
        "explanation": "You may have to return bonuses or other compensation if you leave.",
        "protection": "Understand triggers. Negotiate reasonable vesting schedules."
    },
    "garden_leave_unpaid": {
        "name": "Garden Leave Without Pay",
        "keywords": ["garden leave", "transition period"],
        "severity": "critical",
        "explanation": "You can't work during the transition but they're not paying you.",
        "protection": "Massachusetts requires 50% pay. Negotiate pay continuation."
    }
}


def mock_employment_analysis(contract_text: str, state: str = None, salary: int = None) -> dict:
    """Generate mock employment contract analysis"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 20
    state_notes = []

    # Check state rules
    has_non_compete = 'non-compete' in text_lower or 'covenant not to compete' in text_lower
    has_arbitration = 'arbitration' in text_lower
    has_ip_assignment = 'intellectual property' in text_lower or 'inventions' in text_lower

    non_compete_enforceable = "unknown"
    if state and state.upper() in NON_COMPETE_STATES:
        state_info = NON_COMPETE_STATES[state.upper()]
        if state_info["status"] == "BANNED":
            non_compete_enforceable = "unlikely"
            state_notes.append(f"{state.upper()}: {state_info['notes']}")
        elif state_info["status"] == "THRESHOLD":
            if salary and salary < state_info["threshold"]:
                non_compete_enforceable = "unlikely"
                state_notes.append(f"Your salary (${salary:,}) is below {state.upper()}'s threshold (${state_info['threshold']:,}) - non-compete likely unenforceable")
            else:
                non_compete_enforceable = "likely"
                state_notes.append(f"{state.upper()} threshold: ${state_info['threshold']:,}")

    if has_non_compete:
        red_flags.append({
            "name": "Non-Compete Agreement",
            "severity": "critical" if non_compete_enforceable != "unlikely" else "warning",
            "clause_text": "Employee agrees not to compete with the Company...",
            "explanation": "This restricts where you can work after leaving. Could limit your career options for months or years.",
            "protection": f"Non-compete is {non_compete_enforceable} to be enforceable in {state or 'your state'}. Negotiate shorter duration and narrower scope."
        })
        risk_score += 20 if non_compete_enforceable != "unlikely" else 5

    if has_arbitration:
        red_flags.append({
            "name": "Mandatory Arbitration",
            "severity": "warning",
            "clause_text": "Any disputes shall be resolved through binding arbitration...",
            "explanation": "You're giving up your right to sue in court or join class actions. Arbitration typically favors repeat-player employers.",
            "protection": "Look for an opt-out provision - you often have 30 days to opt out after signing."
        })
        risk_score += 15

    if 'class action' in text_lower and 'waive' in text_lower:
        red_flags.append({
            "name": "Class Action Waiver",
            "severity": "warning",
            "clause_text": "Employee waives right to participate in class or collective actions...",
            "explanation": "You can't join other employees in lawsuits. This makes it economically unfeasible to pursue small claims.",
            "protection": "Some waivers are unenforceable for certain claims. NLRA-protected activity cannot be waived."
        })
        risk_score += 10

    if has_ip_assignment:
        if 'all inventions' in text_lower or 'during employment' in text_lower:
            red_flags.append({
                "name": "Broad IP Assignment",
                "severity": "warning",
                "clause_text": "Employee assigns all inventions conceived during employment...",
                "explanation": "The company may claim ownership of things you create on your own time, with your own resources.",
                "protection": "CA, IL, WA, DE, MN, NC, NV protect personal inventions made on your own time. Attach a prior inventions schedule."
            })
            risk_score += 10

    if 'at-will' in text_lower:
        red_flags.append({
            "name": "At-Will Employment",
            "severity": "info",
            "clause_text": "Employment is at-will and may be terminated at any time...",
            "explanation": "Standard language - they can fire you anytime for any legal reason (and you can quit anytime).",
            "protection": "This is normal. Focus on severance and notice period terms."
        })

    # Determine document type
    if 'offer' in text_lower and 'accept' in text_lower:
        doc_type = "offer_letter"
    elif 'severance' in text_lower or 'separation' in text_lower:
        doc_type = "severance"
    elif 'handbook' in text_lower or 'policy' in text_lower:
        doc_type = "handbook"
    else:
        doc_type = "employment_agreement"

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        summary = f"This contract has {critical_count} critical issue(s) that could significantly limit your future options. "
    else:
        summary = "This contract has some standard restrictions you should understand. "

    if has_non_compete and non_compete_enforceable == "unlikely":
        summary += f"Good news: the non-compete is likely unenforceable in {state or 'your state'}."
    elif has_non_compete:
        summary += "The non-compete could limit where you work after leaving."

    # Generate negotiation points
    negotiation = """POINTS TO NEGOTIATE:

"""
    if has_non_compete:
        negotiation += """1. NON-COMPETE
   - Shorten duration (1 year max is reasonable)
   - Narrow geographic scope to where you actually work
   - Define "competitors" specifically (named companies only)
   - Add carve-outs for non-competing roles

"""
    if has_arbitration:
        negotiation += """2. ARBITRATION
   - Request opt-out provision (30 days to decide)
   - Or negotiate removal entirely
   - At minimum, ensure costs are split fairly

"""
    if has_ip_assignment:
        negotiation += """3. IP ASSIGNMENT
   - Limit to inventions made using company resources
   - Limit to inventions related to company business
   - Attach prior inventions schedule
   - Retain rights to personal projects on own time

"""
    negotiation += """GENERAL TIPS:
- Get all promises in writing (don't rely on verbal agreements)
- Ask for time to review (never sign same day)
- Consider having an employment attorney review
- Document everything during employment
"""

    return {
        "overall_risk": "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low",
        "risk_score": min(100, risk_score),
        "document_type": doc_type,
        "has_non_compete": has_non_compete,
        "non_compete_enforceable": non_compete_enforceable if has_non_compete else None,
        "has_arbitration": has_arbitration,
        "has_ip_assignment": has_ip_assignment,
        "red_flags": red_flags,
        "state_notes": state_notes,
        "summary": summary,
        "negotiation_points": negotiation
    }


EMPLOYMENT_ANALYSIS_PROMPT = """You are an employment attorney helping an employee understand their employment contract.

Your job is to identify clauses that could limit their career options or rights.

CONTRACT TEXT:
<<CONTRACT>>

STATE: <<STATE>>
SALARY: <<SALARY>>

NON-COMPETE STATE RULES:
<<STATE_RULES>>

RED FLAGS TO CHECK:
<<RED_FLAGS>>

Return JSON:
{
    "overall_risk": "high" | "medium" | "low",
    "risk_score": 0-100,
    "document_type": "offer_letter" | "employment_agreement" | "handbook" | "severance",
    "has_non_compete": true/false,
    "non_compete_enforceable": "likely" | "unlikely" | "unknown",
    "has_arbitration": true/false,
    "has_ip_assignment": true/false,
    "red_flags": [
        {
            "name": "Issue name",
            "severity": "critical" | "warning" | "info",
            "clause_text": "The actual contract text",
            "explanation": "Why this matters (plain language)",
            "protection": "What to do about it"
        }
    ],
    "state_notes": ["State-specific information"],
    "summary": "2-3 sentence summary",
    "negotiation_points": "Points the employee could negotiate"
}

Be direct and practical.
Return ONLY valid JSON."""


@app.post("/api/analyze-employment", response_model=EmploymentContractReport)
async def analyze_employment_contract(input: EmploymentContractInput):
    """Analyze an employment contract for problematic terms"""
    try:
        if MOCK_MODE:
            result = mock_employment_analysis(input.contract_text, input.state, input.salary)
            save_upload("employment", input.contract_text, input.state, result)
            return EmploymentContractReport(**result)

        client = get_client()

        state_rules = NON_COMPETE_STATES.get(input.state.upper() if input.state else "", {})

        prompt = EMPLOYMENT_ANALYSIS_PROMPT.replace("<<CONTRACT>>", input.contract_text[:15000])
        prompt = prompt.replace("<<STATE>>", input.state or "Not specified")
        prompt = prompt.replace("<<SALARY>>", f"${input.salary:,}" if input.salary else "Not specified")
        prompt = prompt.replace("<<STATE_RULES>>", json.dumps(state_rules, indent=2))
        prompt = prompt.replace("<<RED_FLAGS>>", json.dumps(EMPLOYMENT_RED_FLAGS, indent=2))

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("employment", input.contract_text, input.state, result)
        return EmploymentContractReport(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Employment contract analysis failed: {str(e)}")


# ============== FREELANCER CONTRACT ANALYSIS ==============

class FreelancerRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str

class FreelancerContractInput(BaseModel):
    contract_text: str
    project_value: Optional[int] = None

class FreelancerContractReport(BaseModel):
    overall_risk: str
    risk_score: int
    contract_type: str  # "project", "retainer", "sow"
    payment_terms: Optional[str]
    ip_ownership: str  # "work_for_hire", "license", "assignment", "unclear"
    has_kill_fee: bool
    revision_limit: Optional[str]
    red_flags: list[FreelancerRedFlag]
    missing_protections: list[str]
    summary: str
    suggested_changes: str


def mock_freelancer_analysis(contract_text: str, project_value: int = None) -> dict:
    """Generate mock freelancer contract analysis"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 25
    missing_protections = []

    # Payment terms
    payment_terms = None
    if 'net 90' in text_lower:
        payment_terms = "Net 90"
        red_flags.append({
            "name": "Net 90 Payment Terms",
            "severity": "critical",
            "clause_text": "Payment due within 90 days of invoice...",
            "explanation": "You're waiting 3 months to get paid. That's a loan to your client.",
            "protection": "Counter with Net-30 maximum. Require 50% deposit upfront."
        })
        risk_score += 25
    elif 'net 60' in text_lower:
        payment_terms = "Net 60"
        red_flags.append({
            "name": "Net 60 Payment Terms",
            "severity": "warning",
            "clause_text": "Payment due within 60 days...",
            "explanation": "Two months is a long time to wait for your money.",
            "protection": "Counter with Net-30. Request deposit for large projects."
        })
        risk_score += 15
    elif 'net 30' in text_lower:
        payment_terms = "Net 30"

    # IP ownership
    ip_ownership = "unclear"
    if 'work for hire' in text_lower or 'work made for hire' in text_lower:
        ip_ownership = "work_for_hire"
        red_flags.append({
            "name": "Work For Hire",
            "severity": "warning",
            "clause_text": "All work product shall be considered work made for hire...",
            "explanation": "Client owns everything from the moment you create it. You can't use it in your portfolio without permission.",
            "protection": "Ensure you retain portfolio rights. If giving up all rights, charge a premium (2-3x)."
        })
        risk_score += 10
    elif 'assigns all' in text_lower or 'assign all rights' in text_lower:
        ip_ownership = "assignment"
        risk_score += 10

    # Kill fee
    has_kill_fee = 'kill fee' in text_lower or 'cancellation fee' in text_lower
    if not has_kill_fee and 'cancel' not in text_lower:
        missing_protections.append("No kill fee - client can cancel without paying")
        risk_score += 15

    # Revisions
    revision_limit = None
    if 'unlimited revision' in text_lower:
        revision_limit = "Unlimited"
        red_flags.append({
            "name": "Unlimited Revisions",
            "severity": "critical",
            "clause_text": "Contractor shall provide unlimited revisions until Client approval...",
            "explanation": "You could be revising forever. There's no end to this.",
            "protection": "Negotiate 2-3 revision rounds. Additional revisions at hourly rate."
        })
        risk_score += 25

    # Non-compete
    if 'non-compete' in text_lower or 'not compete' in text_lower:
        red_flags.append({
            "name": "Non-Compete Clause",
            "severity": "critical",
            "clause_text": "Contractor shall not provide services to competitors...",
            "explanation": "This could prevent you from working with other clients in this industry.",
            "protection": "Resist non-competes. If required, limit to specific named companies and short duration."
        })
        risk_score += 20

    # Indemnification
    if 'indemnify' in text_lower and 'hold harmless' in text_lower:
        red_flags.append({
            "name": "One-Sided Indemnification",
            "severity": "warning",
            "clause_text": "Contractor shall indemnify and hold harmless Client...",
            "explanation": "You may be on the hook for the client's problems, not just your own.",
            "protection": "Make indemnification mutual. Cap liability at fees paid."
        })
        risk_score += 10

    # Missing protections
    if 'deposit' not in text_lower and 'milestone' not in text_lower:
        missing_protections.append("No deposit or milestone payments")
    if 'late fee' not in text_lower and 'interest' not in text_lower:
        missing_protections.append("No late payment penalties")
    if 'portfolio' not in text_lower and 'display' not in text_lower:
        missing_protections.append("No portfolio rights mentioned")

    # Determine contract type
    if 'statement of work' in text_lower or 'sow' in text_lower:
        contract_type = "sow"
    elif 'retainer' in text_lower:
        contract_type = "retainer"
    else:
        contract_type = "project"

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        summary = f"This contract has {critical_count} critical issue(s) that could seriously hurt you. "
    else:
        summary = "This contract has some concerning terms but nothing catastrophic. "

    if missing_protections:
        summary += f"It's also missing {len(missing_protections)} standard protections."

    # Generate suggestions
    suggestions = """CHANGES TO REQUEST:

"""
    if payment_terms in ["Net 60", "Net 90"]:
        suggestions += """1. PAYMENT TERMS
   - Change to Net-30 maximum
   - Add: "50% deposit due upon signing"
   - Add: "Late payments incur 1.5% monthly interest"

"""
    if not has_kill_fee:
        suggestions += """2. KILL FEE
   - Add: "If Client cancels after work begins, Client shall pay:
     - 25% of total if cancelled before delivery
     - 50% of total if cancelled after partial delivery
     - 100% of total if cancelled after full delivery"

"""
    if revision_limit == "Unlimited":
        suggestions += """3. REVISION LIMITS
   - Change to: "This agreement includes 2 rounds of revisions.
     Additional revisions billed at $[X]/hour."

"""
    if ip_ownership == "work_for_hire":
        suggestions += """4. PORTFOLIO RIGHTS
   - Add: "Contractor retains the right to display final deliverables
     in portfolio and self-promotional materials after public release."

"""
    suggestions += """GENERAL TIPS:
- Never start work without a signed contract
- Get deposit before starting large projects
- Keep records of all deliveries and communications
- Invoice immediately upon delivery
"""

    return {
        "overall_risk": "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low",
        "risk_score": min(100, risk_score),
        "contract_type": contract_type,
        "payment_terms": payment_terms,
        "ip_ownership": ip_ownership,
        "has_kill_fee": has_kill_fee,
        "revision_limit": revision_limit,
        "red_flags": red_flags,
        "missing_protections": missing_protections,
        "summary": summary,
        "suggested_changes": suggestions
    }


@app.post("/api/analyze-freelancer", response_model=FreelancerContractReport)
async def analyze_freelancer_contract(input: FreelancerContractInput):
    """Analyze a freelancer/contractor agreement"""
    try:
        if MOCK_MODE:
            result = mock_freelancer_analysis(input.contract_text, input.project_value)
            save_upload("freelancer", input.contract_text, None, result)
            return FreelancerContractReport(**result)

        client = get_client()

        prompt = f"""You are a contract expert helping freelancers understand client agreements.

Analyze this freelancer contract for problems:

CONTRACT:
{input.contract_text[:15000]}

PROJECT VALUE: {f"${input.project_value:,}" if input.project_value else "Not specified"}

Return JSON:
{{
    "overall_risk": "high" | "medium" | "low",
    "risk_score": 0-100,
    "contract_type": "project" | "retainer" | "sow",
    "payment_terms": "Net 30" etc or null,
    "ip_ownership": "work_for_hire" | "license" | "assignment" | "unclear",
    "has_kill_fee": true/false,
    "revision_limit": "2 rounds" or "Unlimited" or null,
    "red_flags": [{{
        "name": "Issue",
        "severity": "critical" | "warning" | "info",
        "clause_text": "Actual text",
        "explanation": "Plain language explanation",
        "protection": "What to do"
    }}],
    "missing_protections": ["Things that should be in the contract but aren't"],
    "summary": "2-3 sentence summary",
    "suggested_changes": "Specific language to request"
}}

Be direct. Focus on payment, IP, scope, and liability.
Return ONLY valid JSON."""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("freelancer", input.contract_text, None, result)
        return FreelancerContractReport(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Freelancer contract analysis failed: {str(e)}")


# ============== INFLUENCER CONTRACT ANALYSIS ==============

class InfluencerRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str

class InfluencerContractInput(BaseModel):
    contract_text: str
    base_rate: Optional[int] = None  # To calculate fair usage premiums

class InfluencerContractReport(BaseModel):
    overall_risk: str
    risk_score: int
    brand_name: Optional[str]
    campaign_type: str  # "one_off", "ongoing", "ambassador"
    usage_rights_duration: Optional[str]
    exclusivity_scope: Optional[str]
    payment_terms: Optional[str]
    has_perpetual_rights: bool
    has_ai_training_rights: bool
    ftc_compliance: str  # "addressed", "unclear", "missing"
    red_flags: list[InfluencerRedFlag]
    summary: str
    negotiation_script: str


def mock_influencer_analysis(contract_text: str, base_rate: int = None) -> dict:
    """Generate mock influencer contract analysis"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 25

    # Check for perpetual rights
    has_perpetual_rights = 'perpetuity' in text_lower or 'forever' in text_lower or 'unlimited duration' in text_lower
    if has_perpetual_rights:
        red_flags.append({
            "name": "Perpetual Usage Rights",
            "severity": "critical",
            "clause_text": "Brand is granted rights in perpetuity...",
            "explanation": "They can use your content FOREVER. No time limit. This should cost 3x your normal rate.",
            "protection": "Counter with 90-day usage. Perpetual rights = 100-150% premium minimum."
        })
        risk_score += 25

    # Check usage duration
    usage_rights_duration = None
    if has_perpetual_rights:
        usage_rights_duration = "Perpetual (FOREVER)"
    elif '12 month' in text_lower or 'one year' in text_lower:
        usage_rights_duration = "12 months"
        red_flags.append({
            "name": "12-Month Usage Rights",
            "severity": "warning",
            "clause_text": "Usage rights for 12 months from posting date...",
            "explanation": "A year is long. Standard is 30-90 days. This should cost more.",
            "protection": "Negotiate additional compensation for extended usage."
        })
        risk_score += 10
    elif '90 day' in text_lower or '3 month' in text_lower:
        usage_rights_duration = "90 days"

    # Check for AI training rights
    has_ai_training_rights = 'machine learning' in text_lower or 'ai training' in text_lower or 'artificial intelligence' in text_lower
    if has_ai_training_rights:
        red_flags.append({
            "name": "AI Training Rights",
            "severity": "critical",
            "clause_text": "Content may be used for machine learning or AI model training...",
            "explanation": "They want to feed your content to AI. Your likeness, voice, style could be replicated.",
            "protection": "Remove this clause entirely. This is a new and dangerous term."
        })
        risk_score += 20

    # Check exclusivity
    exclusivity_scope = None
    if 'exclusiv' in text_lower:
        if 'category' in text_lower:
            exclusivity_scope = "Category-wide"
        elif 'competitor' in text_lower:
            exclusivity_scope = "Named competitors"
        else:
            exclusivity_scope = "Broad/unclear"

        if 'including but not limited to' in text_lower:
            red_flags.append({
                "name": "Vague Exclusivity",
                "severity": "critical",
                "clause_text": "Creator shall not work with competitors including but not limited to...",
                "explanation": "'Including but not limited to' means they can block ANY deal they want. Total trap.",
                "protection": "Demand a specific named list of competitors. No 'including but not limited to.'"
            })
            risk_score += 20

    # Check FTC compliance
    ftc_compliance = "missing"
    if '#ad' in text_lower or 'disclose' in text_lower or 'ftc' in text_lower:
        ftc_compliance = "addressed"
    elif 'partner' in text_lower or 'sponsor' in text_lower:
        ftc_compliance = "unclear"
        red_flags.append({
            "name": "Unclear FTC Disclosure Terms",
            "severity": "warning",
            "clause_text": None,
            "explanation": "The contract doesn't clearly specify FTC disclosure requirements. You could be liable for fines.",
            "protection": "Add clear disclosure requirements. Use #ad or #sponsored. Both parties share responsibility."
        })
        risk_score += 10
    else:
        red_flags.append({
            "name": "No FTC Compliance Mentioned",
            "severity": "warning",
            "clause_text": None,
            "explanation": "No mention of disclosure requirements. FTC fines are $53,000+ per violation.",
            "protection": "Add disclosure clause. Specify who's responsible. You need this protection."
        })
        risk_score += 10

    # Check payment terms
    payment_terms = None
    if 'net 90' in text_lower:
        payment_terms = "Net 90"
        red_flags.append({
            "name": "Net 90 Payment",
            "severity": "critical",
            "clause_text": "Payment within 90 days of campaign completion...",
            "explanation": "Three months to get paid?! That's ridiculous. You've already done the work.",
            "protection": "Counter with Net-30. Request 50% upfront."
        })
        risk_score += 20
    elif 'net 60' in text_lower:
        payment_terms = "Net 60"
        risk_score += 10

    # Check revisions
    if 'unlimited revision' in text_lower:
        red_flags.append({
            "name": "Unlimited Revisions",
            "severity": "critical",
            "clause_text": "Creator shall make revisions until Brand approval...",
            "explanation": "You could be creating content forever. There's no end to this.",
            "protection": "Cap at 2 revision rounds. Additional revisions = additional fee."
        })
        risk_score += 15

    # Check morality clause
    if 'morality' in text_lower or 'moral' in text_lower or 'public disrepute' in text_lower:
        if 'brand' not in text_lower or 'mutual' not in text_lower:
            red_flags.append({
                "name": "One-Sided Morality Clause",
                "severity": "warning",
                "clause_text": "If Creator engages in conduct that damages Brand reputation...",
                "explanation": "They can terminate if YOU do something controversial, but what if THEY do? No protection for you.",
                "protection": "Make it mutual. If the brand has a scandal, you can terminate too."
            })
            risk_score += 10

    # Determine campaign type
    if 'ambassador' in text_lower:
        campaign_type = "ambassador"
    elif 'ongoing' in text_lower or 'monthly' in text_lower:
        campaign_type = "ongoing"
    else:
        campaign_type = "one_off"

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        summary = f"This brand deal has {critical_count} major problem(s) that could cost you money or limit your future deals. "
    else:
        summary = "This contract is fairly standard, but there are some terms to negotiate. "

    if has_perpetual_rights:
        summary += "The perpetual rights clause is a big deal - don't accept this without significant extra pay."

    # Generate negotiation script
    script = """WHAT TO SAY TO THE BRAND:

"""
    if has_perpetual_rights:
        script += """RE: USAGE RIGHTS
"I'm happy to grant extended usage, but perpetual rights require additional
compensation. My rate for perpetual rights is [3x base rate]. Alternatively,
I can offer 90-day usage at my standard rate with renewal options."

"""
    if exclusivity_scope:
        script += """RE: EXCLUSIVITY
"I need a specific list of competitors for the exclusivity clause. 'Including
but not limited to' is too broad and could prevent me from taking legitimate
work. Please provide named companies only, and let's discuss the exclusivity
period - my standard is campaign duration plus 30 days."

"""
    if has_ai_training_rights:
        script += """RE: AI TRAINING
"I'm not comfortable with AI training rights at this time. Please remove
this clause. If this is essential to the campaign, I'd need to understand
the specific use case and negotiate appropriate compensation."

"""
    script += """GENERAL TIPS:
- Never accept first offer on usage rights
- Exclusivity = extra compensation
- Get everything in writing
- Don't sign same day - take time to review
- Counter-offer is expected - don't be afraid to negotiate
"""

    return {
        "overall_risk": "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low",
        "risk_score": min(100, risk_score),
        "brand_name": None,
        "campaign_type": campaign_type,
        "usage_rights_duration": usage_rights_duration,
        "exclusivity_scope": exclusivity_scope,
        "payment_terms": payment_terms,
        "has_perpetual_rights": has_perpetual_rights,
        "has_ai_training_rights": has_ai_training_rights,
        "ftc_compliance": ftc_compliance,
        "red_flags": red_flags,
        "summary": summary,
        "negotiation_script": script
    }


@app.post("/api/analyze-influencer", response_model=InfluencerContractReport)
async def analyze_influencer_contract(input: InfluencerContractInput):
    """Analyze an influencer/sponsorship contract"""
    try:
        if MOCK_MODE:
            result = mock_influencer_analysis(input.contract_text, input.base_rate)
            save_upload("influencer", input.contract_text, None, result)
            return InfluencerContractReport(**result)

        client = get_client()

        prompt = f"""You are an expert helping content creators understand brand deals.

Analyze this influencer contract:

CONTRACT:
{input.contract_text[:15000]}

BASE RATE: {f"${input.base_rate:,}" if input.base_rate else "Not specified"}

Return JSON:
{{
    "overall_risk": "high" | "medium" | "low",
    "risk_score": 0-100,
    "brand_name": "Brand name if found",
    "campaign_type": "one_off" | "ongoing" | "ambassador",
    "usage_rights_duration": "90 days" or "Perpetual" etc,
    "exclusivity_scope": "Category-wide" or "Named competitors" or null,
    "payment_terms": "Net 30" etc or null,
    "has_perpetual_rights": true/false,
    "has_ai_training_rights": true/false,
    "ftc_compliance": "addressed" | "unclear" | "missing",
    "red_flags": [{{
        "name": "Issue",
        "severity": "critical" | "warning" | "info",
        "clause_text": "Actual text",
        "explanation": "Plain language, direct",
        "protection": "What to negotiate"
    }}],
    "summary": "2-3 sentences",
    "negotiation_script": "Exact phrases to use with the brand"
}}

Be direct. Creators need to understand the real impact.
Return ONLY valid JSON."""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("influencer", input.contract_text, None, result)
        return InfluencerContractReport(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Influencer contract analysis failed: {str(e)}")


# ============== TIMESHARE CONTRACT ANALYSIS ==============

class TimeshareRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str

class TimeshareContractInput(BaseModel):
    contract_text: str
    state: Optional[str] = None
    purchase_price: Optional[int] = None
    annual_fee: Optional[int] = None

class TimeshareContractReport(BaseModel):
    overall_risk: str  # Almost always "high" for timeshares
    risk_score: int
    resort_name: Optional[str]
    ownership_type: str  # "deeded", "right_to_use", "points", "unknown"
    has_perpetuity_clause: bool
    rescission_deadline: Optional[str]
    estimated_10yr_cost: Optional[str]
    red_flags: list[TimeshareRedFlag]
    exit_options: list[str]
    summary: str
    rescission_letter: str


# State rescission periods
TIMESHARE_RESCISSION = {
    "AK": {"days": 15, "type": "calendar", "notes": "From receipt of public offering statement"},
    "DC": {"days": 15, "type": "calendar", "notes": ""},
    "FL": {"days": 10, "type": "calendar", "notes": "Major timeshare hub"},
    "MD": {"days": 10, "type": "calendar", "notes": ""},
    "MI": {"days": 9, "type": "calendar", "notes": "From receipt of disclosure"},
    "CA": {"days": 7, "type": "calendar", "notes": "Mandates standardized contracts"},
    "AZ": {"days": 7, "type": "calendar", "notes": ""},
    "CO": {"days": 5, "type": "calendar", "notes": ""},
    "NV": {"days": 5, "type": "calendar", "notes": "Until midnight of 5th day"},
    "AR": {"days": 5, "type": "calendar", "notes": ""},
    "OH": {"days": 3, "type": "business", "notes": ""},
    "KS": {"days": 3, "type": "business", "notes": ""},
    "IN": {"days": 3, "type": "business", "notes": "72 hours"},
}


def mock_timeshare_analysis(contract_text: str, state: str = None, purchase_price: int = None, annual_fee: int = None) -> dict:
    """Generate mock timeshare contract analysis"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 60  # Timeshares start with high risk

    # Check for perpetuity clause
    has_perpetuity_clause = 'perpetuity' in text_lower or 'heirs' in text_lower or 'forever' in text_lower or 'successors' in text_lower
    if has_perpetuity_clause:
        red_flags.append({
            "name": "Perpetuity Clause",
            "severity": "critical",
            "clause_text": "This agreement shall be binding upon Owner's heirs, successors, and assigns in perpetuity...",
            "explanation": "This obligation NEVER ENDS. It passes to your kids when you die. They inherit your debt.",
            "protection": "This is nearly impossible to exit. Only 15% of buyers use rescission period. If you just signed, CANCEL NOW."
        })
        risk_score += 20

    # Check ownership type
    ownership_type = "unknown"
    if 'deeded' in text_lower or 'fee simple' in text_lower:
        ownership_type = "deeded"
        red_flags.append({
            "name": "Deeded Ownership",
            "severity": "warning",
            "clause_text": "Owner receives an undivided fractional interest in fee simple...",
            "explanation": "You own a fraction of real property - which sounds good but means perpetual obligations and harder exit.",
            "protection": "Deeded ownership is harder to escape than right-to-use."
        })
        risk_score += 10
    elif 'right to use' in text_lower or 'license' in text_lower:
        ownership_type = "right_to_use"
        # RTU is slightly better - it expires
    elif 'points' in text_lower:
        ownership_type = "points"

    # Check for uncapped maintenance fees
    if 'maintenance' in text_lower:
        if 'increase' in text_lower or 'adjust' in text_lower:
            red_flags.append({
                "name": "Uncapped Maintenance Fees",
                "severity": "critical",
                "clause_text": "Maintenance fees are subject to annual adjustment...",
                "explanation": "Fees increase 3-8% EVERY YEAR. Average is $1,480/year. In 10 years that could be over $2,000/year.",
                "protection": "There is no protection. This is how timeshares work. Budget for 50% increase over 10 years."
            })
            risk_score += 15

    # Check for special assessments
    if 'special assessment' in text_lower:
        red_flags.append({
            "name": "Special Assessment Authority",
            "severity": "critical",
            "clause_text": "The Association may levy special assessments...",
            "explanation": "They can hit you with surprise bills of $1,000-$3,000+ for 'improvements' or repairs.",
            "protection": "There is no protection. You must pay or face collection/credit damage."
        })
        risk_score += 10

    # Check for rescission period
    rescission_deadline = None
    if state and state.upper() in TIMESHARE_RESCISSION:
        rescission_info = TIMESHARE_RESCISSION[state.upper()]
        rescission_deadline = f"{rescission_info['days']} {rescission_info['type']} days"
        red_flags.append({
            "name": f"Rescission Period: {rescission_deadline}",
            "severity": "info",
            "clause_text": None,
            "explanation": f"You have {rescission_info['days']} {rescission_info['type']} days to cancel and get your money back. After that, you're stuck.",
            "protection": "CANCEL NOW if you're having second thoughts. Send certified mail TODAY."
        })

    # Calculate 10-year cost
    estimated_10yr_cost = None
    if purchase_price and annual_fee:
        # Assume 5% annual fee increase
        total_fees = sum([annual_fee * (1.05 ** year) for year in range(10)])
        total_cost = purchase_price + total_fees
        estimated_10yr_cost = f"${total_cost:,.0f}"
        if total_cost > 50000:
            red_flags.append({
                "name": f"10-Year Cost: {estimated_10yr_cost}",
                "severity": "critical",
                "clause_text": None,
                "explanation": f"Purchase (${purchase_price:,}) + 10 years of fees = {estimated_10yr_cost}. You could take a LOT of vacations for that money.",
                "protection": "Do the math. Compare to just booking hotels/vacation rentals."
            })

    # Integration clause
    if 'entire agreement' in text_lower or 'no representations' in text_lower:
        red_flags.append({
            "name": "Integration Clause (License to Lie)",
            "severity": "warning",
            "clause_text": "This Agreement constitutes the entire agreement... No representations or promises not contained herein shall be binding...",
            "explanation": "Everything the salesperson promised? Doesn't count. Only what's written in this contract matters.",
            "protection": "Get ALL verbal promises in writing BEFORE signing. If they won't, assume they were lying."
        })
        risk_score += 10

    # Generate exit options
    exit_options = []
    if rescission_deadline:
        exit_options.append(f"RESCISSION: Cancel within {rescission_deadline} via certified mail (FREE)")
    exit_options.append("DEVELOPER DEED-BACK: Contact developer's exit program (Wyndham Cares, Marriott, etc.) - $200-$1,000")
    exit_options.append("RESALE: RedWeek.com, TUG2.com - Expect to sell for $0-$1 just to transfer obligation")
    exit_options.append("ATTORNEY: For misrepresentation claims - $3,000-$7,000")
    exit_options.append("ARDA: Call (855) 939-1515 for exit assistance")
    exit_options.append("AVOID: Any 'exit company' demanding large upfront fees - likely a scam")

    # Generate summary
    summary = "Timeshares are designed to be nearly impossible to exit. "
    if has_perpetuity_clause:
        summary += "This one has a perpetuity clause - it passes to your heirs. "
    if rescission_deadline:
        summary += f"If you just signed, you have {rescission_deadline} to cancel FOR FREE. Do it now."
    else:
        summary += "After the rescission period, your options are very limited."

    # Generate rescission letter
    rescission_letter = f"""VIA CERTIFIED MAIL - RETURN RECEIPT REQUESTED

Date: [TODAY'S DATE]

To: [RESORT NAME]
[ADDRESS FROM CONTRACT]

RE: NOTICE OF CANCELLATION / RESCISSION
Contract Number: [CONTRACT NUMBER]
Purchase Date: [DATE SIGNED]
Owner Name(s): [YOUR NAME(S)]

Dear Sir/Madam:

Pursuant to [STATE] law and the terms of the above-referenced contract, I hereby
exercise my right to rescind and cancel the timeshare purchase agreement.

I am canceling within the statutory rescission period and demand:
1. Full refund of all monies paid: $[AMOUNT]
2. Return of any trade-in or exchange property
3. Cancellation of any financing agreements
4. Written confirmation of this cancellation

This cancellation is effective immediately upon mailing of this notice.
Please process my refund within 20 days as required by law.

Sincerely,

[YOUR SIGNATURE]
[YOUR PRINTED NAME]
[YOUR ADDRESS]
[YOUR PHONE]

KEEP THE CERTIFIED MAIL RECEIPT - THIS IS YOUR PROOF"""

    return {
        "overall_risk": "high" if risk_score >= 60 else "medium",
        "risk_score": min(100, risk_score),
        "resort_name": None,
        "ownership_type": ownership_type,
        "has_perpetuity_clause": has_perpetuity_clause,
        "rescission_deadline": rescission_deadline,
        "estimated_10yr_cost": estimated_10yr_cost,
        "red_flags": red_flags,
        "exit_options": exit_options,
        "summary": summary,
        "rescission_letter": rescission_letter
    }


@app.post("/api/analyze-timeshare", response_model=TimeshareContractReport)
async def analyze_timeshare_contract(input: TimeshareContractInput):
    """Analyze a timeshare contract"""
    try:
        if MOCK_MODE:
            result = mock_timeshare_analysis(
                input.contract_text,
                input.state,
                input.purchase_price,
                input.annual_fee
            )
            save_upload("timeshare", input.contract_text, input.state, result)
            return TimeshareContractReport(**result)

        client = get_client()

        rescission_info = TIMESHARE_RESCISSION.get(input.state.upper() if input.state else "", {})

        prompt = f"""You are a consumer protection expert analyzing a timeshare contract.

Your job is to help someone understand what they're getting into (or help them get out).

CONTRACT:
{input.contract_text[:15000]}

STATE: {input.state or "Not specified"}
RESCISSION PERIOD: {json.dumps(rescission_info)}
PURCHASE PRICE: {f"${input.purchase_price:,}" if input.purchase_price else "Unknown"}
ANNUAL FEE: {f"${input.annual_fee:,}" if input.annual_fee else "Unknown"}

Return JSON:
{{
    "overall_risk": "high" | "medium" | "low",
    "risk_score": 0-100 (timeshares are usually 60+),
    "resort_name": "Name if found",
    "ownership_type": "deeded" | "right_to_use" | "points" | "unknown",
    "has_perpetuity_clause": true/false,
    "rescission_deadline": "X days" or null,
    "estimated_10yr_cost": "$XX,XXX" with fee increases,
    "red_flags": [{{
        "name": "Issue",
        "severity": "critical" | "warning" | "info",
        "clause_text": "Actual text",
        "explanation": "Plain language, direct impact",
        "protection": "What to do"
    }}],
    "exit_options": ["Ranked list of exit options"],
    "summary": "2-3 sentences - be direct about the risks",
    "rescission_letter": "Template letter to cancel if within rescission period"
}}

Be blunt. 85% of timeshare buyers regret their purchase.
Return ONLY valid JSON."""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("timeshare", input.contract_text, input.state, result)
        return TimeshareContractReport(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeshare contract analysis failed: {str(e)}")


# ============== INSURANCE POLICY ANALYSIS ==============

class InsurancePolicyRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    what_to_ask: str

class InsurancePolicyInput(BaseModel):
    policy_text: str
    policy_type: Optional[str] = None  # "auto", "home", "renters", "health"
    state: Optional[str] = None

class InsurancePolicyReport(BaseModel):
    overall_risk: str
    risk_score: int
    policy_type: str
    carrier: Optional[str]
    coverage_type: str  # "named_perils", "open_perils", "unknown"
    valuation_method: str  # "actual_cash_value", "replacement_cost", "unknown"
    deductible_type: str  # "flat", "percentage", "unknown"
    has_arbitration: bool
    red_flags: list[InsurancePolicyRedFlag]
    coverage_gaps: list[str]
    summary: str
    questions_for_agent: str


def mock_insurance_policy_analysis(policy_text: str, policy_type: str = None, state: str = None) -> dict:
    """Generate mock insurance policy analysis"""
    text_lower = policy_text.lower()

    red_flags = []
    risk_score = 30
    coverage_gaps = []

    # Determine policy type
    if not policy_type:
        if 'auto' in text_lower or 'vehicle' in text_lower:
            policy_type = "auto"
        elif 'homeowner' in text_lower or 'dwelling' in text_lower:
            policy_type = "home"
        elif 'renter' in text_lower or 'tenant' in text_lower:
            policy_type = "renters"
        elif 'health' in text_lower or 'medical' in text_lower:
            policy_type = "health"
        else:
            policy_type = "unknown"

    # Check valuation method
    valuation_method = "unknown"
    if 'actual cash value' in text_lower:
        valuation_method = "actual_cash_value"
        red_flags.append({
            "name": "Actual Cash Value Coverage",
            "severity": "warning",
            "clause_text": "We will pay the actual cash value of the damaged property...",
            "explanation": "They deduct depreciation. A 10-year-old roof worth $10K to replace might only pay out $5K.",
            "what_to_ask": "Ask about upgrading to Replacement Cost coverage. It costs more but pays full replacement value."
        })
        risk_score += 15
    elif 'replacement cost' in text_lower:
        valuation_method = "replacement_cost"

    # Check for ACC clause
    if 'concurrent' in text_lower and 'sequence' in text_lower:
        red_flags.append({
            "name": "Anti-Concurrent Causation Clause",
            "severity": "critical",
            "clause_text": "...whether or not any other cause or event contributes concurrently or in any sequence...",
            "explanation": "If wind (covered) and flood (excluded) both cause damage, your ENTIRE claim can be denied.",
            "what_to_ask": "This is standard but dangerous. Ask about flood insurance if you're in a flood-prone area."
        })
        risk_score += 20
        if state and state.upper() in ['CA', 'ND', 'WA', 'WV']:
            red_flags[-1]["explanation"] += f" Good news: {state.upper()} may not enforce ACC clauses."

    # Check deductible type
    deductible_type = "unknown"
    if '%' in text_lower and ('hurricane' in text_lower or 'wind' in text_lower or 'hail' in text_lower):
        deductible_type = "percentage"
        red_flags.append({
            "name": "Percentage Deductible",
            "severity": "critical",
            "clause_text": "Hurricane deductible: 5% of Coverage A...",
            "explanation": "5% deductible on a $300K home = $15,000 out of pocket before insurance pays anything.",
            "what_to_ask": "Ask about switching to a flat deductible if available. Calculate worst-case out-of-pocket."
        })
        risk_score += 20
    else:
        deductible_type = "flat"

    # Check coverage type
    coverage_type = "unknown"
    if 'open perils' in text_lower or 'all risk' in text_lower:
        coverage_type = "open_perils"
    elif 'named perils' in text_lower or 'specified perils' in text_lower:
        coverage_type = "named_perils"
        red_flags.append({
            "name": "Named Perils Coverage",
            "severity": "warning",
            "clause_text": "We insure against direct physical loss caused by the following perils...",
            "explanation": "Only listed events are covered. If something happens that's not on the list, you're not covered.",
            "what_to_ask": "Ask about upgrading to Open Perils/All Risk coverage."
        })
        risk_score += 10

    # Check for arbitration
    has_arbitration = 'arbitration' in text_lower
    if has_arbitration:
        red_flags.append({
            "name": "Mandatory Arbitration",
            "severity": "warning",
            "clause_text": "Any disputes shall be resolved through binding arbitration...",
            "explanation": "You can't sue in court if they deny your claim. Arbitration often favors insurers.",
            "what_to_ask": "Check if you can opt out. Note this for if you ever have a claim dispute."
        })
        risk_score += 10

    # Check for common exclusions
    exclusion_checks = [
        ("flood", "Flood Damage", "home"),
        ("earthquake", "Earthquake Damage", "home"),
        ("mold", "Mold Damage", "home"),
        ("sewer backup", "Sewer Backup", "home"),
        ("ordinance", "Building Code Upgrades", "home"),
        ("business use", "Business Use of Vehicle", "auto"),
        ("rideshare", "Rideshare/Delivery", "auto"),
    ]

    for keyword, name, applies_to in exclusion_checks:
        if (policy_type == applies_to or applies_to == "all") and keyword in text_lower and 'exclud' in text_lower:
            coverage_gaps.append(f"{name} excluded - may need separate coverage")

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        summary = f"This policy has {critical_count} critical issue(s) that could result in claim denials. "
    else:
        summary = "This policy has standard terms, but understand your coverage limits. "

    if coverage_gaps:
        summary += f"There are {len(coverage_gaps)} potential coverage gaps to address."

    # Generate questions
    questions = """QUESTIONS TO ASK YOUR INSURANCE AGENT:

1. VALUATION
   - "Is this Actual Cash Value or Replacement Cost?"
   - "Can I upgrade to Replacement Cost?"

2. DEDUCTIBLES
   - "What's my deductible for [hurricane/wind/hail]?"
   - "Is it a flat amount or percentage?"
   - "What's my maximum out-of-pocket for a claim?"

3. EXCLUSIONS
   - "What's NOT covered by this policy?"
   - "Do I need separate flood/earthquake coverage?"
   - "Is sewer backup covered?"

4. CLAIM PROCESS
   - "What's the claim filing deadline?"
   - "What documentation do I need after a loss?"
   - "Is there mandatory arbitration?"

5. DISCOUNTS
   - "Are there discounts I'm not getting?"
   - "Would bundling save me money?"

AFTER A LOSS:
- Document everything with photos/video
- Don't throw anything away until adjuster sees it
- Get multiple repair estimates
- Know that first offer is often negotiable
"""

    return {
        "overall_risk": "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low",
        "risk_score": min(100, risk_score),
        "policy_type": policy_type,
        "carrier": None,
        "coverage_type": coverage_type,
        "valuation_method": valuation_method,
        "deductible_type": deductible_type,
        "has_arbitration": has_arbitration,
        "red_flags": red_flags,
        "coverage_gaps": coverage_gaps,
        "summary": summary,
        "questions_for_agent": questions
    }


@app.post("/api/analyze-insurance-policy", response_model=InsurancePolicyReport)
async def analyze_insurance_policy(input: InsurancePolicyInput):
    """Analyze a consumer insurance policy"""
    try:
        if MOCK_MODE:
            result = mock_insurance_policy_analysis(input.policy_text, input.policy_type, input.state)
            save_upload("insurance_policy", input.policy_text, input.state, result)
            return InsurancePolicyReport(**result)

        client = get_client()

        prompt = f"""You are an insurance expert helping a consumer understand their policy.

POLICY TEXT:
{input.policy_text[:15000]}

POLICY TYPE: {input.policy_type or "Determine from text"}
STATE: {input.state or "Not specified"}

Return JSON:
{{
    "overall_risk": "high" | "medium" | "low",
    "risk_score": 0-100,
    "policy_type": "auto" | "home" | "renters" | "health" | "unknown",
    "carrier": "Name if found",
    "coverage_type": "named_perils" | "open_perils" | "unknown",
    "valuation_method": "actual_cash_value" | "replacement_cost" | "unknown",
    "deductible_type": "flat" | "percentage" | "unknown",
    "has_arbitration": true/false,
    "red_flags": [{{
        "name": "Issue",
        "severity": "critical" | "warning" | "info",
        "clause_text": "Actual policy text",
        "explanation": "What this means in plain language",
        "what_to_ask": "Question to ask your agent"
    }}],
    "coverage_gaps": ["List of potential gaps"],
    "summary": "2-3 sentences",
    "questions_for_agent": "Questions to ask your insurance agent"
}}

Focus on exclusions, deductibles, and valuation method.
Return ONLY valid JSON."""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("insurance_policy", input.policy_text, input.state, result)
        return InsurancePolicyReport(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insurance policy analysis failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
