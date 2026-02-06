from pydantic import BaseModel
from typing import Optional


class GymRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str


class GymContractInput(BaseModel):
    contract_text: str
    state: Optional[str] = None


class GymContractReport(BaseModel):
    overall_risk: str
    risk_score: int
    gym_name: Optional[str]
    contract_type: str
    monthly_fee: Optional[str]
    cancellation_difficulty: str
    red_flags: list[GymRedFlag]
    state_protections: list[str]
    summary: str
    cancellation_guide: str
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None
