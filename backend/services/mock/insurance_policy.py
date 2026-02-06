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
