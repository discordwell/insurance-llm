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
