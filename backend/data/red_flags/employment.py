EMPLOYMENT_RED_FLAGS = {
    "broad_non_compete": {
        "name": "Overly Broad Non-Compete",
        "keywords": ["non-compete", "covenant not to compete", "compete with"],
        "severity": "critical",
        "explanation": "This could prevent you from working in your industry for years after leaving.",
        "protection": "Check your state's laws. Negotiate scope, geography, and duration."
    },
    "mandatory_arbitration": {
        "name": "Mandatory Arbitration",
        "keywords": ["binding arbitration", "arbitration agreement", "waive right to jury"],
        "severity": "warning",
        "explanation": "You give up your right to sue. Arbitration typically favors employers who use it repeatedly.",
        "protection": "Look for opt-out provisions (often within 30 days). Consider negotiating removal."
    },
    "class_action_waiver": {
        "name": "Class Action Waiver",
        "keywords": ["class action", "collective action", "waive right to participate"],
        "severity": "warning",
        "explanation": "You can't join other employees in lawsuits. Makes it expensive to pursue small claims.",
        "protection": "Some waivers are unenforceable. Consult an employment attorney if concerned."
    },
    "broad_ip_assignment": {
        "name": "Broad IP Assignment",
        "keywords": ["all inventions", "work product", "assign all rights", "intellectual property"],
        "severity": "warning",
        "explanation": "The company may own things you create on your own time, with your own resources.",
        "protection": "Check state protections (CA, IL, WA, DE, MN, NC, NV). Attach prior inventions list."
    },
    "no_moonlighting": {
        "name": "No Outside Work",
        "keywords": ["sole employer", "exclusive", "no other employment", "outside business"],
        "severity": "info",
        "explanation": "You may not be allowed to do freelance work or side projects.",
        "protection": "Negotiate explicit carve-outs for non-competing activities."
    },
    "clawback_provisions": {
        "name": "Clawback Provisions",
        "keywords": ["clawback", "repay", "forfeit", "return bonus"],
        "severity": "warning",
        "explanation": "You may have to return bonuses or other compensation if you leave.",
        "protection": "Understand triggers. Negotiate reasonable vesting schedules."
    },
    "garden_leave_unpaid": {
        "name": "Garden Leave Without Pay",
        "keywords": ["garden leave", "transition period"],
        "severity": "critical",
        "explanation": "You can't work during the transition but they're not paying you.",
        "protection": "Massachusetts requires 50% pay. Negotiate pay continuation."
    }
}
