# Note: This prompt is constructed as an f-string in the endpoint.
# Extracted here as a template string with {placeholders} for .format() usage.

INSURANCE_POLICY_ANALYSIS_PROMPT = """You are an insurance expert helping a consumer understand their policy.

POLICY TEXT:
{policy_text}

POLICY TYPE: {policy_type}
STATE: {state}

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
