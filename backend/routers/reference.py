from fastapi import APIRouter, HTTPException
from data.states import STATE_WORKERS_COMP, STATE_ANTI_INDEMNITY, STATE_GL_REQUIREMENTS, STATE_AUTO_MINIMUMS
from data.project_types import PROJECT_TYPE_REQUIREMENTS

router = APIRouter(prefix="/api", tags=["reference"])


@router.get("/project-types")
async def get_project_types():
    """Get available preset project types and their requirements"""
    return {
        key: {
            "name": val["name"],
            "gl_per_occurrence": f"${val['gl_per_occurrence']:,}",
            "gl_aggregate": f"${val['gl_aggregate']:,}",
            "umbrella_required": val.get("umbrella_required", False),
            "umbrella_minimum": f"${val.get('umbrella_minimum', 0):,}" if val.get('umbrella_minimum', 0) > 0 else None,
        }
        for key, val in PROJECT_TYPE_REQUIREMENTS.items()
    }


@router.get("/states")
async def get_states():
    """Get list of all states with summary of their insurance rules"""
    states = []
    for state_code in sorted(STATE_WORKERS_COMP.keys()):
        wc = STATE_WORKERS_COMP.get(state_code, {})
        ai = STATE_ANTI_INDEMNITY.get(state_code, {})
        gl = STATE_GL_REQUIREMENTS.get(state_code, {})

        states.append({
            "code": state_code,
            "wc_required": wc.get('required', True),
            "wc_threshold": wc.get('threshold'),
            "monopolistic_wc": wc.get('monopolistic', False),
            "anti_indemnity_type": ai.get('type', 'Unknown'),
            "voids_ai_coverage": ai.get('voids_ai_for_sole_negligence', False),
            "gl_required_for_license": gl.get('required_for_license', False),
            "risk_level": "HIGH" if ai.get('voids_ai_for_sole_negligence') else ("MEDIUM" if ai.get('type') not in ['None', None] else "LOW")
        })
    return states


@router.get("/state/{state_code}")
async def get_state_details(state_code: str):
    """Get detailed insurance requirements for a specific state"""
    state_upper = state_code.upper()

    if state_upper not in STATE_WORKERS_COMP:
        raise HTTPException(status_code=404, detail=f"State {state_upper} not found")

    wc = STATE_WORKERS_COMP.get(state_upper, {})
    ai = STATE_ANTI_INDEMNITY.get(state_upper, {})
    gl = STATE_GL_REQUIREMENTS.get(state_upper, {})
    auto = STATE_AUTO_MINIMUMS.get(state_upper, {})

    return {
        "state": state_upper,
        "workers_comp": {
            "required": wc.get('required', True),
            "threshold": wc.get('threshold'),
            "construction_specific": wc.get('construction_specific'),
            "monopolistic": wc.get('monopolistic', False),
            "notes": "Must purchase through state fund" if wc.get('monopolistic') else ("Voluntary state" if not wc.get('required') else "Standard private market")
        },
        "anti_indemnity": {
            "type": ai.get('type', 'Unknown'),
            "voids_ai_for_negligence": ai.get('voids_ai_for_sole_negligence', False),
            "insurance_savings_clause": ai.get('insurance_savings_clause', True),
            "notes": ai.get('notes', ''),
            "risk_level": "CRITICAL" if ai.get('voids_ai_for_sole_negligence') else "STANDARD"
        },
        "general_liability": {
            "required_for_license": gl.get('required_for_license', False),
            "minimum_per_occurrence": f"${gl.get('minimum_per_occurrence'):,}" if gl.get('minimum_per_occurrence') else None,
            "notes": gl.get('notes', '')
        },
        "auto_liability": {
            "bodily_injury_per_person": f"${auto.get('bodily_injury_per_person', 25000):,}",
            "bodily_injury_per_accident": f"${auto.get('bodily_injury_per_accident', 50000):,}",
            "property_damage": f"${auto.get('property_damage', 25000):,}",
            "combined_format": f"{auto.get('bodily_injury_per_person', 25000)//1000}/{auto.get('bodily_injury_per_accident', 50000)//1000}/{auto.get('property_damage', 25000)//1000}"
        }
    }


@router.get("/ai-limited-states")
async def get_ai_limited_states():
    """Get states with broad anti-indemnity statutes that limit AI coverage"""
    mitigations = {
        "AZ": ["CG 24 26 endorsement (excludes your negligence from AI)", "Higher primary limits on your own CGL"],
        "CO": ["Wrap-up/OCIP for larger projects", "Contractual liability coverage on your policy", "Explicit fault allocation in subcontracts"],
        "GA": ["Primary & non-contributory language still valid", "Ensure your own CGL has adequate limits"],
        "KS": ["Wrap-up programs", "Higher umbrella limits on your policy"],
        "MT": ["OCIP/CCIP wrap-up insurance", "Project-specific coverage", "Your own policy must be primary"],
        "OR": ["CG 24 26 amendment endorsement", "Contractual liability on your CGL"],
    }

    states = []
    for state_code, ai_rules in STATE_ANTI_INDEMNITY.items():
        if ai_rules.get('voids_ai_for_sole_negligence'):
            states.append({
                "state": state_code,
                "statute_type": ai_rules.get('type'),
                "mitigation_options": mitigations.get(state_code, []),
                "insurance_savings_clause": ai_rules.get('insurance_savings_clause', False)
            })
    return {
        "states": states,
        "count": len(states),
        "note": "These states have broad anti-indemnity statutes. AI coverage may be limited when you share fault. See mitigation options for each state."
    }
