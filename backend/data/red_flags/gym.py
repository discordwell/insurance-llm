GYM_RED_FLAGS = {
    "in_person_cancel": {
        "name": "In-Person Cancellation Only",
        "keywords": ["in person", "visit", "home club", "location"],
        "severity": "critical",
        "explanation": "You can only cancel by physically going to the gym. FTC sued LA Fitness for this exact practice in 2025.",
        "protection": "Check if your state requires alternative cancellation methods. Send certified mail anyway and document everything."
    },
    "certified_mail_only": {
        "name": "Certified Mail Required",
        "keywords": ["certified mail", "registered mail", "return receipt"],
        "severity": "warning",
        "explanation": "They're making it deliberately inconvenient to cancel. You have to go to the post office.",
        "protection": "Send certified mail with return receipt. Keep the receipt forever."
    },
    "long_notice_period": {
        "name": "Excessive Notice Period",
        "keywords": ["30 days", "60 days", "prior to billing"],
        "severity": "warning",
        "explanation": "Miss the window by a day and you're locked in for another month or year.",
        "protection": "Set calendar reminders. Document when you sent cancellation notice."
    },
    "auto_renewal": {
        "name": "Automatic Renewal",
        "keywords": ["automatically renew", "auto-renew", "continuous", "successive"],
        "severity": "warning",
        "explanation": "Your contract keeps going unless you actively stop it during a narrow window.",
        "protection": "Set reminder 60 days before renewal. Check your state's renewal notification requirements."
    },
    "annual_fee": {
        "name": "Hidden Annual Fee",
        "keywords": ["annual fee", "enhancement fee", "yearly fee", "maintenance fee"],
        "severity": "warning",
        "explanation": "Separate from monthly dues - often buried in the contract. Planet Fitness charges $49.99/year on top of monthly fees.",
        "protection": "Calculate total annual cost including all fees before signing."
    },
    "no_freeze": {
        "name": "No Freeze/Pause Option",
        "keywords": [],  # Absence detection
        "severity": "warning",
        "explanation": "If you get injured or travel, you keep paying.",
        "protection": "Negotiate freeze terms before signing. Most gyms offer this but don't advertise it."
    },
    "early_termination_fee": {
        "name": "Early Termination Fee",
        "keywords": ["early termination", "buyout", "remaining balance", "cancellation fee"],
        "severity": "warning",
        "explanation": "You may owe hundreds of dollars to exit the contract early.",
        "protection": "Check if fee exceeds your state's legal cap. Some states limit these fees."
    },
    "arbitration_clause": {
        "name": "Forced Arbitration",
        "keywords": ["arbitration", "waive", "class action", "jury trial"],
        "severity": "warning",
        "explanation": "You can't sue them or join a class action lawsuit - you have to go to private arbitration where they have the advantage.",
        "protection": "This is increasingly common. You may be able to opt out within 30 days of signing."
    },
    "personal_training_separate": {
        "name": "Personal Training is Separate",
        "keywords": ["personal training", "separate agreement", "pt contract"],
        "severity": "info",
        "explanation": "Canceling your membership does NOT cancel personal training. You could owe thousands.",
        "protection": "Review and cancel personal training separately. PT contracts often have stricter terms."
    }
}
