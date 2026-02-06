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
