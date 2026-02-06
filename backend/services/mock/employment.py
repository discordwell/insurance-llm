from data.states import NON_COMPETE_STATES


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
