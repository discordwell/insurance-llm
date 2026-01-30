from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import anthropic
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check if we're in mock mode (for testing without API key)
MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"

# Try to find API key from multiple sources
def get_api_key():
    # 1. Environment variable
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # 2. .env file in current directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key:
                        return key

    # 3. Home directory config
    home_config = Path.home() / ".anthropic" / "api_key"
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
                detail="ANTHROPIC_API_KEY not configured. Set it in environment, .env file, or ~/.anthropic/api_key"
            )
        _client = anthropic.Anthropic(api_key=api_key)
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

class ExtractedPolicy(BaseModel):
    insured_name: Optional[str] = None
    policy_number: Optional[str] = None
    carrier: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    coverages: list[Coverage] = []
    total_premium: Optional[str] = None
    exclusions: list[str] = []
    special_conditions: list[str] = []
    risk_score: Optional[int] = None
    compliance_issues: list[str] = []
    summary: Optional[str] = None

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
        message = get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        response_text = message.content[0].text
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
        message = get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": comparison_prompt}]
        )

        response_text = message.content[0].text
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
        message = get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": proposal_prompt}]
        )

        return {"proposal": message.content[0].text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
