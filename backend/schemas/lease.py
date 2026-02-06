from pydantic import BaseModel
from typing import Optional


class LeaseInsuranceClause(BaseModel):
    clause_type: str
    original_text: str
    summary: str
    risk_level: str
    explanation: str
    recommendation: str


class LeaseRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str


class LeaseAnalysisInput(BaseModel):
    lease_text: str
    state: Optional[str] = None
    lease_type: Optional[str] = "commercial"


class LeaseAnalysisReport(BaseModel):
    overall_risk: str
    risk_score: int
    lease_type: str
    landlord_name: Optional[str]
    tenant_name: Optional[str]
    property_address: Optional[str]
    lease_term: Optional[str]
    insurance_requirements: list[LeaseInsuranceClause]
    red_flags: list[LeaseRedFlag]
    missing_protections: list[str]
    summary: str
    negotiation_letter: str
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None
