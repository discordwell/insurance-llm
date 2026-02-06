from data.states import STATE_GYM_PROTECTIONS


def mock_gym_analysis(contract_text: str, state: str = None) -> dict:
    """Generate mock gym contract analysis for testing"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 30

    # Check for red flags
    if 'in person' in text_lower or 'visit' in text_lower and 'cancel' in text_lower:
        red_flags.append({
            "name": "In-Person Cancellation Only",
            "severity": "critical",
            "clause_text": "Cancellation requests must be made in person at your home club location...",
            "explanation": "You can only cancel by physically going to the gym. The FTC sued LA Fitness for this exact practice in August 2025.",
            "protection": "Check your state laws. Many states require alternative cancellation methods. Send certified mail anyway and keep records."
        })
        risk_score += 25

    if 'certified mail' in text_lower:
        red_flags.append({
            "name": "Certified Mail Required",
            "severity": "warning",
            "clause_text": "Written notice via certified mail to our corporate office...",
            "explanation": "They want you to go to the post office and pay for certified mail just to cancel.",
            "protection": "Do it. Keep the receipt. It's your proof they received it."
        })
        risk_score += 10

    if 'automatically renew' in text_lower or 'auto-renew' in text_lower:
        red_flags.append({
            "name": "Automatic Renewal Trap",
            "severity": "warning",
            "clause_text": "This agreement will automatically renew for successive monthly terms...",
            "explanation": "Your membership keeps going forever unless you actively cancel during the right window.",
            "protection": "Set calendar reminders 60 days before any renewal date. Know the exact cancellation window."
        })
        risk_score += 15

    if 'annual fee' in text_lower or 'enhancement fee' in text_lower:
        red_flags.append({
            "name": "Hidden Annual Fee",
            "severity": "warning",
            "clause_text": "Annual Enhancement Fee of $49.99 will be charged on...",
            "explanation": "This is on TOP of your monthly dues. They sneak it in once a year.",
            "protection": "Add this to your total annual cost calculation. Ask when it's charged so it doesn't surprise you."
        })
        risk_score += 10

    if 'arbitration' in text_lower:
        red_flags.append({
            "name": "Forced Arbitration",
            "severity": "warning",
            "clause_text": "Any disputes shall be resolved through binding arbitration...",
            "explanation": "You can't sue them or join a class action. Arbitration typically favors the company.",
            "protection": "Look for opt-out provisions. Some contracts let you opt out within 30 days."
        })
        risk_score += 10

    if 'early termination' in text_lower or 'buyout' in text_lower:
        red_flags.append({
            "name": "Early Termination Fee",
            "severity": "warning",
            "clause_text": "Early termination requires payment of remaining contract balance...",
            "explanation": "Want out early? That'll cost you. Could be hundreds of dollars.",
            "protection": "Check your state's limits on these fees. Some states cap them."
        })
        risk_score += 15

    # Check for missing protections
    if 'freeze' not in text_lower and 'pause' not in text_lower:
        red_flags.append({
            "name": "No Freeze Option Mentioned",
            "severity": "info",
            "clause_text": None,
            "explanation": "The contract doesn't mention freezing your membership. If you get injured or travel, you may keep paying.",
            "protection": "Ask about freeze policies before signing. Most gyms offer this but hide it."
        })
        risk_score += 5

    # Get state protections
    state_protections = []
    if state and state.upper() in STATE_GYM_PROTECTIONS:
        state_info = STATE_GYM_PROTECTIONS[state.upper()]
        state_protections.append(f"Cooling-off period: {state_info.get('cooling_off', 'Check local laws')}")
        if 'relocation_cancel' in state_info:
            state_protections.append(f"Relocation cancellation: {state_info['relocation_cancel']}")
        if 'max_term' in state_info:
            state_protections.append(f"Maximum contract term: {state_info['max_term']}")
        if 'notes' in state_info:
            state_protections.append(state_info['notes'])

    # Determine difficulty
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        cancellation_difficulty = "nightmare"
    elif risk_score >= 60:
        cancellation_difficulty = "hard"
    elif risk_score >= 40:
        cancellation_difficulty = "moderate"
    else:
        cancellation_difficulty = "easy"

    # Determine contract type
    if 'month-to-month' in text_lower or 'monthly' in text_lower and 'no commitment' in text_lower:
        contract_type = "month-to-month"
    elif '12 month' in text_lower or 'one year' in text_lower or 'annual' in text_lower:
        contract_type = "annual"
    elif '24 month' in text_lower or 'two year' in text_lower:
        contract_type = "multi-year"
    else:
        contract_type = "unknown"

    # Generate summary
    if critical_count > 0:
        summary = f"This gym contract is designed to trap you. {critical_count} critical issue(s) will make cancellation extremely difficult. "
    elif risk_score >= 50:
        summary = "This contract has several concerning clauses that could cost you money or make cancellation difficult. "
    else:
        summary = "This contract is relatively standard, but watch the renewal terms. "

    summary += f"Cancellation difficulty: {cancellation_difficulty.upper()}."

    # Generate cancellation guide
    guide = """HOW TO CANCEL THIS GYM MEMBERSHIP:

1. CHECK YOUR STATE LAWS
   - Look up your state's gym membership laws
   - Know your cooling-off period (often 3-5 days)
   - Check if your state requires alternative cancellation methods

2. DOCUMENT EVERYTHING
   - Screenshot all contract terms
   - Save all payment receipts
   - Record dates of all communication

3. SEND WRITTEN NOTICE
   - Even if they say "in person only", send certified mail
   - Include: name, member ID, request to cancel, effective date
   - Keep the certified mail receipt

4. FOLLOW UP
   - Call to confirm receipt
   - Get confirmation number/name of rep
   - Document the call

5. MONITOR YOUR ACCOUNTS
   - Watch for unauthorized charges after cancellation
   - Dispute any post-cancellation charges with your bank
   - File complaints with your state AG if they keep charging

6. IF THEY WON'T STOP:
   - File complaint: State Attorney General
   - File complaint: FTC (ReportFraud.ftc.gov)
   - File complaint: BBB
   - Consider credit card chargeback for unauthorized charges
"""

    return {
        "overall_risk": "high" if risk_score >= 60 else "medium" if risk_score >= 40 else "low",
        "risk_score": min(100, risk_score),
        "gym_name": None,
        "contract_type": contract_type,
        "monthly_fee": None,
        "cancellation_difficulty": cancellation_difficulty,
        "red_flags": red_flags,
        "state_protections": state_protections,
        "summary": summary,
        "cancellation_guide": guide
    }
