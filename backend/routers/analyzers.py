import json

from fastapi import APIRouter, HTTPException, Request
from config import MOCK_MODE, OPENAI_MODEL
from services.llm import get_client, clean_llm_response, parse_limit_to_number, calculate_extraction_confidence
from services.auth import get_current_user, hash_document, check_premium_access, use_credit
from services.db_ops import save_upload
from services.mock.coi import mock_coi_extract, mock_compliance_check
from services.mock.lease import mock_lease_analysis
from services.mock.gym import mock_gym_analysis
from services.mock.employment import mock_employment_analysis
from services.mock.freelancer import mock_freelancer_analysis
from services.mock.influencer import mock_influencer_analysis
from services.mock.timeshare import mock_timeshare_analysis
from services.mock.insurance_policy import mock_insurance_policy_analysis

from schemas.common import (
    COIComplianceInput, ComplianceReport,
)
from schemas.lease import LeaseAnalysisInput, LeaseAnalysisReport, LeaseInsuranceClause, LeaseRedFlag
from schemas.gym import GymContractInput, GymContractReport
from schemas.employment import EmploymentContractInput, EmploymentContractReport
from schemas.freelancer import FreelancerContractInput, FreelancerContractReport
from schemas.influencer import InfluencerContractInput, InfluencerContractReport
from schemas.timeshare import TimeshareContractInput, TimeshareContractReport
from schemas.insurance_policy import InsurancePolicyInput, InsurancePolicyReport

from prompts.coi import COI_EXTRACTION_PROMPT, COI_COMPLIANCE_PROMPT
from prompts.lease import LEASE_EXTRACTION_PROMPT, LEASE_ANALYSIS_PROMPT
from prompts.gym import GYM_ANALYSIS_PROMPT
from prompts.employment import EMPLOYMENT_ANALYSIS_PROMPT
from prompts.freelancer import FREELANCER_ANALYSIS_PROMPT
from prompts.influencer import INFLUENCER_ANALYSIS_PROMPT
from prompts.timeshare import TIMESHARE_ANALYSIS_PROMPT
from prompts.insurance_policy import INSURANCE_POLICY_ANALYSIS_PROMPT

from data.project_types import PROJECT_TYPE_REQUIREMENTS
from data.states import (
    STATE_GYM_PROTECTIONS,
    NON_COMPETE_STATES,
    TIMESHARE_RESCISSION,
)
from data.red_flags import LEASE_RED_FLAGS, GYM_RED_FLAGS, EMPLOYMENT_RED_FLAGS

router = APIRouter(prefix="/api", tags=["analyzers"])


# ============== COI COMPLIANCE CHECK ==============

@router.post("/check-coi-compliance", response_model=ComplianceReport)
async def check_coi_compliance(input: COIComplianceInput, request: Request):
    """Check a Certificate of Insurance against contract requirements"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.coi_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        # Get requirements from preset or custom
        if input.project_type and input.project_type in PROJECT_TYPE_REQUIREMENTS:
            requirements = PROJECT_TYPE_REQUIREMENTS[input.project_type]
        elif input.custom_requirements:
            requirements = input.custom_requirements
        else:
            # Default to commercial construction requirements
            requirements = PROJECT_TYPE_REQUIREMENTS["commercial_construction"]

        project_type_name = requirements.get('name', 'Commercial Construction')

        # Use mock mode or real API
        if MOCK_MODE:
            coi_data = mock_coi_extract(input.coi_text)
            result = mock_compliance_check(coi_data, requirements, input.state)
            # Save upload
            save_upload("coi", input.coi_text, input.state, result, user_id=user.id if user else None)
            report = ComplianceReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("critical_gaps", [])) + len(result.get("warnings", []))
            return report

        # Step 1: Extract COI data
        extract_prompt = COI_EXTRACTION_PROMPT.replace("<<DOCUMENT>>", input.coi_text)
        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": extract_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        coi_data = json.loads(response_text)

        # Step 2: Check compliance
        compliance_prompt = COI_COMPLIANCE_PROMPT.replace("<<COI_DATA>>", json.dumps(coi_data, indent=2))
        compliance_prompt = compliance_prompt.replace("<<REQUIREMENTS>>", json.dumps(requirements, indent=2))
        compliance_prompt = compliance_prompt.replace("<<PROJECT_TYPE>>", project_type_name)

        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": compliance_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        result = json.loads(response_text)
        result['coi_data'] = coi_data

        # Calculate extraction confidence metadata
        extraction_metadata = calculate_extraction_confidence(coi_data)
        result['extraction_metadata'] = extraction_metadata

        # Save upload
        save_upload("coi", input.coi_text, input.state, result, user_id=user.id if user else None)

        report = ComplianceReport(**result)
        report.document_hash = doc_hash
        report.is_premium = is_premium
        report.total_issues = len(result.get("critical_gaps", [])) + len(result.get("warnings", []))
        return report

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== LEASE ANALYSIS ==============

@router.post("/analyze-lease", response_model=LeaseAnalysisReport)
async def analyze_lease(input: LeaseAnalysisInput, request: Request):
    """Analyze a lease for insurance-related red flags and risks"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.lease_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        # Mock mode
        if MOCK_MODE:
            result = mock_lease_analysis(input.lease_text, input.state)
            save_upload("lease", input.lease_text, input.state, result, user_id=user.id if user else None)
            report = LeaseAnalysisReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("red_flags", [])) + len(result.get("missing_protections", []))
            return report

        client = get_client()

        # Step 1: Extract lease data
        extract_prompt = LEASE_EXTRACTION_PROMPT.replace("<<DOCUMENT>>", input.lease_text[:15000])  # Limit length

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": extract_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        lease_data = json.loads(response_text)

        # Step 2: Analyze for red flags
        analysis_prompt = LEASE_ANALYSIS_PROMPT.replace("<<LEASE_DATA>>", json.dumps(lease_data, indent=2))
        analysis_prompt = analysis_prompt.replace("<<RED_FLAGS>>", json.dumps(LEASE_RED_FLAGS, indent=2))
        analysis_prompt = analysis_prompt.replace("<<STATE>>", input.state or "Not specified")

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": analysis_prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        analysis = json.loads(response_text)

        # Merge extraction and analysis
        result = {
            "overall_risk": analysis.get("overall_risk", "medium"),
            "risk_score": analysis.get("risk_score", 50),
            "red_flags": analysis.get("red_flags", [])
        }
        save_upload("lease", input.lease_text, input.state, result, user_id=user.id if user else None)

        # Calculate total issues for teaser
        red_flags = analysis.get("red_flags", [])
        missing_protections = analysis.get("missing_protections", [])
        total_issues = len(red_flags) + len(missing_protections)

        return LeaseAnalysisReport(
            overall_risk=analysis.get("overall_risk", "medium"),
            risk_score=analysis.get("risk_score", 50),
            lease_type=lease_data.get("lease_type", input.lease_type),
            landlord_name=lease_data.get("landlord_name"),
            tenant_name=lease_data.get("tenant_name"),
            property_address=lease_data.get("property_address"),
            lease_term=lease_data.get("lease_term"),
            insurance_requirements=[LeaseInsuranceClause(**r) for r in analysis.get("insurance_requirements", [])],
            red_flags=[LeaseRedFlag(**r) for r in red_flags],
            missing_protections=missing_protections,
            summary=analysis.get("summary", "Analysis complete."),
            negotiation_letter=analysis.get("negotiation_letter", ""),
            document_hash=doc_hash,
            is_premium=is_premium,
            total_issues=total_issues
        )

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lease analysis failed: {str(e)}")


# ============== GYM CONTRACT ANALYSIS ==============

@router.post("/analyze-gym", response_model=GymContractReport)
async def analyze_gym_contract(input: GymContractInput, request: Request):
    """Analyze a gym membership contract for red flags"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.contract_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        if MOCK_MODE:
            result = mock_gym_analysis(input.contract_text, input.state)
            save_upload("gym", input.contract_text, input.state, result, user_id=user.id if user else None)
            report = GymContractReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("red_flags", []))
            return report

        client = get_client()

        # Get state laws
        state_laws = STATE_GYM_PROTECTIONS.get(input.state.upper() if input.state else "", {})

        prompt = GYM_ANALYSIS_PROMPT.replace("<<CONTRACT>>", input.contract_text[:15000])
        prompt = prompt.replace("<<STATE>>", input.state or "Not specified")
        prompt = prompt.replace("<<STATE_LAWS>>", json.dumps(state_laws, indent=2))
        prompt = prompt.replace("<<RED_FLAGS>>", json.dumps(GYM_RED_FLAGS, indent=2))

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("gym", input.contract_text, input.state, result, user_id=user.id if user else None)

        report = GymContractReport(**result)
        report.document_hash = doc_hash
        report.is_premium = is_premium
        report.total_issues = len(result.get("red_flags", []))
        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gym contract analysis failed: {str(e)}")


# ============== EMPLOYMENT CONTRACT ANALYSIS ==============

@router.post("/analyze-employment", response_model=EmploymentContractReport)
async def analyze_employment_contract(input: EmploymentContractInput, request: Request):
    """Analyze an employment contract for problematic terms"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.contract_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        if MOCK_MODE:
            result = mock_employment_analysis(input.contract_text, input.state, input.salary)
            save_upload("employment", input.contract_text, input.state, result, user_id=user.id if user else None)
            report = EmploymentContractReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("red_flags", []))
            return report

        client = get_client()

        state_rules = NON_COMPETE_STATES.get(input.state.upper() if input.state else "", {})

        prompt = EMPLOYMENT_ANALYSIS_PROMPT.replace("<<CONTRACT>>", input.contract_text[:15000])
        prompt = prompt.replace("<<STATE>>", input.state or "Not specified")
        prompt = prompt.replace("<<SALARY>>", f"${input.salary:,}" if input.salary else "Not specified")
        prompt = prompt.replace("<<STATE_RULES>>", json.dumps(state_rules, indent=2))
        prompt = prompt.replace("<<RED_FLAGS>>", json.dumps(EMPLOYMENT_RED_FLAGS, indent=2))

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("employment", input.contract_text, input.state, result, user_id=user.id if user else None)

        report = EmploymentContractReport(**result)
        report.document_hash = doc_hash
        report.is_premium = is_premium
        report.total_issues = len(result.get("red_flags", []))
        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Employment contract analysis failed: {str(e)}")


# ============== FREELANCER CONTRACT ANALYSIS ==============

@router.post("/analyze-freelancer", response_model=FreelancerContractReport)
async def analyze_freelancer_contract(input: FreelancerContractInput, request: Request):
    """Analyze a freelancer/contractor agreement"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.contract_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        if MOCK_MODE:
            result = mock_freelancer_analysis(input.contract_text, input.project_value)
            save_upload("freelancer", input.contract_text, None, result, user_id=user.id if user else None)
            report = FreelancerContractReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("red_flags", [])) + len(result.get("missing_protections", []))
            return report

        client = get_client()

        prompt = FREELANCER_ANALYSIS_PROMPT.format(
            contract_text=input.contract_text[:15000],
            project_value=f"${input.project_value:,}" if input.project_value else "Not specified"
        )

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("freelancer", input.contract_text, None, result, user_id=user.id if user else None)

        report = FreelancerContractReport(**result)
        report.document_hash = doc_hash
        report.is_premium = is_premium
        report.total_issues = len(result.get("red_flags", [])) + len(result.get("missing_protections", []))
        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Freelancer contract analysis failed: {str(e)}")


# ============== INFLUENCER CONTRACT ANALYSIS ==============

@router.post("/analyze-influencer", response_model=InfluencerContractReport)
async def analyze_influencer_contract(input: InfluencerContractInput, request: Request):
    """Analyze an influencer/sponsorship contract"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.contract_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        if MOCK_MODE:
            result = mock_influencer_analysis(input.contract_text, input.base_rate)
            save_upload("influencer", input.contract_text, None, result, user_id=user.id if user else None)
            report = InfluencerContractReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("red_flags", []))
            return report

        client = get_client()

        prompt = INFLUENCER_ANALYSIS_PROMPT.format(
            contract_text=input.contract_text[:15000],
            base_rate=f"${input.base_rate:,}" if input.base_rate else "Not specified"
        )

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("influencer", input.contract_text, None, result, user_id=user.id if user else None)

        report = InfluencerContractReport(**result)
        report.document_hash = doc_hash
        report.is_premium = is_premium
        report.total_issues = len(result.get("red_flags", []))
        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Influencer contract analysis failed: {str(e)}")


# ============== TIMESHARE CONTRACT ANALYSIS ==============

@router.post("/analyze-timeshare", response_model=TimeshareContractReport)
async def analyze_timeshare_contract(input: TimeshareContractInput, request: Request):
    """Analyze a timeshare contract"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.contract_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        if MOCK_MODE:
            result = mock_timeshare_analysis(
                input.contract_text,
                input.state,
                input.purchase_price,
                input.annual_fee
            )
            save_upload("timeshare", input.contract_text, input.state, result, user_id=user.id if user else None)
            report = TimeshareContractReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("red_flags", []))
            return report

        client = get_client()

        rescission_info = TIMESHARE_RESCISSION.get(input.state.upper() if input.state else "", {})

        prompt = TIMESHARE_ANALYSIS_PROMPT.format(
            contract_text=input.contract_text[:15000],
            state=input.state or "Not specified",
            rescission_info=json.dumps(rescission_info),
            purchase_price=f"${input.purchase_price:,}" if input.purchase_price else "Unknown",
            annual_fee=f"${input.annual_fee:,}" if input.annual_fee else "Unknown"
        )

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("timeshare", input.contract_text, input.state, result, user_id=user.id if user else None)

        report = TimeshareContractReport(**result)
        report.document_hash = doc_hash
        report.is_premium = is_premium
        report.total_issues = len(result.get("red_flags", []))
        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeshare contract analysis failed: {str(e)}")


# ============== INSURANCE POLICY ANALYSIS ==============

@router.post("/analyze-insurance-policy", response_model=InsurancePolicyReport)
async def analyze_insurance_policy(input: InsurancePolicyInput, request: Request):
    """Analyze a consumer insurance policy"""
    try:
        # Compute document hash and check premium access
        doc_hash = hash_document(input.policy_text)
        user = get_current_user(request)
        is_premium = False
        if user:
            is_premium = check_premium_access(user.id, doc_hash)

        if MOCK_MODE:
            result = mock_insurance_policy_analysis(input.policy_text, input.policy_type, input.state)
            save_upload("insurance_policy", input.policy_text, input.state, result, user_id=user.id if user else None)
            report = InsurancePolicyReport(**result)
            report.document_hash = doc_hash
            report.is_premium = is_premium
            report.total_issues = len(result.get("red_flags", [])) + len(result.get("coverage_gaps", []))
            return report

        client = get_client()

        prompt = INSURANCE_POLICY_ANALYSIS_PROMPT.format(
            policy_text=input.policy_text[:15000],
            policy_type=input.policy_type or "Determine from text",
            state=input.state or "Not specified"
        )

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.choices[0].message.content
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        result = json.loads(response_text.strip())
        save_upload("insurance_policy", input.policy_text, input.state, result, user_id=user.id if user else None)

        report = InsurancePolicyReport(**result)
        report.document_hash = doc_hash
        report.is_premium = is_premium
        report.total_issues = len(result.get("red_flags", [])) + len(result.get("coverage_gaps", []))
        return report

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insurance policy analysis failed: {str(e)}")
