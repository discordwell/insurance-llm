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

def mock_compliance_check(coi_data: dict, requirements: dict) -> dict:
    """Generate mock compliance check for testing"""
    critical_gaps = []
    warnings = []
    passed = []

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
            result = mock_compliance_check(coi_data, requirements)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
