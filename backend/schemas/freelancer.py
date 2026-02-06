from pydantic import BaseModel
from typing import Optional


class FreelancerRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str


class FreelancerContractInput(BaseModel):
    contract_text: str
    project_value: Optional[int] = None


class FreelancerContractReport(BaseModel):
    overall_risk: str
    risk_score: int
    contract_type: str  # "project", "retainer", "sow"
    payment_terms: Optional[str]
    ip_ownership: str  # "work_for_hire", "license", "assignment", "unclear"
    has_kill_fee: bool
    revision_limit: Optional[str]
    red_flags: list[FreelancerRedFlag]
    missing_protections: list[str]
    summary: str
    suggested_changes: str
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None
