from pydantic import BaseModel
from typing import Optional


class InsurancePolicyRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    what_to_ask: str


class InsurancePolicyInput(BaseModel):
    policy_text: str
    policy_type: Optional[str] = None  # "auto", "home", "renters", "health"
    state: Optional[str] = None


class InsurancePolicyReport(BaseModel):
    overall_risk: str
    risk_score: int
    policy_type: str
    carrier: Optional[str]
    coverage_type: str  # "named_perils", "open_perils", "unknown"
    valuation_method: str  # "actual_cash_value", "replacement_cost", "unknown"
    deductible_type: str  # "flat", "percentage", "unknown"
    has_arbitration: bool
    red_flags: list[InsurancePolicyRedFlag]
    coverage_gaps: list[str]
    summary: str
    questions_for_agent: str
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None
