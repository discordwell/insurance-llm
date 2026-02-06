from schemas.common import (
    DocumentInput, Coverage, ExtractedPolicy, FieldConfidence,
    COIData, ExtractionMetadata, ComplianceRequirement, ComplianceReport,
    COIComplianceInput, OCRInput, ClassifyInput, ClassifyResult,
    WaitlistInput, WaitlistResponse
)
from schemas.auth import SignupInput, LoginInput, AuthResponse, UserInfo, CheckoutInput
from schemas.lease import LeaseInsuranceClause, LeaseRedFlag, LeaseAnalysisInput, LeaseAnalysisReport
from schemas.gym import GymRedFlag, GymContractInput, GymContractReport
from schemas.employment import EmploymentRedFlag, EmploymentContractInput, EmploymentContractReport
from schemas.freelancer import FreelancerRedFlag, FreelancerContractInput, FreelancerContractReport
from schemas.influencer import InfluencerRedFlag, InfluencerContractInput, InfluencerContractReport
from schemas.timeshare import TimeshareRedFlag, TimeshareContractInput, TimeshareContractReport
from schemas.insurance_policy import InsurancePolicyRedFlag, InsurancePolicyInput, InsurancePolicyReport
