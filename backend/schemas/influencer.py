from pydantic import BaseModel
from typing import Optional


class InfluencerRedFlag(BaseModel):
    name: str
    severity: str
    clause_text: Optional[str]
    explanation: str
    protection: str


class InfluencerContractInput(BaseModel):
    contract_text: str
    base_rate: Optional[int] = None  # To calculate fair usage premiums


class InfluencerContractReport(BaseModel):
    overall_risk: str
    risk_score: int
    brand_name: Optional[str]
    campaign_type: str  # "one_off", "ongoing", "ambassador"
    usage_rights_duration: Optional[str]
    exclusivity_scope: Optional[str]
    payment_terms: Optional[str]
    has_perpetual_rights: bool
    has_ai_training_rights: bool
    ftc_compliance: str  # "addressed", "unclear", "missing"
    red_flags: list[InfluencerRedFlag]
    summary: str
    negotiation_script: str
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None
