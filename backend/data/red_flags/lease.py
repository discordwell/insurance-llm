# Lease insurance red flags to check
LEASE_RED_FLAGS = {
    "blanket_indemnification": {
        "name": "Blanket Indemnification",
        "keywords": ["indemnify", "hold harmless", "defend"],
        "bad_pattern": "all claims",  # Without negligence carve-out
        "severity": "critical",
        "explanation": "You may be agreeing to pay for the landlord's mistakes, not just your own.",
        "protection": "Add 'except to the extent caused by landlord's negligence or willful misconduct'"
    },
    "landlord_not_liable": {
        "name": "Landlord Not Liable Clause",
        "keywords": ["landlord shall not be liable", "not responsible for", "waives all claims"],
        "severity": "critical",
        "explanation": "Landlord is trying to eliminate liability even for their own negligence.",
        "protection": "Add 'except for landlord's negligence or willful misconduct'"
    },
    "insurance_proceeds_to_landlord": {
        "name": "Insurance Proceeds to Landlord",
        "keywords": ["insurance proceeds", "paid to landlord", "payable to lessor"],
        "severity": "critical",
        "explanation": "Your insurance payout for your improvements could go to the landlord instead of you.",
        "protection": "Ensure your improvements coverage pays you directly"
    },
    "no_tenant_termination": {
        "name": "No Tenant Termination Right",
        "keywords": ["landlord may terminate", "tenant shall have no right"],
        "severity": "critical",
        "explanation": "If there's major damage, landlord can walk away but you're stuck waiting or paying rent.",
        "protection": "Negotiate mutual termination rights or tenant termination if repairs exceed 90-180 days"
    },
    "additional_insured_requirement": {
        "name": "Additional Insured Requirement",
        "keywords": ["additional insured", "named insured"],
        "severity": "warning",
        "explanation": "Landlord will share YOUR policy limits. If they use $500K defending themselves, you only have $500K left.",
        "protection": "Increase liability limits to account for sharing. Negotiate to exclude landlord's sole negligence."
    },
    "primary_noncontributory": {
        "name": "Primary and Non-Contributory",
        "keywords": ["primary and non-contributory", "primary basis", "non-contributory"],
        "severity": "warning",
        "explanation": "Your policy pays first even if the landlord was at fault. Very landlord-favorable.",
        "protection": "Resist this language or significantly increase your limits"
    },
    "waiver_of_subrogation": {
        "name": "Waiver of Subrogation",
        "keywords": ["waiver of subrogation", "waive subrogation", "waiver of recovery"],
        "severity": "warning",
        "explanation": "If landlord's negligence damages your property, your insurer can't sue them to recover. You eat the deductibles and gaps.",
        "protection": "Ensure it's mutual. Get the endorsement on your policy. Negotiate carve-outs for gross negligence."
    },
    "self_insurance_requirement": {
        "name": "Self-Insurance/High Deductible",
        "keywords": ["self-insure", "first $", "deductible of"],
        "severity": "warning",
        "explanation": "This is a hidden cost - every claim will cost you this amount out of pocket.",
        "protection": "Negotiate down or eliminate. Budget for it if unavoidable."
    },
    "coverage_lapse_default": {
        "name": "Coverage Lapse = Default",
        "keywords": ["lapse in coverage", "failure to maintain", "immediate default"],
        "severity": "warning",
        "explanation": "A paperwork error by your insurer could get you evicted.",
        "protection": "Negotiate a 30-day cure period. Set up automatic payments."
    },
    "landlord_can_purchase_insurance": {
        "name": "Landlord Can Buy and Charge Back",
        "keywords": ["landlord may purchase", "charge to tenant", "additional rent"],
        "severity": "warning",
        "explanation": "Landlord buys overpriced coverage and bills you at a markup as 'rent'.",
        "protection": "Negotiate right to cure before landlord can purchase. Cap chargebacks at market rates."
    },
    "care_custody_control_gap": {
        "name": "Care, Custody & Control Gap",
        "keywords": ["damage to premises", "damage to building", "tenant responsible for"],
        "severity": "warning",
        "explanation": "Your GL policy excludes damage to property you rent. You could be personally liable for building damage.",
        "protection": "Add 'Damage to Premises Rented to You' coverage (Fire Legal Liability) with adequate limits."
    },
    "betterments_ownership": {
        "name": "Improvements Become Landlord's Property",
        "keywords": ["improvements shall become", "property of landlord", "tenant improvements"],
        "severity": "warning",
        "explanation": "Your $300K build-out becomes theirs - and they may not insure it.",
        "protection": "Get Betterments & Improvements coverage at replacement cost. Clarify who insures what in writing."
    },
    "unlimited_repair_timeline": {
        "name": "No Repair Deadline",
        "keywords": ["reasonable time", "diligent efforts", "as soon as practicable"],
        "severity": "warning",
        "explanation": "Landlord has no urgency to repair - especially if they're collecting loss-of-rents insurance.",
        "protection": "Negotiate hard deadlines (90-180 days max) with termination rights if not met."
    },
    "no_rent_abatement": {
        "name": "No Rent Abatement",
        "keywords": ["rent shall continue", "no abatement", "rent not reduced"],
        "severity": "critical",
        "explanation": "You keep paying rent even when you can't use the space due to damage.",
        "protection": "Negotiate rent abatement during any period the premises are unusable."
    },
    "extraordinary_coverage": {
        "name": "Unusual Coverage Requirements",
        "keywords": ["terrorism", "pollution", "cyber", "earthquake", "flood"],
        "severity": "info",
        "explanation": "Some of these coverages may be expensive, unavailable, or inapplicable to your business.",
        "protection": "Only agree to coverage that's available, affordable, and applicable. Add 'if commercially available at reasonable cost'."
    }
}
