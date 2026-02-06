def mock_lease_analysis(lease_text: str, state: str = None) -> dict:
    """Generate mock lease analysis for testing"""
    text_lower = lease_text.lower()

    red_flags = []
    insurance_requirements = []
    risk_score = 50

    # Check for common red flags
    if 'indemnify' in text_lower and 'hold harmless' in text_lower:
        if 'negligence' not in text_lower or 'except' not in text_lower:
            red_flags.append({
                "name": "Blanket Indemnification",
                "severity": "critical",
                "clause_text": "Tenant shall indemnify and hold harmless Landlord from any and all claims...",
                "explanation": "You're agreeing to pay for the landlord's mistakes, not just your own. If someone slips on ice the landlord should have salted, you could be on the hook.",
                "protection": "Add: 'except to the extent caused by Landlord's negligence or willful misconduct'"
            })
            risk_score += 20

    if 'additional insured' in text_lower:
        red_flags.append({
            "name": "Additional Insured Requirement",
            "severity": "warning",
            "clause_text": "Tenant shall name Landlord as Additional Insured on all liability policies...",
            "explanation": "The landlord gets to use YOUR insurance policy limits. If they use $500K defending a lawsuit, you only have $500K left for your own claims.",
            "protection": "Increase your liability limits. Negotiate to exclude coverage for landlord's sole negligence."
        })
        insurance_requirements.append({
            "clause_type": "additional_insured",
            "original_text": "Landlord shall be named as Additional Insured",
            "summary": "You must add the landlord to your insurance policy",
            "risk_level": "medium",
            "explanation": "Landlord shares your policy limits",
            "recommendation": "Increase liability limits to $2M+ to account for sharing"
        })
        risk_score += 10

    if 'waiver of subrogation' in text_lower or 'waive subrogation' in text_lower:
        red_flags.append({
            "name": "Waiver of Subrogation",
            "severity": "warning",
            "clause_text": "Tenant waives all rights of subrogation against Landlord...",
            "explanation": "If the landlord's negligence causes a fire that destroys your business, your insurance pays you but CAN'T sue the landlord to recover. You eat the deductibles and coverage gaps.",
            "protection": "Make sure it's mutual. Get the endorsement on your policy. Negotiate carve-outs for gross negligence."
        })
        risk_score += 10

    if 'primary and non-contributory' in text_lower:
        red_flags.append({
            "name": "Primary and Non-Contributory",
            "severity": "warning",
            "clause_text": "Tenant's insurance shall be primary and non-contributory...",
            "explanation": "Your insurance pays FIRST, even if it's the landlord's fault. Their insurance sits back and watches yours get depleted.",
            "protection": "Resist this language if possible. If required, significantly increase your limits."
        })
        risk_score += 15

    if 'not be liable' in text_lower or 'not responsible' in text_lower:
        red_flags.append({
            "name": "Landlord Not Liable",
            "severity": "critical",
            "clause_text": "Landlord shall not be liable for any damage to Tenant's property...",
            "explanation": "The landlord is trying to avoid ALL liability, even for their own negligence. This may not be enforceable, but you'll have to fight it in court.",
            "protection": "Add: 'except for damage caused by Landlord's negligence or willful misconduct'"
        })
        risk_score += 15

    # Check for missing protections
    missing = []
    if 'abatement' not in text_lower and 'abate' not in text_lower:
        missing.append("Rent abatement during periods when premises are unusable")
        risk_score += 10

    if 'terminate' not in text_lower or ('landlord may terminate' in text_lower and 'tenant may terminate' not in text_lower):
        missing.append("Tenant termination right if repairs take too long")
        risk_score += 10

    # Add some basic insurance requirements if found
    if '$1,000,000' in lease_text or '$1M' in text_lower:
        insurance_requirements.append({
            "clause_type": "gl_requirement",
            "original_text": "Commercial General Liability: $1,000,000 per occurrence",
            "summary": "You need at least $1M in general liability coverage",
            "risk_level": "low",
            "explanation": "This is a standard commercial requirement",
            "recommendation": "Make sure your policy meets or exceeds this limit"
        })

    if '$2,000,000' in lease_text or '$2M' in text_lower:
        insurance_requirements.append({
            "clause_type": "gl_aggregate",
            "original_text": "General Aggregate: $2,000,000",
            "summary": "Your policy needs $2M aggregate limit",
            "risk_level": "low",
            "explanation": "Standard aggregate for commercial leases",
            "recommendation": "Verify your policy's aggregate limit"
        })

    # Cap risk score
    risk_score = min(100, risk_score)

    # Determine overall risk
    if risk_score >= 70:
        overall_risk = "high"
    elif risk_score >= 40:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    warning_count = len([r for r in red_flags if r['severity'] == 'warning'])

    if critical_count > 0:
        summary = f"This lease has {critical_count} critical issues that could expose you to significant liability. "
    else:
        summary = "This lease has some concerning provisions but no critical red flags. "

    if missing:
        summary += f"It's also missing {len(missing)} standard tenant protections."

    # Generate negotiation letter
    letter_items = []
    for rf in red_flags:
        if rf['severity'] == 'critical':
            letter_items.append(f"- {rf['name']}: {rf['protection']}")

    for missing_item in missing[:3]:
        letter_items.append(f"- Add: {missing_item}")

    letter = f"""RE: Lease Insurance and Liability Terms - Requested Modifications

Dear Landlord,

We have reviewed the proposed lease agreement and identified several provisions that require modification before we can proceed:

REQUESTED CHANGES:
{chr(10).join(letter_items) if letter_items else '- No critical changes required'}

These modifications reflect standard commercial practice and appropriate risk allocation between landlord and tenant. We believe these changes are reasonable and look forward to discussing them.

Please provide a revised lease addressing these items within 10 business days.

Best regards,
[Tenant Name]
"""

    return {
        "overall_risk": overall_risk,
        "risk_score": risk_score,
        "lease_type": "commercial" if 'commercial' in text_lower else "residential",
        "landlord_name": None,
        "tenant_name": None,
        "property_address": None,
        "lease_term": None,
        "insurance_requirements": insurance_requirements,
        "red_flags": red_flags,
        "missing_protections": missing,
        "summary": summary,
        "negotiation_letter": letter
    }
