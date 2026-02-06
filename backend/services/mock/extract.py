import re


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
