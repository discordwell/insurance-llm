from openai import OpenAI
from fastapi import HTTPException

from config import get_api_key, MOCK_MODE


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


def clean_llm_response(response_text: str) -> str:
    """Clean up potential markdown formatting from LLM JSON responses.

    Handles the common pattern where LLMs wrap JSON in ```json``` code blocks.
    """
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    return response_text.strip()


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
