from data.states import TIMESHARE_RESCISSION


def mock_timeshare_analysis(contract_text: str, state: str = None, purchase_price: int = None, annual_fee: int = None) -> dict:
    """Generate mock timeshare contract analysis"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 60  # Timeshares start with high risk

    # Check for perpetuity clause
    has_perpetuity_clause = 'perpetuity' in text_lower or 'heirs' in text_lower or 'forever' in text_lower or 'successors' in text_lower
    if has_perpetuity_clause:
        red_flags.append({
            "name": "Perpetuity Clause",
            "severity": "critical",
            "clause_text": "This agreement shall be binding upon Owner's heirs, successors, and assigns in perpetuity...",
            "explanation": "This obligation NEVER ENDS. It passes to your kids when you die. They inherit your debt.",
            "protection": "This is nearly impossible to exit. Only 15% of buyers use rescission period. If you just signed, CANCEL NOW."
        })
        risk_score += 20

    # Check ownership type
    ownership_type = "unknown"
    if 'deeded' in text_lower or 'fee simple' in text_lower:
        ownership_type = "deeded"
        red_flags.append({
            "name": "Deeded Ownership",
            "severity": "warning",
            "clause_text": "Owner receives an undivided fractional interest in fee simple...",
            "explanation": "You own a fraction of real property - which sounds good but means perpetual obligations and harder exit.",
            "protection": "Deeded ownership is harder to escape than right-to-use."
        })
        risk_score += 10
    elif 'right to use' in text_lower or 'license' in text_lower:
        ownership_type = "right_to_use"
        # RTU is slightly better - it expires
    elif 'points' in text_lower:
        ownership_type = "points"

    # Check for uncapped maintenance fees
    if 'maintenance' in text_lower:
        if 'increase' in text_lower or 'adjust' in text_lower:
            red_flags.append({
                "name": "Uncapped Maintenance Fees",
                "severity": "critical",
                "clause_text": "Maintenance fees are subject to annual adjustment...",
                "explanation": "Fees increase 3-8% EVERY YEAR. Average is $1,480/year. In 10 years that could be over $2,000/year.",
                "protection": "There is no protection. This is how timeshares work. Budget for 50% increase over 10 years."
            })
            risk_score += 15

    # Check for special assessments
    if 'special assessment' in text_lower:
        red_flags.append({
            "name": "Special Assessment Authority",
            "severity": "critical",
            "clause_text": "The Association may levy special assessments...",
            "explanation": "They can hit you with surprise bills of $1,000-$3,000+ for 'improvements' or repairs.",
            "protection": "There is no protection. You must pay or face collection/credit damage."
        })
        risk_score += 10

    # Check for rescission period
    rescission_deadline = None
    if state and state.upper() in TIMESHARE_RESCISSION:
        rescission_info = TIMESHARE_RESCISSION[state.upper()]
        rescission_deadline = f"{rescission_info['days']} {rescission_info['type']} days"
        red_flags.append({
            "name": f"Rescission Period: {rescission_deadline}",
            "severity": "info",
            "clause_text": None,
            "explanation": f"You have {rescission_info['days']} {rescission_info['type']} days to cancel and get your money back. After that, you're stuck.",
            "protection": "CANCEL NOW if you're having second thoughts. Send certified mail TODAY."
        })

    # Calculate 10-year cost
    estimated_10yr_cost = None
    if purchase_price and annual_fee:
        # Assume 5% annual fee increase
        total_fees = sum([annual_fee * (1.05 ** year) for year in range(10)])
        total_cost = purchase_price + total_fees
        estimated_10yr_cost = f"${total_cost:,.0f}"
        if total_cost > 50000:
            red_flags.append({
                "name": f"10-Year Cost: {estimated_10yr_cost}",
                "severity": "critical",
                "clause_text": None,
                "explanation": f"Purchase (${purchase_price:,}) + 10 years of fees = {estimated_10yr_cost}. You could take a LOT of vacations for that money.",
                "protection": "Do the math. Compare to just booking hotels/vacation rentals."
            })

    # Integration clause
    if 'entire agreement' in text_lower or 'no representations' in text_lower:
        red_flags.append({
            "name": "Integration Clause (License to Lie)",
            "severity": "warning",
            "clause_text": "This Agreement constitutes the entire agreement... No representations or promises not contained herein shall be binding...",
            "explanation": "Everything the salesperson promised? Doesn't count. Only what's written in this contract matters.",
            "protection": "Get ALL verbal promises in writing BEFORE signing. If they won't, assume they were lying."
        })
        risk_score += 10

    # Generate exit options
    exit_options = []
    if rescission_deadline:
        exit_options.append(f"RESCISSION: Cancel within {rescission_deadline} via certified mail (FREE)")
    exit_options.append("DEVELOPER DEED-BACK: Contact developer's exit program (Wyndham Cares, Marriott, etc.) - $200-$1,000")
    exit_options.append("RESALE: RedWeek.com, TUG2.com - Expect to sell for $0-$1 just to transfer obligation")
    exit_options.append("ATTORNEY: For misrepresentation claims - $3,000-$7,000")
    exit_options.append("ARDA: Call (855) 939-1515 for exit assistance")
    exit_options.append("AVOID: Any 'exit company' demanding large upfront fees - likely a scam")

    # Generate summary
    summary = "Timeshares are designed to be nearly impossible to exit. "
    if has_perpetuity_clause:
        summary += "This one has a perpetuity clause - it passes to your heirs. "
    if rescission_deadline:
        summary += f"If you just signed, you have {rescission_deadline} to cancel FOR FREE. Do it now."
    else:
        summary += "After the rescission period, your options are very limited."

    # Generate rescission letter
    rescission_letter = f"""VIA CERTIFIED MAIL - RETURN RECEIPT REQUESTED

Date: [TODAY'S DATE]

To: [RESORT NAME]
[ADDRESS FROM CONTRACT]

RE: NOTICE OF CANCELLATION / RESCISSION
Contract Number: [CONTRACT NUMBER]
Purchase Date: [DATE SIGNED]
Owner Name(s): [YOUR NAME(S)]

Dear Sir/Madam:

Pursuant to [STATE] law and the terms of the above-referenced contract, I hereby
exercise my right to rescind and cancel the timeshare purchase agreement.

I am canceling within the statutory rescission period and demand:
1. Full refund of all monies paid: $[AMOUNT]
2. Return of any trade-in or exchange property
3. Cancellation of any financing agreements
4. Written confirmation of this cancellation

This cancellation is effective immediately upon mailing of this notice.
Please process my refund within 20 days as required by law.

Sincerely,

[YOUR SIGNATURE]
[YOUR PRINTED NAME]
[YOUR ADDRESS]
[YOUR PHONE]

KEEP THE CERTIFIED MAIL RECEIPT - THIS IS YOUR PROOF"""

    return {
        "overall_risk": "high" if risk_score >= 60 else "medium",
        "risk_score": min(100, risk_score),
        "resort_name": None,
        "ownership_type": ownership_type,
        "has_perpetuity_clause": has_perpetuity_clause,
        "rescission_deadline": rescission_deadline,
        "estimated_10yr_cost": estimated_10yr_cost,
        "red_flags": red_flags,
        "exit_options": exit_options,
        "summary": summary,
        "rescission_letter": rescission_letter
    }
