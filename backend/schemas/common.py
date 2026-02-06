from pydantic import BaseModel
from typing import Optional


class DocumentInput(BaseModel):
    text: str
    doc_type: Optional[str] = "auto"


class Coverage(BaseModel):
    type: str
    limit: str
    deductible: Optional[str] = None
    notes: Optional[str] = None


class FieldConfidence(BaseModel):
    level: str
    reason: Optional[str] = None
    source_quote: Optional[str] = None


class COIData(BaseModel):
    insured_name: Optional[str] = None
    policy_number: Optional[str] = None
    carrier: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    gl_limit_per_occurrence: Optional[str] = None
    gl_limit_aggregate: Optional[str] = None
    workers_comp: bool = False
    auto_liability: bool = False
    umbrella_limit: Optional[str] = None
    additional_insured_checked: bool = False
    waiver_of_subrogation_checked: bool = False
    primary_noncontributory: bool = False
    certificate_holder: Optional[str] = None
    description_of_operations: Optional[str] = None
    cg_20_10_endorsement: bool = False
    cg_20_37_endorsement: bool = False
    confidence: Optional[dict[str, FieldConfidence]] = None


class ExtractionMetadata(BaseModel):
    overall_confidence: float
    needs_human_review: bool
    review_reasons: list[str] = []
    low_confidence_fields: list[str] = []
    extraction_notes: Optional[str] = None


class ComplianceRequirement(BaseModel):
    name: str
    required_value: str
    actual_value: str
    status: str
    explanation: str


class ComplianceReport(BaseModel):
    overall_status: str
    coi_data: COIData
    critical_gaps: list[ComplianceRequirement] = []
    warnings: list[ComplianceRequirement] = []
    passed: list[ComplianceRequirement] = []
    risk_exposure: str
    fix_request_letter: str
    extraction_metadata: Optional[ExtractionMetadata] = None
    document_hash: Optional[str] = None
    is_premium: bool = False
    total_issues: Optional[int] = None

    def __init__(self, **data):
        for field in ['critical_gaps', 'warnings', 'passed']:
            if data.get(field) is None:
                data[field] = []
        super().__init__(**data)


class COIComplianceInput(BaseModel):
    coi_text: str
    project_type: Optional[str] = None
    custom_requirements: Optional[dict] = None
    state: Optional[str] = None


class OCRInput(BaseModel):
    file_data: str
    file_type: str
    file_name: str


class ClassifyInput(BaseModel):
    text: str


class ClassifyResult(BaseModel):
    document_type: str
    confidence: float
    description: str
    supported: bool


class ExtractedPolicy(BaseModel):
    insured_name: Optional[str] = None
    policy_number: Optional[str] = None
    carrier: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    coverages: Optional[list[Coverage]] = []
    total_premium: Optional[str] = None
    exclusions: Optional[list[str]] = []
    special_conditions: Optional[list[str]] = []
    risk_score: Optional[int] = None
    compliance_issues: Optional[list[str]] = []
    summary: Optional[str] = None

    def __init__(self, **data):
        for field in ['coverages', 'exclusions', 'special_conditions', 'compliance_issues']:
            if data.get(field) is None:
                data[field] = []
        super().__init__(**data)


class WaitlistInput(BaseModel):
    email: str
    document_type: str
    document_text: Optional[str] = None


class WaitlistResponse(BaseModel):
    success: bool
    message: str
