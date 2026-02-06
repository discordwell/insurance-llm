from pydantic import BaseModel
from typing import Optional


class EmploymentRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str


class EmploymentContractInput(BaseModel):
    contract_text: str
    state: Optional[str] = None
    salary: Optional[int] = None


class EmploymentContractReport(BaseModel):
    overall_risk: str
    risk_score: int
    document_type: str
    has_non_compete: bool
    non_compete_enforceable: Optional[str]
    has_arbitration: bool
    has_ip_assignment: bool
    red_flags: list[EmploymentRedFlag]
    state_notes: list[str]
    summary: str
    negotiation_points: str
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None
