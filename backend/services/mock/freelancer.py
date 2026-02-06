def mock_freelancer_analysis(contract_text: str, project_value: int = None) -> dict:
    """Generate mock freelancer contract analysis"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 25
    missing_protections = []

    # Payment terms
    payment_terms = None
    if 'net 90' in text_lower:
        payment_terms = "Net 90"
        red_flags.append({
            "name": "Net 90 Payment Terms",
            "severity": "critical",
            "clause_text": "Payment due within 90 days of invoice...",
            "explanation": "You're waiting 3 months to get paid. That's a loan to your client.",
            "protection": "Counter with Net-30 maximum. Require 50% deposit upfront."
        })
        risk_score += 25
    elif 'net 60' in text_lower:
        payment_terms = "Net 60"
        red_flags.append({
            "name": "Net 60 Payment Terms",
            "severity": "warning",
            "clause_text": "Payment due within 60 days...",
            "explanation": "Two months is a long time to wait for your money.",
            "protection": "Counter with Net-30. Request deposit for large projects."
        })
        risk_score += 15
    elif 'net 30' in text_lower:
        payment_terms = "Net 30"

    # IP ownership
    ip_ownership = "unclear"
    if 'work for hire' in text_lower or 'work made for hire' in text_lower:
        ip_ownership = "work_for_hire"
        red_flags.append({
            "name": "Work For Hire",
            "severity": "warning",
            "clause_text": "All work product shall be considered work made for hire...",
            "explanation": "Client owns everything from the moment you create it. You can't use it in your portfolio without permission.",
            "protection": "Ensure you retain portfolio rights. If giving up all rights, charge a premium (2-3x)."
        })
        risk_score += 10
    elif 'assigns all' in text_lower or 'assign all rights' in text_lower:
        ip_ownership = "assignment"
        risk_score += 10

    # Kill fee
    has_kill_fee = 'kill fee' in text_lower or 'cancellation fee' in text_lower
    if not has_kill_fee and 'cancel' not in text_lower:
        missing_protections.append("No kill fee - client can cancel without paying")
        risk_score += 15

    # Revisions
    revision_limit = None
    if 'unlimited revision' in text_lower:
        revision_limit = "Unlimited"
        red_flags.append({
            "name": "Unlimited Revisions",
            "severity": "critical",
            "clause_text": "Contractor shall provide unlimited revisions until Client approval...",
            "explanation": "You could be revising forever. There's no end to this.",
            "protection": "Negotiate 2-3 revision rounds. Additional revisions at hourly rate."
        })
        risk_score += 25

    # Non-compete
    if 'non-compete' in text_lower or 'not compete' in text_lower:
        red_flags.append({
            "name": "Non-Compete Clause",
            "severity": "critical",
            "clause_text": "Contractor shall not provide services to competitors...",
            "explanation": "This could prevent you from working with other clients in this industry.",
            "protection": "Resist non-competes. If required, limit to specific named companies and short duration."
        })
        risk_score += 20

    # Indemnification
    if 'indemnify' in text_lower and 'hold harmless' in text_lower:
        red_flags.append({
            "name": "One-Sided Indemnification",
            "severity": "warning",
            "clause_text": "Contractor shall indemnify and hold harmless Client...",
            "explanation": "You may be on the hook for the client's problems, not just your own.",
            "protection": "Make indemnification mutual. Cap liability at fees paid."
        })
        risk_score += 10

    # Missing protections
    if 'deposit' not in text_lower and 'milestone' not in text_lower:
        missing_protections.append("No deposit or milestone payments")
    if 'late fee' not in text_lower and 'interest' not in text_lower:
        missing_protections.append("No late payment penalties")
    if 'portfolio' not in text_lower and 'display' not in text_lower:
        missing_protections.append("No portfolio rights mentioned")

    # Determine contract type
    if 'statement of work' in text_lower or 'sow' in text_lower:
        contract_type = "sow"
    elif 'retainer' in text_lower:
        contract_type = "retainer"
    else:
        contract_type = "project"

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        summary = f"This contract has {critical_count} critical issue(s) that could seriously hurt you. "
    else:
        summary = "This contract has some concerning terms but nothing catastrophic. "

    if missing_protections:
        summary += f"It's also missing {len(missing_protections)} standard protections."

    # Generate suggestions
    suggestions = """CHANGES TO REQUEST:

"""
    if payment_terms in ["Net 60", "Net 90"]:
        suggestions += """1. PAYMENT TERMS
   - Change to Net-30 maximum
   - Add: "50% deposit due upon signing"
   - Add: "Late payments incur 1.5% monthly interest"

"""
    if not has_kill_fee:
        suggestions += """2. KILL FEE
   - Add: "If Client cancels after work begins, Client shall pay:
     - 25% of total if cancelled before delivery
     - 50% of total if cancelled after partial delivery
     - 100% of total if cancelled after full delivery"

"""
    if revision_limit == "Unlimited":
        suggestions += """3. REVISION LIMITS
   - Change to: "This agreement includes 2 rounds of revisions.
     Additional revisions billed at $[X]/hour."

"""
    if ip_ownership == "work_for_hire":
        suggestions += """4. PORTFOLIO RIGHTS
   - Add: "Contractor retains the right to display final deliverables
     in portfolio and self-promotional materials after public release."

"""
    suggestions += """GENERAL TIPS:
- Never start work without a signed contract
- Get deposit before starting large projects
- Keep records of all deliveries and communications
- Invoice immediately upon delivery
"""

    return {
        "overall_risk": "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low",
        "risk_score": min(100, risk_score),
        "contract_type": contract_type,
        "payment_terms": payment_terms,
        "ip_ownership": ip_ownership,
        "has_kill_fee": has_kill_fee,
        "revision_limit": revision_limit,
        "red_flags": red_flags,
        "missing_protections": missing_protections,
        "summary": summary,
        "suggested_changes": suggestions
    }
