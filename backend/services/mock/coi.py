import re

from data.states import (
    STATE_WORKERS_COMP,
    STATE_ANTI_INDEMNITY,
    STATE_GL_REQUIREMENTS,
    STATE_AUTO_MINIMUMS,
)


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
    gl_per_occ_value = coi_data.get('gl_limit_per_occurrence') or 'Not specified'
    if coi_limit >= req_limit:
        passed.append({
            "name": "GL Per Occurrence Limit",
            "required_value": f"${req_limit:,}",
            "actual_value": gl_per_occ_value,
            "status": "pass",
            "explanation": "Limit meets or exceeds requirement"
        })
    else:
        critical_gaps.append({
            "name": "GL Per Occurrence Limit",
            "required_value": f"${req_limit:,}",
            "actual_value": gl_per_occ_value,
            "status": "fail",
            "explanation": f"INADEQUATE COVERAGE: Limit is ${coi_limit:,} but contract requires ${req_limit:,}. This leaves a ${req_limit - coi_limit:,} gap in coverage."
        })

    # Check GL aggregate
    coi_agg = parse_limit_to_number(coi_data.get('gl_limit_aggregate', '') or '')
    req_agg = requirements.get('gl_aggregate', 2000000)
    gl_agg_value = coi_data.get('gl_limit_aggregate') or 'Not specified'
    if coi_agg >= req_agg:
        passed.append({
            "name": "GL Aggregate Limit",
            "required_value": f"${req_agg:,}",
            "actual_value": gl_agg_value,
            "status": "pass",
            "explanation": "Aggregate limit meets or exceeds requirement"
        })
    else:
        critical_gaps.append({
            "name": "GL Aggregate Limit",
            "required_value": f"${req_agg:,}",
            "actual_value": gl_agg_value,
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
