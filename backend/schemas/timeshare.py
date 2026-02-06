from pydantic import BaseModel
from typing import Optional


class TimeshareRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str


class TimeshareContractInput(BaseModel):
    contract_text: str
    state: Optional[str] = None
    purchase_price: Optional[int] = None
    annual_fee: Optional[int] = None


class TimeshareContractReport(BaseModel):
    overall_risk: str  # Almost always "high" for timeshares
    risk_score: int
    resort_name: Optional[str]
    ownership_type: str  # "deeded", "right_to_use", "points", "unknown"
    has_perpetuity_clause: bool
    rescission_deadline: Optional[str]
    estimated_10yr_cost: Optional[str]
    red_flags: list[TimeshareRedFlag]
    exit_options: list[str]
    summary: str
    rescission_letter: str
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None
