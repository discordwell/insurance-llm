def mock_influencer_analysis(contract_text: str, base_rate: int = None) -> dict:
    """Generate mock influencer contract analysis"""
    text_lower = contract_text.lower()

    red_flags = []
    risk_score = 25

    # Check for perpetual rights
    has_perpetual_rights = 'perpetuity' in text_lower or 'forever' in text_lower or 'unlimited duration' in text_lower
    if has_perpetual_rights:
        red_flags.append({
            "name": "Perpetual Usage Rights",
            "severity": "critical",
            "clause_text": "Brand is granted rights in perpetuity...",
            "explanation": "They can use your content FOREVER. No time limit. This should cost 3x your normal rate.",
            "protection": "Counter with 90-day usage. Perpetual rights = 100-150% premium minimum."
        })
        risk_score += 25

    # Check usage duration
    usage_rights_duration = None
    if has_perpetual_rights:
        usage_rights_duration = "Perpetual (FOREVER)"
    elif '12 month' in text_lower or 'one year' in text_lower:
        usage_rights_duration = "12 months"
        red_flags.append({
            "name": "12-Month Usage Rights",
            "severity": "warning",
            "clause_text": "Usage rights for 12 months from posting date...",
            "explanation": "A year is long. Standard is 30-90 days. This should cost more.",
            "protection": "Negotiate additional compensation for extended usage."
        })
        risk_score += 10
    elif '90 day' in text_lower or '3 month' in text_lower:
        usage_rights_duration = "90 days"

    # Check for AI training rights
    has_ai_training_rights = 'machine learning' in text_lower or 'ai training' in text_lower or 'artificial intelligence' in text_lower
    if has_ai_training_rights:
        red_flags.append({
            "name": "AI Training Rights",
            "severity": "critical",
            "clause_text": "Content may be used for machine learning or AI model training...",
            "explanation": "They want to feed your content to AI. Your likeness, voice, style could be replicated.",
            "protection": "Remove this clause entirely. This is a new and dangerous term."
        })
        risk_score += 20

    # Check exclusivity
    exclusivity_scope = None
    if 'exclusiv' in text_lower:
        if 'category' in text_lower:
            exclusivity_scope = "Category-wide"
        elif 'competitor' in text_lower:
            exclusivity_scope = "Named competitors"
        else:
            exclusivity_scope = "Broad/unclear"

        if 'including but not limited to' in text_lower:
            red_flags.append({
                "name": "Vague Exclusivity",
                "severity": "critical",
                "clause_text": "Creator shall not work with competitors including but not limited to...",
                "explanation": "'Including but not limited to' means they can block ANY deal they want. Total trap.",
                "protection": "Demand a specific named list of competitors. No 'including but not limited to.'"
            })
            risk_score += 20

    # Check FTC compliance
    ftc_compliance = "missing"
    if '#ad' in text_lower or 'disclose' in text_lower or 'ftc' in text_lower:
        ftc_compliance = "addressed"
    elif 'partner' in text_lower or 'sponsor' in text_lower:
        ftc_compliance = "unclear"
        red_flags.append({
            "name": "Unclear FTC Disclosure Terms",
            "severity": "warning",
            "clause_text": None,
            "explanation": "The contract doesn't clearly specify FTC disclosure requirements. You could be liable for fines.",
            "protection": "Add clear disclosure requirements. Use #ad or #sponsored. Both parties share responsibility."
        })
        risk_score += 10
    else:
        red_flags.append({
            "name": "No FTC Compliance Mentioned",
            "severity": "warning",
            "clause_text": None,
            "explanation": "No mention of disclosure requirements. FTC fines are $53,000+ per violation.",
            "protection": "Add disclosure clause. Specify who's responsible. You need this protection."
        })
        risk_score += 10

    # Check payment terms
    payment_terms = None
    if 'net 90' in text_lower:
        payment_terms = "Net 90"
        red_flags.append({
            "name": "Net 90 Payment",
            "severity": "critical",
            "clause_text": "Payment within 90 days of campaign completion...",
            "explanation": "Three months to get paid?! That's ridiculous. You've already done the work.",
            "protection": "Counter with Net-30. Request 50% upfront."
        })
        risk_score += 20
    elif 'net 60' in text_lower:
        payment_terms = "Net 60"
        risk_score += 10

    # Check revisions
    if 'unlimited revision' in text_lower:
        red_flags.append({
            "name": "Unlimited Revisions",
            "severity": "critical",
            "clause_text": "Creator shall make revisions until Brand approval...",
            "explanation": "You could be creating content forever. There's no end to this.",
            "protection": "Cap at 2 revision rounds. Additional revisions = additional fee."
        })
        risk_score += 15

    # Check morality clause
    if 'morality' in text_lower or 'moral' in text_lower or 'public disrepute' in text_lower:
        if 'brand' not in text_lower or 'mutual' not in text_lower:
            red_flags.append({
                "name": "One-Sided Morality Clause",
                "severity": "warning",
                "clause_text": "If Creator engages in conduct that damages Brand reputation...",
                "explanation": "They can terminate if YOU do something controversial, but what if THEY do? No protection for you.",
                "protection": "Make it mutual. If the brand has a scandal, you can terminate too."
            })
            risk_score += 10

    # Determine campaign type
    if 'ambassador' in text_lower:
        campaign_type = "ambassador"
    elif 'ongoing' in text_lower or 'monthly' in text_lower:
        campaign_type = "ongoing"
    else:
        campaign_type = "one_off"

    # Generate summary
    critical_count = len([r for r in red_flags if r['severity'] == 'critical'])
    if critical_count > 0:
        summary = f"This brand deal has {critical_count} major problem(s) that could cost you money or limit your future deals. "
    else:
        summary = "This contract is fairly standard, but there are some terms to negotiate. "

    if has_perpetual_rights:
        summary += "The perpetual rights clause is a big deal - don't accept this without significant extra pay."

    # Generate negotiation script
    script = """WHAT TO SAY TO THE BRAND:

"""
    if has_perpetual_rights:
        script += """RE: USAGE RIGHTS
"I'm happy to grant extended usage, but perpetual rights require additional
compensation. My rate for perpetual rights is [3x base rate]. Alternatively,
I can offer 90-day usage at my standard rate with renewal options."

"""
    if exclusivity_scope:
        script += """RE: EXCLUSIVITY
"I need a specific list of competitors for the exclusivity clause. 'Including
but not limited to' is too broad and could prevent me from taking legitimate
work. Please provide named companies only, and let's discuss the exclusivity
period - my standard is campaign duration plus 30 days."

"""
    if has_ai_training_rights:
        script += """RE: AI TRAINING
"I'm not comfortable with AI training rights at this time. Please remove
this clause. If this is essential to the campaign, I'd need to understand
the specific use case and negotiate appropriate compensation."

"""
    script += """GENERAL TIPS:
- Never accept first offer on usage rights
- Exclusivity = extra compensation
- Get everything in writing
- Don't sign same day - take time to review
- Counter-offer is expected - don't be afraid to negotiate
"""

    return {
        "overall_risk": "high" if risk_score >= 50 else "medium" if risk_score >= 30 else "low",
        "risk_score": min(100, risk_score),
        "brand_name": None,
        "campaign_type": campaign_type,
        "usage_rights_duration": usage_rights_duration,
        "exclusivity_scope": exclusivity_scope,
        "payment_terms": payment_terms,
        "has_perpetual_rights": has_perpetual_rights,
        "has_ai_training_rights": has_ai_training_rights,
        "ftc_compliance": ftc_compliance,
        "red_flags": red_flags,
        "summary": summary,
        "negotiation_script": script
    }
